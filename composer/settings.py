"""Your settings (non-secret, inside the current data generation) and your model key (a separate file, 0600).

  <data>/generations/<g>/config.json    provider, model, sources, narration, schedule, port, backups
  <data>/generations/<g>/sources.json   sources you added (the bundled ones are always there)
  <data>/secrets.env                    NAME=value lines, mode 0600, in a folder only you can open (0700)

The key file is read when a model call is made, never copied into the process environment, never printed,
never logged, and not included in backups unless you ask (`composer backup --include-secrets`).
"""
from __future__ import annotations

import copy
import json
import os
import re
import stat
from pathlib import Path

from .home import atomic_write, private_folder, touch_private

CONFIG_SCHEMA = "composer-config/v1"
SECRETS = "secrets.env"
WRITER_KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")
CHECKER_KEY = "COMPOSER_CHECKER_API_KEY"  # the optional separate checker model's key, under its own name
KEY_NAMES = (*WRITER_KEY_NAMES, CHECKER_KEY)
VOICES = ("af_heart", "am_michael", "bf_emma")
DEFAULTS = {
    "schema": CONFIG_SCHEMA,
    "provider": {"kind": "anthropic", "model": "", "base_url": "", "key": "none", "key_env": "ANTHROPIC_API_KEY"},
    # the model that checks the claims: the writer's own unless `same` is false
    "checker": {"same": True, "kind": "anthropic", "model": "", "base_url": "", "key": "none", "key_env": CHECKER_KEY},
    "narration": {"enabled": False, "engine": "none", "model_path": "", "voices_path": "", "python": "",
                  "url": "", "voices": [], "reused": False, "max_bytes": 120000, "max_seconds": 600},
    "schedule": {"enabled": False, "time": "07:00", "timezone": "local", "sources": ["google-ai", "deepmind"],
                 "lens": "what changed this week that a builder should act on", "insights": 5},
    "backup": {"weekly": True, "keep": 8},
    "server": {"port": 8765},
    "extraction": {"trafilatura": False},
    "seals": {"daily": True},
}
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SettingsError(ValueError):
    pass


def generation_dir(data: Path, *, create: bool = True) -> Path:
    """The current generation's folder, creating the versioned data root the first time."""
    pointer = data / "current"
    if not pointer.exists():
        if not create:
            raise SettingsError(f"no Composer data at {data} yet; run `composer setup`")
        from .job_store import JobStore
        private_folder(data)  # 0700, set through the folder as opened: a link in its place is refused
        touch_private(data, "up.lock")  # the run lock (composer.lifecycle.RUN_LOCK), never made through a link
        JobStore(data, worker=None)
    value = pointer.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"g[0-9]+", value) or not (data / "generations" / value).is_dir():
        raise SettingsError(f"{pointer} does not name a data generation")
    return data / "generations" / value


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(data: Path) -> dict:
    try:
        path = generation_dir(data, create=False) / "config.json"
    except SettingsError:
        return copy.deepcopy(DEFAULTS)
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsError(f"{path} cannot be read: {exc}") from None
    if not isinstance(doc, dict) or doc.get("schema") != CONFIG_SCHEMA:
        raise SettingsError(f"{path} is not a Composer settings file")
    cfg = _merge(DEFAULTS, doc)
    validate(cfg)
    return cfg


def save(data: Path, cfg: dict) -> Path:
    validate(cfg)
    path = generation_dir(data) / "config.json"
    atomic_write(path, json.dumps(cfg, indent=2, sort_keys=True) + "\n", mode=0o600)
    return path


def validate(cfg: dict) -> None:
    p = cfg["provider"]
    if p["kind"] not in ("anthropic", "openai", "none"):
        raise SettingsError("provider must be anthropic, openai or none")
    if p["key"] not in ("stored", "env", "none"):
        raise SettingsError("provider.key must be stored, env or none")
    if p["key_env"] not in WRITER_KEY_NAMES:
        raise SettingsError(f"provider.key_env must be one of {', '.join(WRITER_KEY_NAMES)}")
    c = cfg["checker"]
    if not isinstance(c.get("same"), bool):
        raise SettingsError("checker.same must be true or false")
    if not c["same"]:
        if c["kind"] not in ("anthropic", "openai"):
            raise SettingsError("checker.kind must be anthropic or openai")
        if c["key"] not in ("stored", "env", "none"):
            raise SettingsError("checker.key must be stored, env or none")
        if c["key_env"] != CHECKER_KEY:
            raise SettingsError(f"checker.key_env must be {CHECKER_KEY}")
        if c["kind"] == "openai" and (not c["base_url"] or not c["model"]):
            raise SettingsError("an OpenAI-compatible checker needs base_url and model")
    n = cfg["narration"]
    if n["engine"] not in ("none", "kokoro-onnx", "kokoro-http"):
        raise SettingsError("narration.engine must be none, kokoro-onnx or kokoro-http")
    if n["enabled"] and n["engine"] == "none":
        raise SettingsError("narration is on but names no engine")
    if not isinstance(n["voices"], list) or any(v not in VOICES for v in n["voices"]):
        raise SettingsError(f"narration.voices may only name {', '.join(VOICES)}")
    for key, low, high in (("max_bytes", 200, 200000), ("max_seconds", 30, 3600)):
        if not isinstance(n[key], int) or isinstance(n[key], bool) or not low <= n[key] <= high:
            raise SettingsError(f"narration.{key} must be a whole number from {low} to {high}")
    s = cfg["schedule"]
    if not isinstance(s["enabled"], bool) or not _TIME.match(str(s["time"])):
        raise SettingsError("schedule.time must be HH:MM (24-hour)")
    if s["timezone"] not in ("local", "UTC"):
        raise SettingsError("schedule.timezone must be local or UTC")
    if not isinstance(s["sources"], list) or not s["sources"] or not all(isinstance(x, str) for x in s["sources"]):
        raise SettingsError("schedule.sources must name at least one source")
    if not isinstance(s["lens"], str) or not 1 <= len(s["lens"].strip()) <= 300:
        raise SettingsError("schedule.lens must be 1 to 300 characters")
    if not isinstance(s["insights"], int) or isinstance(s["insights"], bool) or not 3 <= s["insights"] <= 10:
        raise SettingsError("schedule.insights must be from 3 to 10")
    if not isinstance(cfg["extraction"].get("trafilatura"), bool) or set(cfg["extraction"]) != {"trafilatura"}:
        raise SettingsError("extraction.trafilatura must be true or false")
    if not isinstance(cfg["seals"].get("daily"), bool) or set(cfg["seals"]) != {"daily"}:
        raise SettingsError("seals.daily must be true or false")
    port = cfg["server"]["port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise SettingsError("server.port must be from 1024 to 65535")
    keep = cfg["backup"]["keep"]
    if not isinstance(keep, int) or isinstance(keep, bool) or not 1 <= keep <= 100:
        raise SettingsError("backup.keep must be from 1 to 100")


def sources_file(data: Path) -> Path:
    return generation_dir(data, create=False) / "sources.json"


# ------------------------------------------------------------------------------------------------ secrets

def secrets_path(data: Path) -> Path:
    return data / SECRETS


def write_secret(data: Path, name: str, value: str) -> Path:
    """Store one key in <data>/secrets.env (0600; the data folder 0700). Replaces that name only."""
    if name not in KEY_NAMES:
        raise SettingsError(f"unknown key name {name}")
    value = value.strip()
    if not value or any(c in value for c in "\r\n\0") or len(value) > 512:
        raise SettingsError("the key is empty or has characters a key cannot have")
    private_folder(data)
    current = {k: v for k, v in read_secrets(data, strict=True).items() if k != name}  # loose mode: refuse
    current[name] = value
    body = "".join(f"{k}={v}\n" for k, v in sorted(current.items()))
    path = secrets_path(data)
    atomic_write(path, "# Composer's model key. Keep this file private (mode 0600).\n" + body, mode=0o600)
    return path


def secrets_mode_ok(data: Path) -> bool | None:
    """True when the key file is private (no group or other bits), False when it is not, None when absent."""
    path = secrets_path(data)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return False
    return os.name == "nt" or (st.st_mode & 0o077) == 0


def read_secrets(data: Path, *, strict: bool = True) -> dict:
    path = secrets_path(data)
    ok = secrets_mode_ok(data)
    if ok is None:
        return {}
    if not ok:
        if strict:
            raise SettingsError(f"{path} can be read by other users; run: chmod 600 {path}")
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() in KEY_NAMES and value.strip():
            out[name.strip()] = value.strip()
    return out


def key_present(data: Path, cfg: dict, role: str = "provider") -> bool:
    """Whether the writer's key (or, with role "checker", the separate checker's key) is set; never its value."""
    name = cfg[role]["key_env"]
    if os.environ.get(name, "").strip():
        return True
    try:
        return bool(read_secrets(data).get(name))
    except SettingsError:
        return False


def checker_env(cfg: dict) -> dict:
    """The separate checker's settings as the variables providers.checker_from_env reads; {} when the writer's
    model checks the claims. Never the key itself."""
    c = cfg["checker"]
    if c["same"]:
        return {}
    env = {"COMPOSER_CHECKER_PROVIDER": c["kind"]}
    if c["model"]:
        env["COMPOSER_CHECKER_MODEL"] = c["model"]
    if c["kind"] == "openai" and c["base_url"]:
        env["COMPOSER_CHECKER_OPENAI_BASE_URL"] = c["base_url"]
    return env


def provider_env(cfg: dict) -> dict:
    """The provider settings as the variables providers.from_env reads (never the key itself)."""
    p = cfg["provider"]
    env = {}
    if p["kind"] in ("anthropic", "openai"):
        env["COMPOSER_PROVIDER"] = p["kind"]
    if p["model"]:
        env["COMPOSER_MODEL"] = p["model"]
    if p["kind"] == "openai" and p["base_url"]:
        env["COMPOSER_OPENAI_BASE_URL"] = p["base_url"]
    return env
