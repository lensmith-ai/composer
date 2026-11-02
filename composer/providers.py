"""The model layer: bring your own API key.

Two providers, both plain HTTPS calls with the standard library:

  anthropic   the Anthropic Messages API (the default). Key from ANTHROPIC_API_KEY.
  openai      any OpenAI-compatible chat-completions endpoint (OpenAI, OpenRouter, a local
              server). Key from OPENAI_API_KEY, endpoint from COMPOSER_OPENAI_BASE_URL.

Settings (environment variables; the command line can override the first two):

  COMPOSER_PROVIDER         anthropic (default) or openai
  COMPOSER_MODEL            the model id; default claude-sonnet-5-5 for anthropic.
                            The openai provider has no default model: set one.
  COMPOSER_OPENAI_BASE_URL  for openai, e.g. https://api.openai.com/v1
  COMPOSER_MAX_TOKENS       the reply ceiling per call (default 16000)

An optional separate checker (the model claim-seal asks whether each source supports each claim, and whether the
connection holds) has its own settings; without them the writer's model checks its own brief:

  COMPOSER_CHECKER_PROVIDER         anthropic or openai
  COMPOSER_CHECKER_MODEL            the checker's model id (default claude-sonnet-5-5 for anthropic)
  COMPOSER_CHECKER_OPENAI_BASE_URL  for an openai checker
  COMPOSER_CHECKER_API_KEY          the checker's key (or in the 0600 key file under that name)

A provider is a callable `provider(prompt, timeout=None) -> reply text`. That is the shape
claim-seal expects for its judge, so the same object can write the brief and check it. The reply
is a str that also carries `.model` (the model that answered) and `.usage` (token counts, when
the endpoint reports them).

The key is read from the environment (or the 0600 key file `composer setup` writes) at call time. It is never stored on the object, never
logged, and never written to any output file. Redirects are refused on any call that carries a
key, and a plain http:// endpoint is refused unless it is this machine (127.0.0.1, ::1,
localhost), for a local model server.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

DEFAULT_PROVIDER = "anthropic"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# Models that accept the server-side refusal fallback ("fallbacks": "default"). On these, a
# request a safety classifier declines is retried by the API on a model chosen for that case,
# instead of coming back empty. Set COMPOSER_ANTHROPIC_FALLBACK=off to turn it off.
FALLBACK_MODELS = frozenset({"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"
DEFAULT_MAX_TOKENS = 16000
DEFAULT_TIMEOUT_S = 240
REPLY_CEILING = 8 * 1024 * 1024
LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


class ProviderError(RuntimeError):
    """The endpoint could not be reached, refused the call, or answered with something unusable."""


class MissingKey(ProviderError):
    """No key is set for the model that would be called. Its text is the plain sentence the page, `composer
    compose`, `composer doctor` and the scheduler all show."""


NO_KEY_MESSAGE = "Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider."
NO_CHECKER_KEY_MESSAGE = "Composer needs the checker model's key to check a brief. Run ./setup.sh --reconfigure checker."


class Reply(str):
    """Reply text, plus the model that answered and the token counts the endpoint reported."""

    def __new__(cls, text: str, model: str | None = None, usage: dict | None = None):
        obj = super().__new__(cls, text)
        obj.model = model
        obj.usage = dict(usage or {})
        return obj


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError(f"the endpoint answered with a redirect ({code}); set the final URL directly")


_OPENER = urllib.request.build_opener(_NoRedirect())


def urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, bytes]:
    """POST `body` to `url`; (status, reply bytes). HTTP errors return their status and body."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            data = resp.read(REPLY_CEILING + 1)
            status = resp.status
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(64 * 1024)
    except ProviderError:
        raise
    except (urllib.error.URLError, OSError) as exc:
        raise ProviderError(f"could not reach the endpoint: {type(exc).__name__}") from None
    if len(data) > REPLY_CEILING:
        raise ProviderError("the reply is over 8 MiB; refused unread")
    return status, data


def checked_endpoint(url: str) -> str:
    """The URL a key may be sent to, or ProviderError. Errors name only scheme and host."""
    p = urllib.parse.urlsplit(url or "")
    if p.username or p.password:
        raise ProviderError("the endpoint URL must not carry a user:password part")
    if p.scheme == "https" and p.hostname:
        return url
    if p.scheme == "http" and p.hostname in LOOPBACK:
        return url
    raise ProviderError(f"refused endpoint {p.scheme or '?'}://{p.hostname or '?'}: use https, "
                        "or http only to this machine")


_BEARER = re.compile(r"(?i)\b(bearer)\s+\S+")


_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}")


def _token_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 10**12 else None


# The reflection policy. A reply "holds the key" when it contains the whole key or ANY run of KEY_FRAGMENT (12) or
# more characters copied from it: its start, its end or anywhere inside. A key's public, fixed prefix (for example
# "sk-ant-api03-") is not by itself a fragment; a run that reaches one character past it is. This is checked on the
# text exactly as the endpoint sent it: it does not catch a key the endpoint has re-encoded (reversed, spaced out,
# base64 and so on), and it does not claim to.
KEY_FRAGMENT = 12
_PUBLIC_KEY_PREFIX = re.compile(r"^(?:sk-ant-[a-z]+\d*-|sk-proj-|sk-or-v\d+-|sk-)")


def holds_key(text: str, key: str) -> bool:
    """True when text holds the key, or a run of KEY_FRAGMENT or more of its characters (see the policy above)."""
    if not key or not isinstance(text, str) or not text:
        return False
    if key in text:
        return True
    if len(key) < KEY_FRAGMENT:
        return False
    public = len(_PUBLIC_KEY_PREFIX.match(key).group(0)) if _PUBLIC_KEY_PREFIX.match(key) else 0
    for start in range(len(key) - KEY_FRAGMENT + 1):
        if start + KEY_FRAGMENT <= public:
            continue  # wholly inside the published prefix every key of this kind starts with
        if key[start:start + KEY_FRAGMENT] in text:
            return True
    return False


def _checked_reply(text: str, reported_model, usage: dict, configured_model: str, key: str) -> Reply:
    """A success reply, made safe to record: what the endpoint says about itself (the model id, the token counts)
    is kept only when it has the right shape and does not hold the key the call was made with (holds_key); otherwise
    the configured model id stands in and the count is unknown. A reply whose text holds the key is refused, so the
    key, or a long piece of it, never reaches a brief, its receipts or anything served."""
    if holds_key(text, key):
        raise ProviderError("the reply contains the key the call was made with, or a long piece of it; it was not "
                            "used (check the endpoint: it echoes what it is sent)")
    model = reported_model if (isinstance(reported_model, str) and _MODEL_ID.fullmatch(reported_model)
                               and not holds_key(reported_model, key)) else configured_model
    return Reply(text, model=model, usage={"input_tokens": _token_count(usage.get("input_tokens")),
                                           "output_tokens": _token_count(usage.get("output_tokens"))})


def _error_text(status: int, data: bytes, secret: str = "") -> str:
    """The endpoint's error, short. An endpoint that echoes the key back (some proxies do) does
    not get it printed or sent on: the key, and anything after "Bearer", is replaced."""
    try:
        err = json.loads(data.decode("utf-8")).get("error")
        if isinstance(err, dict):
            def scrub(value) -> str:  # before any cut, so a key at the cut cannot leave a prefix
                text = _BEARER.sub(r"\1 [hidden]", str(value or ""))
                return text.replace(secret, "[your key]") if secret else text
            kind = scrub(err.get("type") or err.get("code") or "error")[:60]
            msg = scrub(err.get("message"))[:200]
            return f"HTTP {status} {kind}: {msg}"
    except Exception:
        pass
    return f"HTTP {status}"


_KEY_FILE = None  # set by `composer up` to <data>/secrets.env; read at call time, never copied into os.environ


def use_key_file(path) -> None:
    """Also look for keys in this file (NAME=value lines, mode 0600) when the environment has none."""
    global _KEY_FILE
    _KEY_FILE = path


def _key_from_file(env_name: str) -> str:
    if _KEY_FILE is None:
        return ""
    from pathlib import Path
    from .settings import SettingsError, read_secrets
    try:
        return read_secrets(Path(_KEY_FILE).parent).get(env_name, "")
    except (OSError, SettingsError) as exc:
        raise ProviderError(str(exc)) from None


def _key(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip() or _key_from_file(env_name)
    if not value:
        raise MissingKey(NO_CHECKER_KEY_MESSAGE if env_name == "COMPOSER_CHECKER_API_KEY" else NO_KEY_MESSAGE)
    return value


@dataclass
class Anthropic:
    """The Anthropic Messages API. One user message per call; the reply's text blocks joined."""

    model: str = DEFAULT_ANTHROPIC_MODEL
    api_key_env: str = "ANTHROPIC_API_KEY"
    url: str = ANTHROPIC_URL
    max_tokens: int = DEFAULT_MAX_TOKENS
    fallback: bool = True
    transport: object = field(default=urllib_transport, repr=False)

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def ready(self) -> None:
        """Raise ProviderError now if the key or endpoint is missing, before any feed is read."""
        checked_endpoint(self.url)
        _key(self.api_key_env)

    def request_body(self, prompt: str) -> dict:
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if self.fallback and self.model in FALLBACK_MODELS:
            body["fallbacks"] = "default"
        return body

    def __call__(self, prompt: str, timeout: float | None = None) -> Reply:
        return self.call_with_key(prompt, _key(self.api_key_env), timeout)

    def call_with_key(self, prompt: str, key: str, timeout: float | None = None) -> Reply:
        """One call with a key the caller holds (setup's test call, before the key is stored); never kept."""
        url = checked_endpoint(self.url)
        body = self.request_body(prompt)
        headers = {"content-type": "application/json", "anthropic-version": ANTHROPIC_VERSION,
                   "x-api-key": key}
        if "fallbacks" in body:
            headers["anthropic-beta"] = FALLBACK_BETA
        status, data = self.transport(url, headers, json.dumps(body).encode("utf-8"),
                                      timeout or DEFAULT_TIMEOUT_S)
        if status != 200:
            raise ProviderError(_error_text(status, data, key))
        try:
            doc = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderError("the reply is not JSON") from None
        stop = doc.get("stop_reason")
        if stop == "refusal":
            raise ProviderError("the model declined this request (stop_reason: refusal)")
        text = "".join(b.get("text", "") for b in doc.get("content") or []
                       if isinstance(b, dict) and b.get("type") == "text")
        if stop == "max_tokens":
            raise ProviderError(f"the reply hit the {self.max_tokens}-token ceiling before it finished; "
                                "raise COMPOSER_MAX_TOKENS")
        if not text.strip():
            raise ProviderError("the reply has no text")
        u = doc.get("usage") if isinstance(doc.get("usage"), dict) else {}
        usage = {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens")}
        return _checked_reply(text, doc.get("model"), usage, self.model, key)


@dataclass
class OpenAICompatible:
    """Any endpoint that speaks the OpenAI chat-completions shape."""

    model: str
    base_url: str
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = DEFAULT_MAX_TOKENS
    transport: object = field(default=urllib_transport, repr=False)

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def ready(self) -> None:
        """Raise ProviderError now if the key or endpoint is missing, before any feed is read."""
        checked_endpoint(self.base_url)
        _key(self.api_key_env)

    def __call__(self, prompt: str, timeout: float | None = None) -> Reply:
        return self.call_with_key(prompt, _key(self.api_key_env), timeout)

    def call_with_key(self, prompt: str, key: str, timeout: float | None = None) -> Reply:
        """One call with a key the caller holds (setup's test call, before the key is stored); never kept."""
        base = checked_endpoint(self.base_url).rstrip("/")
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
        status, data = self.transport(base + "/chat/completions", headers, json.dumps(body).encode("utf-8"),
                                      timeout or DEFAULT_TIMEOUT_S)
        if status != 200:
            raise ProviderError(_error_text(status, data, key))
        try:
            doc = json.loads(data.decode("utf-8"))
            choice = doc["choices"][0]
            text = choice["message"]["content"] or ""
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise ProviderError("the reply is not a chat-completions answer") from None
        if choice.get("finish_reason") == "length":
            raise ProviderError(f"the reply hit the {self.max_tokens}-token ceiling before it finished; "
                                "raise COMPOSER_MAX_TOKENS")
        if not text.strip():
            raise ProviderError("the reply has no text")
        u = doc.get("usage") if isinstance(doc.get("usage"), dict) else {}
        usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")}
        return _checked_reply(text, doc.get("model"), usage, self.model, key)


def _max_tokens(env) -> int:
    raw = env.get("COMPOSER_MAX_TOKENS", "")
    if not raw:
        return DEFAULT_MAX_TOKENS
    try:
        value = int(raw)
    except ValueError:
        raise ProviderError("COMPOSER_MAX_TOKENS must be a whole number") from None
    if not 256 <= value <= 128000:
        raise ProviderError("COMPOSER_MAX_TOKENS must be from 256 to 128000")
    return value


def from_env(provider: str | None = None, model: str | None = None, *, env=None, transport=None):
    """Build the provider the settings name. Nothing is called and no key is read here."""
    env = os.environ if env is None else env
    kind = (provider or env.get("COMPOSER_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    model = (model or env.get("COMPOSER_MODEL") or "").strip()
    extra = {"transport": transport} if transport is not None else {}
    if kind == "anthropic":
        return Anthropic(model=model or DEFAULT_ANTHROPIC_MODEL, max_tokens=_max_tokens(env),
                         fallback=env.get("COMPOSER_ANTHROPIC_FALLBACK", "on").lower() != "off", **extra)
    if kind == "openai":
        base = env.get("COMPOSER_OPENAI_BASE_URL", "").strip()
        if not base:
            raise ProviderError("set COMPOSER_OPENAI_BASE_URL for the openai provider, "
                                "e.g. https://api.openai.com/v1")
        if not model:
            raise ProviderError("set COMPOSER_MODEL (or --model) for the openai provider")
        checked_endpoint(base)
        return OpenAICompatible(model=model, base_url=base, max_tokens=_max_tokens(env), **extra)
    raise ProviderError(f"unknown provider {kind[:20]!r}: use anthropic or openai")


TEST_CALL_TOKENS = 16
TEST_CALL_TIMEOUT_S = 15


def test_call(kind: str, model: str, base_url: str, key: str, *, transport=None) -> tuple[bool, str]:
    """Setup's one tiny call: does this key work with this model at this endpoint? (ok, a plain sentence).

    At most TEST_CALL_TOKENS tokens back and TEST_CALL_TIMEOUT_S seconds per network wait. It goes through no
    counter, so it is in no brief's calls or costs. The sentence never holds the key."""
    extra = {"transport": transport} if transport is not None else {}
    try:
        if kind == "anthropic":
            provider = Anthropic(model=model or DEFAULT_ANTHROPIC_MODEL, max_tokens=TEST_CALL_TOKENS, fallback=False,
                                 **extra)
        else:
            provider = OpenAICompatible(model=model, base_url=base_url, max_tokens=TEST_CALL_TOKENS, **extra)
        reply = provider.call_with_key("Reply with the single word OK.", key, TEST_CALL_TIMEOUT_S)
    except ProviderError as exc:
        text = str(exc).replace(key, "[your key]") if key else str(exc)
        low = text.lower()
        if "token ceiling" in low or "has no text" in low:
            return True, "the key and the model id work (the endpoint answered)"
        if low.startswith(("could not reach", "refused endpoint", "the endpoint answered with a redirect")):
            return False, f"the endpoint could not be reached ({text[:160]})"
        if re.search(r"http (401|403)\b", low) or "authentication" in low or "api key" in low:
            return False, f"the key was refused ({text[:160]})"
        if re.search(r"http 404\b", low) or ("model" in low and re.search(r"not.?found|does not exist|invalid", low)):
            return False, f"the model id was not found ({text[:160]})"
        return False, f"the test call failed ({text[:160]})"
    # name the model that was asked for, never the endpoint's own `model` field: a hostile or broken endpoint could
    # echo the key there, and this sentence is printed
    said = f"the key and the model id work ({model or DEFAULT_ANTHROPIC_MODEL} answered)"
    return True, said.replace(key, "[your key]") if key else said


CHECKER_KEY_ENV = "COMPOSER_CHECKER_API_KEY"


def checker_from_env(*, env=None, transport=None):
    """The separate checker the settings name, or None when the writer's model checks the claims. Nothing is called
    and no key is read here; its key is COMPOSER_CHECKER_API_KEY, never the writer's."""
    env = os.environ if env is None else env
    kind = (env.get("COMPOSER_CHECKER_PROVIDER") or "").strip().lower()
    if not kind:
        return None
    model = (env.get("COMPOSER_CHECKER_MODEL") or "").strip()
    extra = {"transport": transport} if transport is not None else {}
    if kind == "anthropic":
        return Anthropic(model=model or DEFAULT_ANTHROPIC_MODEL, api_key_env=CHECKER_KEY_ENV,
                         max_tokens=_max_tokens(env),
                         fallback=env.get("COMPOSER_ANTHROPIC_FALLBACK", "on").lower() != "off", **extra)
    if kind == "openai":
        base = (env.get("COMPOSER_CHECKER_OPENAI_BASE_URL") or "").strip()
        if not base or not model:
            raise ProviderError("an openai checker needs COMPOSER_CHECKER_OPENAI_BASE_URL and COMPOSER_CHECKER_MODEL")
        checked_endpoint(base)
        return OpenAICompatible(model=model, base_url=base, api_key_env=CHECKER_KEY_ENV,
                                max_tokens=_max_tokens(env), **extra)
    raise ProviderError(f"unknown checker provider {kind[:20]!r}: use anthropic or openai")


class Counted:
    """Wraps a provider and counts its calls and reported tokens. Used for the cost line."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.failed = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.tokens_known = True
        self.models: list[str] = []
        self.per_call: list[dict] = []
        self._lock = threading.Lock()  # claim-seal checks claims two at a time

    @property
    def name(self):
        return getattr(self.inner, "name", None)

    def __call__(self, prompt: str, timeout: float | None = None):
        with self._lock:
            self.calls += 1
            number = self.calls
        started = time.monotonic()
        try:
            reply = self.inner(prompt, timeout=timeout)
        except Exception as exc:
            with self._lock:
                self.failed += 1
                self.per_call.append({"call": number, "ok": False, "error": type(exc).__name__,
                                      "seconds": round(time.monotonic() - started, 1)})
            raise
        usage = getattr(reply, "usage", {}) or {}
        usage = {k: _token_count(usage.get(k)) for k in ("input_tokens", "output_tokens")} if isinstance(usage, dict) \
            else {}
        model = getattr(reply, "model", None)
        if not (isinstance(model, str) and _MODEL_ID.fullmatch(model)):
            model = None  # only a well-formed model id is recorded (the providers already check it against the key)
        with self._lock:
            self.per_call.append({"call": number, "ok": True, "model": model,
                                  "input_tokens": usage.get("input_tokens"),
                                  "output_tokens": usage.get("output_tokens"),
                                  "seconds": round(time.monotonic() - started, 1)})
            if isinstance(usage.get("input_tokens"), int) and isinstance(usage.get("output_tokens"), int):
                self.input_tokens += usage["input_tokens"]
                self.output_tokens += usage["output_tokens"]
            else:
                self.tokens_known = False
            if model and model not in self.models:
                self.models.append(model)
        return reply

    def summary(self) -> dict:
        return {"calls": self.calls, "failed_calls": self.failed, "models": list(self.models),
                "input_tokens": self.input_tokens if self.tokens_known else None,
                "output_tokens": self.output_tokens if self.tokens_known else None,
                "per_call": sorted((dict(c) for c in self.per_call), key=lambda c: c["call"])}

    def receipt(self) -> dict:
        """Provider-reported usage only. No prices or inferred token counts are added."""
        return {"provider": self.name, **self.summary()}
