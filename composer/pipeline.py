"""One brief, start to finish: read, screen, write, check, seal.

    1 read     each chosen source through its adapter (composer.adapters); a feed entry with no real text (empty,
               "TBD", "coming soon") is read from its own page, or left out and the receipt says why
               (composer.adapters.thin), so filler text is never written up as news
    2 screen   every string cleaned (composer.sanitize); counts kept per source
    3 write    one model call under your lens (composer.prompt); one retry if the answer
               cannot be used; then the quote rule (composer.quotes): at most 25 words per quoted
               run copied from an article, at most 2 quotes per article, never its opening
               sentence. A brief that breaks it is sent back once; if that does not fix it, the
               parts that break it are dropped and the receipt says so
    4 check    claim-seal: every cited title must exist (plain code), then one model call per
               claim (each insight, and the connection) to judge support, sentence by sentence
    5 seal     claim-seal's SHA-256 chain over the claim-evidence rows

Model calls per brief: 1 to write, plus 1 per insight, plus 1 for the connection. With the
default 5 insights that is 7. A retry, a quote-rule repair, or a brief with fewer items changes the
count; the edition records the real number. With a separate checker model (optional), the writer makes the
write call(s) and the checker makes every check call (each insight and the connection); the
edition and the receipt record the two separately.

What is written to disk (composer.cli decides where): the edition (our words, the cited titles
and links, the verdicts and the seal; never the articles' text) and the full claim-seal result.
The feed text itself stays in memory unless you ask for it with --keep-sources.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from . import adapters, lenses, prompt as P, quotes as Q
from .fetch import http_get
from .providers import Counted

SCHEMA = "composer-edition/v1"
STATE_LABELS = {"supported": "supported", "partial": "partly supported", "unsupported": "not supported",
                "unchecked": "not checked"}


class ComposeError(RuntimeError):
    """The brief could not be written (no source gave material, or the model's answer was unusable)."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_sources(sources: list, get=http_get, log=lambda *_: None) -> dict:
    """source id -> (items, receipt)."""
    out = {}
    for s in sources:
        log("source.started", f"reading {s.label}")
        items, receipt = adapters.fetch(s, get, enrich=True)
        out[s.id] = (items, receipt)
        state = f"{receipt['items']} items (ok)" if receipt["status"] == "ok" else f"failed: {receipt.get('error')}"
        thin = receipt.get("thin") or {}
        if thin.get("enriched"):
            state += f" · {thin['enriched']} read from the item's own page (the feed had no real text)"
        if thin.get("dropped_count"):
            state += f" · {thin['dropped_count']} left out (no real text in the feed or on its page)"
        log("source.done", f"{s.label} · {state}")
    return out


def seal_sources(sources: list, fetched: dict, retrieved_at: str) -> dict:
    """The sources in claim-seal's shape: {id: {"label", "items": [{id, title, text, url, retrieved_at}]}}."""
    out = {}
    for s in sources:
        items, _ = fetched[s.id]
        out[s.id] = {"label": s.label, "items": [
            {"id": f"{s.id}-{n + 1}", "title": it["title"], "text": it["description"] or it["title"],
             "url": it["url"], "retrieved_at": retrieved_at}
            for n, it in enumerate(items)]}
    return out


def write(lens: str, sources: list, fetched: dict, model, count: int, log=lambda *_: None,
          lens_definition: lenses.Lens | None = None) -> tuple[dict, dict]:
    """(brief, info): the model's brief, checked for shape, with single-source labels added."""
    if not any(r["status"] == "ok" for _, r in fetched.values()):
        raise ComposeError("no source gave any material; nothing to write from")
    level = lens_definition.reading_level if lens_definition is not None else P.DEFAULT_READING_LEVEL
    register = lens_definition.register if lens_definition is not None else ""
    text, info = P.build(lens, sources, fetched, count, reading_level=level, register=register)
    info["prompt_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    log("lens.started", "writing under the lens")
    valid = {s.id for s in sources}
    problems: list[str] = []
    for attempt in (1, 2):
        reply = model(text if attempt == 1 else P.retry_prompt(text, problems))
        try:
            brief = P.parse_reply(reply)
            problems = P.check_shape(brief, valid, count)
            if not problems and lens_definition is not None:
                problems = lenses.check_shape(lens_definition, brief, count)
        except P.ShapeError as exc:
            problems = [str(exc)]
        if not problems:
            info["attempts"] = attempt
            brief, info["quotes"] = quote_rule(brief, reply, text, sources, fetched, model, valid, count, log,
                                               lens_definition=lens_definition)
            info["single_source_labels_added"] = P.label_single_source(brief)
            log("lens.applied", f"brief written · {len(brief['items'])} insights")
            return brief, info
        log("lens.retry", "the answer could not be used: " + "; ".join(problems[:3]))
    raise ComposeError("the model's answer could not be used twice: " + "; ".join(problems[:5]))


def quote_rule(brief: dict, reply: str, prompt: str, sources: list, fetched: dict, model, valid: set, count: int,
               log=lambda *_: None, *, lens_definition: lenses.Lens | None = None) -> tuple[dict, dict]:
    """Hold the brief to the quote rule (composer.quotes) while the articles are still in memory.

    A brief that breaks it is sent back to the writer once (one more model call) to put those parts in its own
    words. If the answer cannot be used or still breaks the rule, the parts of the first brief that break it are
    dropped: those insights, the connection, or the transcript (then no narration). Returns (brief, note); the note
    goes into the edition and the receipt, with counts and positions only, never an article's words."""
    first = Q.check(brief, sources, fetched)
    note = {"rule": dict(Q.RULES), "runs": first["runs"], "passages": first["passages"],
            "breaches": len(first["breaches"]), "repaired": False, "repair_call": False}
    if not first["breaches"]:
        return brief, note
    arts = {(a["source"], a["item"]): a for a in Q.articles(sources, fetched)}
    problems = [Q.describe(b, arts) for b in first["breaches"]]
    log("quote.repair", f"the brief copies too much of an article in {len(first['breaches'])} place(s); "
                        "asking the writer to use its own words")
    note["repair_call"] = True
    try:
        again = P.parse_reply(model(P.quote_repair_prompt(prompt, reply, problems)))
        shape = P.check_shape(again, valid, count)
        if not shape and lens_definition is not None:
            shape = lenses.check_shape(lens_definition, again, count)
    except P.ShapeError as exc:
        again, shape = None, [str(exc)]
    if again is not None and not shape:
        second = Q.check(again, sources, fetched)
        if not second["breaches"]:
            note.update(repaired=True, runs=second["runs"], passages=second["passages"])
            log("quote.repaired", "the writer put those parts in its own words")
            return again, note
        note["breaches_after_repair"] = len(second["breaches"])
    else:
        note["repair_unusable"] = "; ".join(shape[:3])
    dropped = Q.drop(brief, first["breaches"])
    note["dropped"] = dropped
    if not brief.get("items"):
        raise ComposeError("every insight copied too much of an article, even after one request to rewrite; "
                           "nothing was kept")
    n = len(dropped["dropped_items"])
    parts = ([f"{n} insight{'s' if n != 1 else ''}"] if n else []) + (
        ["the connection"] if dropped["dropped_connection"] else []) + (
        ["the transcript"] if dropped["dropped_transcript"] else [])
    log("quote.dropped", "dropped " + " and ".join(parts) + " that copied too much of an article")
    return brief, note


def check(brief: dict, sealed_sources: dict, model, log=lambda *_: None) -> dict:
    """claim-seal's judge over the brief; returns its full result."""
    try:
        import claim_seal
    except ImportError:
        raise ComposeError("claim-seal is not installed; run `pip install -e .` in this folder") from None
    log("claim.verifying", "checking each claim against the articles it cites")
    result = claim_seal.judge(brief, sealed_sources, model=model)
    if result.get("claim_evidence") is not None and not claim_seal.verify_seal(result["claim_evidence"]):
        raise ComposeError("the seal did not verify right after it was made")
    return result


_FIELD_NAMES = {"insight": "insight", "why_it_matters": "why"}


def _edition_field(field: str) -> str | None:
    if field in _FIELD_NAMES:
        return _FIELD_NAMES[field]
    if field.startswith("detail["):
        return "details[" + field[len("detail["):]
    return None


def _window_digests(claim_evidence: dict | None) -> dict:
    """(item index, citation index) -> sha256 of the first located evidence window."""
    out = {}
    for row in (claim_evidence or {}).get("outcomes") or []:
        ref = row.get("claim_ref") or {}
        spans = row.get("evidence_spans") or []
        if ref.get("kind") == "item" and spans and isinstance(spans[0], dict) and spans[0].get("sha256"):
            out[(ref.get("item_index"), row.get("citation_index"))] = spans[0]["sha256"]
    return out


def _card(item: dict, index: int, labels: dict, digests: dict) -> dict:
    v = item.get("verification") or {}
    state = v.get("verdict") if v.get("verdict") in STATE_LABELS else "unchecked"
    card = {"insight": item.get("insight", ""), "why": item.get("why_it_matters", ""),
            "details": list(item.get("detail") or []), "state": state, "citations": []}
    # The judge's one-line reason stays in check.json only: it often quotes the source, and the
    # edition is the part of a brief meant to be shared.
    for n, cit in enumerate(v.get("citations") or []):
        row = {"label": labels.get(cit.get("source"), cit.get("source") or ""),
               "title": cit.get("matched_title") or cit.get("ref") or "",
               "url": cit.get("url") or "", "resolution": cit.get("resolution")}
        span = cit.get("span") or {}
        field = _edition_field(span.get("field") or "")
        if field and isinstance(span.get("start"), int) and isinstance(span.get("end"), int):
            row.update({"field": field, "start": span["start"], "end": span["end"],
                        "relation": span.get("sentence_relation")})
        if (index, n) in digests:
            row["window_sha256"] = digests[(index, n)]
        card["citations"].append(row)
    return card


def edition(*, lens: str, sources: list, fetched: dict, result: dict, model: Counted, seconds: int,
            composed_at: str, write_info: dict, lens_definition: lenses.Lens | None = None,
            checker: Counted | None = None) -> dict:
    """The shareable record of one brief: our words, cited titles and links, verdicts, the seal.

    It holds no article text. It is the same shape the replay page reads."""
    import claim_seal

    labels = {s.id: s.label for s in sources}
    digests = _window_digests(result.get("claim_evidence"))
    brief = result["brief"]
    cards = [_card(it, i, labels, digests) for i, it in enumerate(brief.get("items") or [])]
    conn = brief.get("connection")
    # the lens the page shows: a named lens (built in or saved) by its name, otherwise the reader's own words
    shown = lens_definition.name if lens_definition is not None and lens_definition.id != "ad-hoc" else lens
    out = {"schema": SCHEMA, "lens": shown, "composed_on": composed_at[:10], "seconds": seconds,
           "sources": [{"label": s.label, "items": fetched[s.id][1]["items"],
                        "status": fetched[s.id][1]["status"]} for s in sources],
           "cards": cards}
    if isinstance(conn, dict) and conn.get("headline"):
        cv = conn.get("verification") or {}
        out["connection"] = {"headline": conn["headline"], "confidence": conn.get("confidence"),
                             "why": conn.get("why", ""),
                             "state": cv.get("verdict") if cv.get("verdict") in STATE_LABELS else "unchecked"}
    if brief.get("honest_note"):
        out["honest_note"] = str(brief["honest_note"])
    if isinstance(write_info.get("quotes"), dict):
        out["quotes"] = write_info["quotes"]  # the quote rule's note: counts and positions, no article text
    if isinstance(brief.get("transcript"), str) and brief["transcript"].strip():
        out["transcript"] = brief["transcript"].strip()  # the narration script, in our own words
    ce = result.get("claim_evidence") or {}
    out["check"] = {"tool": f"claim-seal {claim_seal.__version__}", "status": result.get("status"),
                    "rows": len(ce.get("outcomes") or []),
                    "seal": ((ce.get("verification") or {}).get("seal") or {}).get("value"),
                    "seal_verified": bool(ce) and claim_seal.verify_seal(ce)}
    out["model"] = {"provider": getattr(model.inner, "name", None), **model.summary(),
                    "write_attempts": write_info.get("attempts")}
    if checker is None or checker is model:
        out["checker"] = {"provider": getattr(model.inner, "name", None), "same_as_writer": True}
    else:
        out["checker"] = {"provider": getattr(checker.inner, "name", None), "same_as_writer": False,
                          **checker.summary()}
    if lens_definition is not None:
        out["lens_definition"] = {"id": lens_definition.id, "name": lens_definition.name,
                                  "reading_level": lens_definition.reading_level,
                                  "register": lens_definition.register,
                                  "revision": lens_definition.revision,
                                  "prompt_sha256": write_info["prompt_sha256"]}
    return out


def compose(*, lens: str, sources: list, model, count: int = P.DEFAULT_INSIGHTS, get=http_get,
            log=lambda *_: None, clock=time.monotonic, lens_definition: lenses.Lens | None = None,
            checker=None) -> dict:
    """Run the whole brief. Returns {"edition", "result", "fetched"}; raises ComposeError.

    `model` writes the brief; `checker`, when given, makes every claim-seal call (each insight and the
    connection) instead of the writer."""
    lens = P.check_lens(lens)
    counted = model if isinstance(model, Counted) else Counted(model)
    judge = counted if checker is None else (checker if isinstance(checker, Counted) else Counted(checker))
    events = []

    def emit(kind, text):
        events.append({"kind": kind, "text": text})
        log(kind, text)

    started = clock()
    composed_at = _now()
    emit("run.started", f"compose started · {len(sources)} sources · lens: {lens}")
    fetched = read_sources(sources, get, emit)
    emit("sanitize.passed", "source text screened · "
        + f"{sum(r['cleaned'] for _, r in fetched.values())} risky strings neutralized")
    brief, info = write(lens, sources, fetched, counted, count, emit, lens_definition=lens_definition)
    result = check(brief, seal_sources(sources, fetched, composed_at), judge, emit)
    ed = edition(lens=lens, sources=sources, fetched=fetched, result=result, model=counted,
                 seconds=int(round(clock() - started)), composed_at=composed_at, write_info=info,
                 lens_definition=lens_definition, checker=judge)
    tally = {}
    for c in ed["cards"]:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    emit("claim.verified", "checked · " + " · ".join(f"{n} {STATE_LABELS[k]}" for k, n in tally.items()))
    out = {"edition": ed, "result": result, "fetched": fetched, "events": events, "receipt": counted.receipt()}
    if judge is not counted:
        out["checker_receipt"] = judge.receipt()
    return out
