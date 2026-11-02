"""The receipt and transcript files of one brief, written without any source text.

  receipts.json   what was read and how (each source's status, item count and fetch tier), the model calls with
                  the usage the provider reported (no prices, nothing estimated), which model wrote the brief and
                  which checked it (`models`; with a separate checker its calls are in `checker_calls` and
                  `model_calls` holds the writer's), the check summary and, when a
                  lens from the registry or the lens store was used, that lens's revision and the prompt's digest
  transcript.txt  the narration script the model wrote with the brief, the same words the page's transcript
                  sheet shows and narration reads; a brief without one gets no transcript file

The server writes receipts.json into each job's folder and serves it at /data/live/<job>/receipts.json;
`composer compose` writes both files next to the brief.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "composer-receipt/v1"


def model_receipt(counted) -> dict:
    return counted.receipt()


def build_receipt(run: dict, *, requested: list | None = None) -> dict:
    """`sources` is keyed by source id, as the page reads it; `requested_sources` keeps the order asked for."""
    sources = {}
    for source_id, (_items, receipt) in (run.get("fetched") or {}).items():
        sources[source_id] = {"label": receipt.get("label", ""), "status": receipt.get("status", "failed"),
                              "items": receipt.get("items", 0), "fetch_tier": receipt.get("fetch_tier", "native")}
    edition = run.get("edition") or {}
    output = {"schema": SCHEMA, "requested_sources": list(requested if requested is not None else sources),
              "sources": sources, "model_calls": dict(run.get("receipt") or {}),
              "check": dict(edition.get("check") or {})}
    writer = dict(run.get("receipt") or {})
    checker = run.get("checker_receipt")
    output["models"] = {"writer": {"provider": writer.get("provider"), "models": list(writer.get("models") or [])},
                        "checker": {"provider": (checker or writer).get("provider"),
                                    "models": list((checker or writer).get("models") or []),
                                    "same_as_writer": checker is None}}
    if checker is not None:
        output["checker_calls"] = dict(checker)
    lens_definition = edition.get("lens_definition")
    if isinstance(lens_definition, dict):
        output["lens_definition"] = {key: lens_definition[key] for key in
                                     ("id", "name", "reading_level", "register", "revision", "prompt_sha256")
                                     if key in lens_definition}
    return output


def transcript_text(edition: object) -> str | None:
    """The model-written narration script of a brief, as plain text, or None when it has none."""
    if isinstance(edition, dict) and isinstance(edition.get("transcript"), str) and edition["transcript"].strip():
        return edition["transcript"].strip() + "\n"
    return None


def write_brief_artifacts(out: Path, run: dict, *, requested: list | None = None) -> list[Path]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    text = transcript_text(run.get("edition"))
    if text is not None:
        transcript = out / "transcript.txt"
        transcript.write_text(text, encoding="utf-8")
        written.append(transcript)
    receipt = out / "receipts.json"
    receipt.write_text(json.dumps(build_receipt(run, requested=requested), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    written.append(receipt)
    return written
