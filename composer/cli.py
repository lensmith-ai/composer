"""The `composer` command.

  composer demo [--site DIR | --page FILE] [--fast]
  composer compose --sources google-ai,deepmind --lens "..." [--insights 5] [--out DIR]
                   [--provider anthropic|openai] [--model ID] [--sources-file FILE] [--keep-sources]
  composer sources list [--sources-file FILE]
  composer sources add --id ID --label LABEL --kind rss-or-atom --url URL [--file FILE]
  composer sources check ID [--sources-file FILE]
  composer serve [--host 127.0.0.1] [--port 8765] [--out DIR]

Exit codes: 0 done, 1 the brief could not be composed, 2 a usage or input problem.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, demo, page, pipeline, registry
from .fetch import http_get
from .prompt import DEFAULT_INSIGHTS, INSIGHT_RANGE
from .providers import ProviderError, from_env


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
    out = _fresh_dir(args.out)

    def log(_kind, text):
        print(f"  {text}", flush=True)

    try:
        run = pipeline.compose(lens=args.lens, sources=sources, model=model, count=args.insights, get=http_get,
                               log=log)
    except (pipeline.ComposeError, ProviderError) as exc:
        print(f"could not compose: {exc}", file=sys.stderr)
        return 1
    ed = run["edition"]
    (out / "edition.json").write_text(json.dumps(ed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "check.json").write_text(json.dumps(run["result"], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    page.write(out / "index.html", ed)
    if args.keep_sources:
        fetched = {sid: {"items": items, "receipt": receipt} for sid, (items, receipt) in run["fetched"].items()}
        (out / "sources-read.json").write_text(json.dumps(fetched, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
    print()
    print(demo.text_report(ed))
    print(f"\nwrote {out}/edition.json, check.json and index.html"
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


def cmd_serve(args) -> int:
    from . import server
    reg = _registry(args)
    passphrase = server.passphrase_from_env()
    server.check_bind(args.host, passphrase)
    try:
        from_env(args.provider, args.model).ready()  # the key itself is read again on every call
    except ProviderError as exc:
        print(f"note: {exc}. The page will show the recorded brief; Compose will fail until a key is set.", flush=True)
    data_root = Path(args.out) if args.out else Path.home() / ".lensmith-composer" / "data"
    app = server.App(reg, lambda: from_env(args.provider, args.model),
                     out_dir=Path(args.out) if args.out else None, data_root=data_root, passphrase=passphrase)
    server.serve(app, args.host, args.port)
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
    c.add_argument("--lens", required=True, help="what to look for, in your words (up to 300 characters)")
    c.add_argument("--insights", type=int, default=DEFAULT_INSIGHTS,
                   choices=list(INSIGHT_RANGE), help="how many insights (default 5)")
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

    v = sub.add_parser("serve", help="run the web page with a compose form (needs an API key)")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--out", help="folder to save the latest brief in")
    v.add_argument("--provider", choices=["anthropic", "openai"])
    v.add_argument("--model")
    v.add_argument("--sources-file")
    v.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
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
    try:
        return args.func(args)
    except (registry.RegistryError, ProviderError, ValueError) as exc:
        print(f"composer: {exc}", file=sys.stderr)
        return 2
