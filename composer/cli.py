"""The `composer` command.

  composer demo [--site DIR | --page FILE] [--fast]
  composer compose --sources google-ai,deepmind --lens "..." [--insights 5] [--out DIR]
                   [--provider anthropic|openai] [--model ID] [--sources-file FILE] [--keep-sources]
  composer sources list [--sources-file FILE]
  composer sources add --id ID --label LABEL --kind rss-or-atom --url URL [--file FILE]
  composer sources check ID [--sources-file FILE]
  composer serve [--host 127.0.0.1] [--port 8765] [--out DIR]        (0.1: the classic page and form)

  composer setup [--answers FILE | --yes] [--reconfigure PART] [--home DIR] [--data-only]
  composer up [--host 127.0.0.1] [--port N]       the app, its engine, narration and daily brief
  composer doctor [--online] [--parity] [--seals]
  composer backup [--include-secrets] [--out DIR]    composer restore FILE [--include-secrets]
  composer update --from-file RELEASE [--sha256 HEX]    composer rollback [--data-only]
  composer uninstall [--delete-data]

Every install command takes --home DIR (default COMPOSER_HOME or ~/.lensmith-composer) and --data DIR
(default COMPOSER_DATA, or <home>/data).

Exit codes: 0 done, 1 the brief could not be composed, 2 a usage or input problem.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, demo, lenses, page, pipeline, receipts, registry, seal, sources_registry
from .fetch import http_get
from .prompt import DEFAULT_INSIGHTS, INSIGHT_RANGE
from .providers import ProviderError, checker_from_env, from_env


def _registry(args) -> registry.Registry:
    return registry.Registry.load(getattr(args, "sources_file", None))


def cmd_demo(args) -> int:
    ed = demo.load()
    if args.site:
        from . import window
        written = window.write_site(args.site, ed)
        print(f"wrote {len(written)} files to {args.site}  (serve the folder, or open index.html; "
              "it makes no outside request)")
        return 0
    if args.page:
        path = page.write(args.page, ed)
        print(f"wrote {path}  (open it in a browser; it makes no outside request)")
        return 0
    demo.replay(ed, sys.stdout, beat_s=0 if args.fast else 0.6)
    return 0


def _fresh_dir(out: str | None) -> Path:
    if out:
        p = Path(out)
    else:
        p = Path("briefs") / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if p.exists() and any(p.iterdir()):
        raise SystemExit(f"refused: {p} already holds files; name a new folder with --out")
    p.mkdir(parents=True, exist_ok=True)
    return p


def cmd_compose(args) -> int:
    reg = _registry(args)
    ids = [x.strip() for x in args.sources.split(",") if x.strip()]
    sources = reg.pick(ids)
    model = from_env(args.provider, args.model)
    model.ready()
    checker = checker_from_env()  # optional: COMPOSER_CHECKER_PROVIDER and friends
    if checker is not None:
        checker.ready()
    out = _fresh_dir(args.out)

    def log(_kind, text):
        print(f"  {text}", flush=True)

    try:
        lens = lenses.LensRegistry.builtin().get(args.lens.strip())  # a public lens by id
    except lenses.LensError:
        lens = None  # the words themselves are the lens
    if args.reading_level:
        import dataclasses
        lens = dataclasses.replace(lens, reading_level=args.reading_level) if lens else lenses.Lens(
            "ad-hoc", "Your words", "A lens written for this brief.", lenses.validate_text(args.lens),
            args.reading_level)
    try:
        run = pipeline.compose(lens=lens.instruction if lens else args.lens, sources=sources, model=model,
                               count=args.insights, get=http_get, log=log, lens_definition=lens, checker=checker)
    except (pipeline.ComposeError, ProviderError) as exc:
        print(f"could not compose: {exc}", file=sys.stderr)
        return 1
    ed = run["edition"]
    (out / "edition.json").write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "check.json").write_text(json.dumps(run["result"], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    page.write(out / "index.html", ed)
    written = [p.name for p in receipts.write_brief_artifacts(out, run, requested=ids)]
    if args.keep_sources:
        fetched = {sid: {"items": items, "receipt": receipt} for sid, (items, receipt) in run["fetched"].items()}
        (out / "sources-read.json").write_text(json.dumps(fetched, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
    print()
    print(demo.text_report(ed))
    print(f"\nwrote {out}/edition.json, check.json, index.html, {' and '.join(written)}"
          + (" and sources-read.json (feed text: keep it private)" if args.keep_sources else ""))
    return 0


def cmd_sources(args) -> int:
    if args.action == "list":
        for s in _registry(args).entries():
            print(f"{s.id:<16} {s.kind:<12} {s.label}  {s.url}")
        return 0
    if args.action == "add":
        raw = {"id": args.id, "label": args.label, "kind": args.kind, "url": args.url, "max_items": args.max_items}
        if args.kind == "html-index":
            if not (args.allow_host and args.allow_path):
                raise registry.RegistryError("an html-index source needs --allow-host and --allow-path")
            raw["discovery"] = {"allowed_hosts": args.allow_host, "allowed_path_prefixes": args.allow_path,
                                "max_candidates": args.max_candidates}
        entry = registry.parse_entry(raw)
        target = args.file or registry.LOCAL_DEFAULT
        registry.add_to_file(target, entry)
        print(f"added {entry.id} to {target}; try it with: composer sources check {entry.id}")
        return 0
    if args.action == "check":
        from . import adapters
        entry = _registry(args).get(args.id)
        items, receipt = adapters.fetch(entry, http_get)
        print(json.dumps(receipt, indent=1))
        for it in items:
            print(f"  - {it['title']}  {it['url']}")
        return 0 if receipt["status"] == "ok" else 1
    return 2


def cmd_seal(args) -> int:
    try:
        verified, value = seal.verify_check_path(Path(args.path))
    except seal.SealError as exc:
        print(f"composer: {exc}", file=sys.stderr)
        return 2
    if not verified:
        print("seal did not verify", file=sys.stderr)
        return 1
    print("seal verified" + (f": {value}" if value else ""))
    return 0


def cmd_serve(args) -> int:
    from . import home as H, lifecycle, server
    # read-only trust admission of the folder the job store writes in, before anything else
    lifecycle.admit(None, H.given_path(args.out) if args.out else Path.home() / ".lensmith-composer" / "data")
    reg = _registry(args)
    passphrase = server.passphrase_from_env()
    server.check_bind(args.host, passphrase)
    try:
        from_env(args.provider, args.model).ready()  # the key itself is read again on every call
    except ProviderError as exc:
        print(f"note: {exc}. The page will show the recorded brief; Compose will fail until a key is set.", flush=True)
    data_root = Path(args.out) if args.out else Path.home() / ".lensmith-composer" / "data"
    source_path = registry.local_path(args.sources_file) or Path(args.sources_file or registry.LOCAL_DEFAULT)
    app = server.App(reg, lambda: from_env(args.provider, args.model), make_checker=lambda: checker_from_env(),
                     out_dir=Path(args.out) if args.out else None, data_root=data_root, passphrase=passphrase,
                     source_service=sources_registry.SourceService(
                         source_path, packages=sources_registry.PackageService(
                             source_path.parent / "composer-packages.json")),
                     lens_store=lenses.LensStore(source_path.parent / "composer-lenses"))
    server.serve(app, args.host, args.port)
    return 0


def _where(args):
    from . import home as H
    home = H.resolve_home(getattr(args, "home", None))
    return home, H.data_root(home, getattr(args, "data", None))


def cmd_setup(args) -> int:
    from . import installer
    from . import home as H
    home, _ = _where(args)
    # as written, made absolute, never resolved: setup checks the path it is given (a link on it is refused)
    data = H.given_path(args.data) if args.data else None
    import os
    from .providers import test_call
    skip = args.no_test_call or os.environ.get("COMPOSER_NO_TEST_CALL", "").strip() == "1"
    return installer.run(home=home, data=data, answers_file=args.answers, assume_yes=args.yes,
                         reconfigure=args.reconfigure or [], data_only=args.data_only,
                         home_created_by_bootstrap=args.home_created, check_only=args.check_only,
                         test_call=None if skip else test_call)


CHECKER_SETTINGS = ("COMPOSER_CHECKER_PROVIDER", "COMPOSER_CHECKER_MODEL", "COMPOSER_CHECKER_OPENAI_BASE_URL")


def up_env(cfg: dict, environ) -> dict:
    """The model settings `composer up` uses: the environment with the saved settings on top. For the checker the
    saved choice decides alone: with "the same model" set, checker settings inherited from the environment are
    dropped, so they cannot route the checks to another model (or block a brief on a missing checker key)."""
    from . import settings as S
    env = {k: v for k, v in dict(environ).items() if k not in CHECKER_SETTINGS}
    env.update(S.provider_env(cfg))
    env.update(S.checker_env(cfg))  # the separate checker's settings, if any (never a key)
    return env


def _ready(*models) -> None:
    for model in models:
        if model is not None:
            model.ready()


def build_scheduler(data: Path, cfg: dict, env: dict, *, provider=None, model=None, store=None, clock=None,
                    log=print):
    """`composer up`'s scheduler: the daily brief (skipped, with the reason logged, while no model provider key is
    set), the weekly backup and the daily seal re-check of every saved brief."""
    from . import lifecycle
    from .scheduler import Scheduler
    return Scheduler(data, cfg, store, backup=lambda keep: lifecycle.backup(data, keep=keep, tag="weekly"),
                     model_ready=lambda: _ready(from_env(provider, model, env=env),
                                                None if cfg["checker"]["same"] else checker_from_env(env=env)),
                     seal_check=lambda: seal.recheck_saved(data), clock=clock, log=log)


def cmd_up(args) -> int:
    import os
    from . import home as H, lifecycle, narration, server, settings as S
    from .providers import use_key_file
    from .scheduler import chain
    home, data = _where(args)
    container = bool(os.environ.get(H.DATA_ENV)) and not (home / H.MANIFEST).exists()
    if not (data / "current").exists() and not container:
        print(f"composer: no Composer data at {data}; run setup.sh (or `composer setup`) first", file=sys.stderr)
        return 2
    native = home if (home / "app").is_dir() else None
    lifecycle.admit(native, data)  # read-only trust admission, before the lock, recovery or any write
    data.mkdir(parents=True, exist_ok=True)
    lock = lifecycle.hold_run_lock(data)  # noqa: F841  (held for as long as the server runs, taken before recovery)
    lifecycle.recover(native, data)
    S.generation_dir(data)
    lifecycle.migrate_on_start(data)
    lifecycle.check_data_schema(data)
    cfg = S.load(data)
    use_key_file(S.secrets_path(data))
    env = up_env(cfg, os.environ)
    sf = S.sources_file(data)
    reg = registry.Registry.load(str(sf) if sf.exists() else None)
    base = H.runtime_base(home, data)
    narrator = narration.Narrator(cfg["narration"], base)
    sched = build_scheduler(data, cfg, env, provider=args.provider, model=args.model)
    app = server.App(reg, lambda: from_env(args.provider, args.model, env=env), data_root=data, settings=cfg,
                     make_checker=None if cfg["checker"]["same"] else (lambda: checker_from_env(env=env)),
                     source_service=sources_registry.SourceService(
                         sf, packages=sources_registry.PackageService(sf.parent / "packages.json")),
                     lens_store=lenses.LensStore(sf.parent / "lenses"),
                     on_finished=chain(lambda j: narrator.on_finished(j), lambda j: sched.on_finished(j)))
    narrator.attach(app.jobs)
    sched.store = app.jobs
    app.scheduler = sched.start()
    trusted, origin = None, ""
    if os.environ.get("COMPOSER_TRUSTED_PROXY"):
        trusted = server.parse_trusted(os.environ["COMPOSER_TRUSTED_PROXY"])
        origin = server.check_public_origin(os.environ.get("COMPOSER_PUBLIC_ORIGIN", ""))
    passphrase = server.passphrase_from_env()
    app.passphrase = passphrase
    try:
        from_env(args.provider, args.model, env=env).ready()
    except ProviderError as exc:
        print(f"note: {exc} Until then the page shows the recorded brief.", flush=True)
    print(f"narration: {'on (' + cfg['narration']['engine'] + ')' if narrator.enabled else 'off (text-only)'}; "
          f"daily brief: {'at ' + cfg['schedule']['time'] if cfg['schedule']['enabled'] else 'off'}", flush=True)
    server.serve(app, args.host, args.port or cfg["server"]["port"], trusted=trusted, public_origin=origin)
    return 0


def cmd_doctor(args) -> int:
    from . import doctor
    home, data = _where(args)
    return doctor.run(home, data, online=args.online, parity=args.parity, seals=args.seals,
                      integrity_only=args.integrity_only)


def cmd_backup(args) -> int:
    from . import lifecycle
    _, data = _where(args)
    path = lifecycle.backup(data, include_secrets=args.include_secrets, out_dir=Path(args.out) if args.out else None)
    print(f"wrote {path}" + ("  (it includes your key: keep it private)" if args.include_secrets else
                             "  (your key is not in it)"))
    print("Copy it somewhere else too: a backup that only lives next to your data is lost with it.")
    return 0


def cmd_restore(args) -> int:
    from . import lifecycle
    _, data = _where(args)
    result = lifecycle.restore(data, Path(args.file), include_secrets=args.include_secrets)
    print(f"restored {result['restored_files']} files. What was there before is backed up at "
          f"{result['safety_backup']} and kept at {result['replaced_kept_at']}.")
    return 0


def cmd_update(args) -> int:
    from . import lifecycle
    home, data = _where(args)
    result = lifecycle.update(home, data, Path(args.from_file), sha256=args.sha256)
    print(f"updated {result['from']} -> {result['to']}"
          + (" (your data was migrated as a copy; the original is kept)" if result["data_migrated"] else ""))
    print("To go back: composer rollback")
    return 0


def cmd_rollback(args) -> int:
    from . import lifecycle
    home, data = _where(args)
    result = lifecycle.rollback(home, data, data_only=args.data_only)
    if result["export_directory"]:
        print(f"briefs made since the update were exported to {result['export_directory']}: "
              + (", ".join(result["exported_jobs"]) or "none"))
    print("rolled back" + (f" to {result['code']}" if result["code"] else " the data (now start the previous image)"))
    if result.get("removed_version"):
        print(f"removed version {result['removed_version']} (to install it again, update to it again)")
    return 0


def cmd_uninstall(args) -> int:
    from . import home as H, lifecycle
    home, data = _where(args)

    def confirm(question: str) -> bool:
        if args.yes:
            return True
        if not sys.stdin.isatty():
            return False
        return input(question).strip() == "DELETE"

    if args.delete_data:
        print("Before you delete your data, you can keep a copy: composer backup --out <a folder outside "
              f"{home}>")
    result = lifecycle.uninstall(home, data, delete_data=args.delete_data, confirm=confirm)
    print("removed: " + (", ".join(result["removed"]) or "nothing"))
    if result["kept_data"]:
        print(f"kept your data: {result['kept_data']} (remove it with `composer uninstall --delete-data`, or "
              "run setup again to pick it up)")
    for path in result["reused_untouched"]:
        print(f"left untouched (reused read-only): {path}")
    for name in result["not_ours_left_alone"]:
        print(f"left alone (not created by Composer): {home / name}")
    print("If you added the alias line to your shell profile, remove it yourself.")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="composer", description="Read feeds, write a brief through your lens, "
                                                             "check every claim against its source.")
    p.add_argument("--version", action="version", version=f"composer {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="replay a recorded brief (no key, no network)")
    d.add_argument("--page", metavar="FILE", help="write the replay as a one-file web page instead")
    d.add_argument("--site", metavar="DIR", help="write the animated replay as a small static site instead")
    d.add_argument("--fast", action="store_true", help="no pauses between steps")
    d.set_defaults(func=cmd_demo)

    c = sub.add_parser("compose", help="compose a new brief (needs an API key)")
    c.add_argument("--sources", required=True, help="comma-separated source ids, e.g. google-ai,deepmind")
    c.add_argument("--lens", required=True, help="what to look for, in your words (up to 300 characters), or "
                   "a public lens id: system-improvements, second-order-effects, raised-eyebrow")
    c.add_argument("--insights", type=int, default=DEFAULT_INSIGHTS,
                   choices=list(INSIGHT_RANGE), help="how many insights (default 5)")
    c.add_argument("--reading-level", choices=list(lenses.READING_LEVELS),
                   help="plain, standard or technical (default: the lens's own, else standard)")
    c.add_argument("--out", help="a new folder for the brief (default briefs/<time>)")
    c.add_argument("--provider", choices=["anthropic", "openai"], help="default: COMPOSER_PROVIDER or anthropic")
    c.add_argument("--model", help="default: COMPOSER_MODEL, or claude-sonnet-5-5 for anthropic")
    c.add_argument("--sources-file", help="your own sources file (default ./composer-sources.json)")
    c.add_argument("--keep-sources", action="store_true",
                   help="also save the feed text that was read (for debugging; do not publish it)")
    c.set_defaults(func=cmd_compose)

    s = sub.add_parser("sources", help="list, add or test sources")
    s.add_argument("action", choices=["list", "add", "check"])
    s.add_argument("id", nargs="?", help="for check: the source id")
    s.add_argument("--sources-file", help="your own sources file (default ./composer-sources.json)")
    s.add_argument("--id", dest="new_id", help=argparse.SUPPRESS)
    s.add_argument("--label")
    s.add_argument("--kind", choices=list(registry.KINDS), default="rss-or-atom")
    s.add_argument("--url")
    s.add_argument("--max-items", type=int, default=5)
    s.add_argument("--allow-host", action="append", help="html-index: a host articles may be on (repeatable)")
    s.add_argument("--allow-path", action="append", help="html-index: a path prefix articles start with (repeatable)")
    s.add_argument("--max-candidates", type=int, default=20)
    s.add_argument("--file", help="for add: the file to add to (default ./composer-sources.json)")
    s.set_defaults(func=cmd_sources)

    q = sub.add_parser("seal", help="re-verify a saved claim-evidence seal without a model call")
    q.add_argument("action", choices=["verify"])
    q.add_argument("path", help="a check.json file or brief directory")
    q.set_defaults(func=cmd_seal)

    v = sub.add_parser("serve", help="run the web page with a compose form (needs an API key)")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--out", help="folder to save the latest brief in")
    v.add_argument("--provider", choices=["anthropic", "openai"])
    v.add_argument("--model")
    v.add_argument("--sources-file")
    v.set_defaults(func=cmd_serve)

    def where(sp):
        sp.add_argument("--home", help="the app folder (default COMPOSER_HOME or ~/.lensmith-composer)")
        sp.add_argument("--data", help="the data folder (default COMPOSER_DATA or <home>/data)")
        return sp

    st = where(sub.add_parser("setup", help="set Composer up: provider and key, sources, narration, schedule, port"))
    st.add_argument("--answers", metavar="FILE", help="answers file (.toml or .json): no questions")
    st.add_argument("--yes", action="store_true", help="no questions: every default")
    st.add_argument("--reconfigure", action="append", metavar="PART",
                    help="ask one part again: provider, checker, sources, parser, narration, schedule or port")
    st.add_argument("--data-only", action="store_true", help="settings and key in the data folder only (container)")
    st.add_argument("--home-created", action="store_true", help=argparse.SUPPRESS)
    st.add_argument("--check-only", action="store_true", help="run every check, ask nothing, write nothing")
    st.add_argument("--no-test-call", action="store_true",
                    help="skip the one tiny model call that checks each key and model id (also COMPOSER_NO_TEST_CALL=1)")
    st.set_defaults(func=cmd_setup)

    u = where(sub.add_parser("up", help="run the app (page, engine, narration, daily brief)"))
    u.add_argument("--host", default="127.0.0.1")
    u.add_argument("--port", type=int, help="default: the port chosen at setup (8765)")
    u.add_argument("--provider", choices=["anthropic", "openai"], help=argparse.SUPPRESS)
    u.add_argument("--model", help=argparse.SUPPRESS)
    u.set_defaults(func=cmd_up)

    dr = where(sub.add_parser("doctor", help="check this install, one line per check"))
    dr.add_argument("--online", action="store_true", help="also call the model, read each source, render a sentence")
    dr.add_argument("--parity", action="store_true", help="also run a fixture brief through the real routes")
    dr.add_argument("--seals", action="store_true", help="also re-verify the seal of every saved brief")
    dr.add_argument("--integrity-only", action="store_true", help=argparse.SUPPRESS)
    dr.set_defaults(func=cmd_doctor)

    b = where(sub.add_parser("backup", help="archive your current data (not your key unless asked)"))
    b.add_argument("--include-secrets", action="store_true")
    b.add_argument("--out", metavar="DIR", help="default <data>/backups")
    b.set_defaults(func=cmd_backup)

    rs = where(sub.add_parser("restore", help="bring a backup back (checked first; what is there now is kept)"))
    rs.add_argument("file")
    rs.add_argument("--include-secrets", action="store_true")
    rs.set_defaults(func=cmd_restore)

    up = where(sub.add_parser("update", help="install a release file as a checked, undoable update"))
    up.add_argument("--from-file", required=True, metavar="RELEASE")
    up.add_argument("--sha256", help="the release file's SHA-256 (or put SHA256SUMS next to it)")
    up.set_defaults(func=cmd_update)

    rb = where(sub.add_parser("rollback", help="go back to the version and data before the last update"))
    rb.add_argument("--data-only", action="store_true", help="only point the data back (Docker)")
    rb.set_defaults(func=cmd_rollback)

    un = where(sub.add_parser("uninstall", help="remove what setup created; your data only with --delete-data"))
    un.add_argument("--delete-data", action="store_true", help="also delete your data folder (asks first)")
    un.add_argument("--yes", action="store_true", help="do not ask before deleting data")
    un.set_defaults(func=cmd_uninstall)
    return p


def no_group_write_umask() -> None:
    """Everything Composer writes, and everything the programs it starts write (venv, pip, Python's bytecode cache,
    the narration runtime), is made without a group or other write bit, whatever umask it was started with (002 is
    common): the trust contract refuses such folders and files in the app and data folders (home.check_tree)."""
    from .home import no_group_write
    no_group_write().__enter__()  # for the whole command: never undone


def main(argv: list[str] | None = None) -> int:
    no_group_write_umask()
    args = parser().parse_args(argv)
    if args.command == "sources":
        if args.action == "add":
            args.id = args.new_id or args.id
            missing = [n for n, v in (("--id", args.id), ("--label", args.label), ("--url", args.url)) if not v]
            if missing:
                print(f"composer sources add needs {', '.join(missing)}", file=sys.stderr)
                return 2
        elif args.action == "check" and not args.id:
            print("composer sources check needs a source id", file=sys.stderr)
            return 2
    from .answers import AnswersError
    from .home import HomeError
    from .installer import SetupError
    from .lifecycle import LifecycleError
    from .settings import SettingsError
    try:
        return args.func(args)
    except (registry.RegistryError, ProviderError, ValueError, HomeError, SetupError, LifecycleError,
            SettingsError, AnswersError) as exc:
        print(f"composer: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nstopped; nothing more was written", file=sys.stderr)
        return 130
