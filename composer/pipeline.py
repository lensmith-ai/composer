"""One brief, start to finish: read, screen, write, check, seal.

    1 read     each chosen source through its adapter (composer.adapters)
    2 screen   every string cleaned (composer.sanitize); counts kept per source
    3 write    one model call under your lens (composer.prompt); one retry if the answer
               cannot be used
    4 check    claim-seal: every cited title must exist (plain code), then one model call per
               claim (each insight, and the connection) to judge support, sentence by sentence
    5 seal     claim-seal's SHA-256 chain over the claim-evidence rows

Model calls per brief: 1 to write, plus 1 per insight, plus 1 for the connection. With the
default 5 insights that is 7. A retry, or a brief with fewer items, changes the count; the
edition records the real number.

What is written to disk (composer.cli decides where): the edition (our words, the cited titles
and links, the verdicts and the seal; never the articles' text) and the full claim-seal result.
The feed text itself stays in memory unless you ask for it with --keep-sources.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from . import adapters, prompt as P
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
        items, receipt = adapters.fetch(s, get)
        out[s.id] = (items, receipt)
        state = f"{receipt['items']} items (ok)" if receipt["status"] == "ok" else f"failed: {receipt.get('error')}"
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


def write(lens: str, sources: list, fetched: dict, model, count: int, log=lambda *_: None) -> tuple[dict, dict]:
    """(brief, info): the model's brief, checked for shape, with single-source labels added."""
    if not any(r["status"] == "ok" for _, r in fetched.values()):
        raise ComposeError("no source gave any material; nothing to write from")
    text, info = P.build(lens, sources, fetched, count)
    log("lens.started", "writing under the lens")
    valid = {s.id for s in sources}
    problems: list[str] = []
    for attempt in (1, 2):
        reply = model(text if attempt == 1 else P.retry_prompt(text, problems))
        try:
            brief = P.parse_reply(reply)
            problems = P.check_shape(brief, valid, count)
        except P.ShapeError as exc:
            problems = [str(exc)]
        if not problems:
            info["attempts"] = attempt
            info["single_source_labels_added"] = P.label_single_source(brief)
            log("lens.applied", f"brief written · {len(brief['items'])} insights")
            return brief, info
        log("lens.retry", "the answer could not be used: " + "; ".join(problems[:3]))
    raise ComposeError("the model's answer could not be used twice: " + "; ".join(problems[:5]))


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
            composed_at: str, write_info: dict) -> dict:
    """The shareable record of one brief: our words, cited titles and links, verdicts, the seal.

    It holds no article text. It is the same shape the replay page reads."""
    import claim_seal

    labels = {s.id: s.label for s in sources}
    digests = _window_digests(result.get("claim_evidence"))
    brief = result["brief"]
    cards = [_card(it, i, labels, digests) for i, it in enumerate(brief.get("items") or [])]
    conn = brief.get("connection")
    out = {"schema": SCHEMA, "lens": lens, "composed_on": composed_at[:10], "seconds": seconds,
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
    if isinstance(brief.get("transcript"), str) and brief["transcript"].strip():
        out["transcript"] = brief["transcript"].strip()  # the narration script, in our own words
    ce = result.get("claim_evidence") or {}
    out["check"] = {"tool": f"claim-seal {claim_seal.__version__}", "status": result.get("status"),
                    "rows": len(ce.get("outcomes") or []),
                    "seal": ((ce.get("verification") or {}).get("seal") or {}).get("value"),
                    "seal_verified": bool(ce) and claim_seal.verify_seal(ce)}
    out["model"] = {"provider": getattr(model.inner, "name", None), **model.summary(),
                    "write_attempts": write_info.get("attempts")}
    return out


def compose(*, lens: str, sources: list, model, count: int = P.DEFAULT_INSIGHTS, get=http_get,
            log=lambda *_: None, clock=time.monotonic) -> dict:
    """Run the whole brief. Returns {"edition", "result", "fetched"}; raises ComposeError."""
    P.check_lens(lens)
    counted = model if isinstance(model, Counted) else Counted(model)
    started = clock()
    composed_at = _now()
    log("run.started", f"compose started · {len(sources)} sources · lens: {lens}")
    fetched = read_sources(sources, get, log)
    log("sanitize.passed", "source text screened · "
        + f"{sum(r['cleaned'] for _, r in fetched.values())} risky strings neutralized")
    brief, info = write(lens, sources, fetched, counted, count, log)
    result = check(brief, seal_sources(sources, fetched, composed_at), counted, log)
    ed = edition(lens=lens, sources=sources, fetched=fetched, result=result, model=counted,
                 seconds=int(round(clock() - started)), composed_at=composed_at, write_info=info)
    tally = {}
    for c in ed["cards"]:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    log("claim.verified", "checked · " + " · ".join(f"{n} {STATE_LABELS[k]}" for k, n in tally.items()))
    return {"edition": ed, "result": result, "fetched": fetched}
