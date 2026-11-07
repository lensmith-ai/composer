"""The data files the app page reads for one brief, under /data/live/<job>/.

  job.json         the job record, with `audio_state` (off, generating, ready, failed) and `audio`
  composed.json    the brief in the page's composed-brief/v1 shape, including `transcript`: the narration script
  transcript.txt   the same narration script, as plain text
  receipts.json    what was read and how, the model calls and the check summary (no source text; see receipts.py)
  composer-<voice>.mp3 (or .wav)   the narration, once it is ready

Nothing is ever joined from the request: the job id must match the store's job-id shape and the file name must
be one of the names above (a voice from the fixed list), so no other file can be reached.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import receipts
from .narration import VOICES

PREFIX = "/data/live/"
JOB_ID = re.compile(r"^job-[0-9a-f]{16}$")
TEXT_FILES = ("job.json", "composed.json", "transcript.txt", "receipts.json")
AUDIO = re.compile(r"^composer-(" + "|".join(VOICES) + r")\.(mp3|wav)$")
AUDIO_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}
VERDICT = {"supported": "supported", "partial": "partially_supported", "unsupported": "unsupported",
           "unresolved": "unresolved", "unchecked": "unchecked"}


def parse(path: str) -> tuple[str, str] | None:
    """(job id, file name) for a /data/live/ URL, or None when it is not one of the allowed files."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith(PREFIX):
        return None
    rest = path[len(PREFIX):].split("/")
    if len(rest) != 2 or not JOB_ID.match(rest[0]):
        return None
    if rest[1] in TEXT_FILES or AUDIO.match(rest[1]):
        return rest[0], rest[1]
    return None


# the edition names a claim's field one way and the page's composed-brief shape another
_PAGE_FIELD = {"insight": "insight", "why": "why_it_matters"}


def _page_field(field) -> str | None:
    if isinstance(field, str) and field.startswith("details["):
        return "detail[" + field[len("details["):]
    return _PAGE_FIELD.get(field)


def composed_view(job: dict, source_ids: dict | None = None, passages: dict | None = None) -> dict | None:
    """The page's composed-brief/v1 view of a finished job's edition, or None before the text is ready.
    `source_ids` maps a source label to its id. `passages` is the job's passages.json rows ("<item>.<citation>"
    -> the few words of located evidence); each citation row carries its `passage` and, when the checker marked a
    sentence of the brief's own words, its `span` {field, start, end, sentence_relation}: what the page's claim
    popover reads. Both are absent when the check kept none."""
    ed = job.get("result")
    if not isinstance(ed, dict):
        return None
    ids = source_ids or {}
    rows = (passages or {}) if isinstance(passages, dict) else {}

    def sources(citations):
        out = []
        for c in citations or []:
            if isinstance(c, dict) and c.get("title"):
                out.append({"id": ids.get(c.get("label"), c.get("label")), "label": c.get("label"),
                            "ref": c.get("title"), "url": c.get("url") or None})
        return out

    items = []
    for n, card in enumerate(ed.get("cards") or []):
        if not isinstance(card, dict):
            continue
        cites = [c for c in (card.get("citations") or []) if isinstance(c, dict) and c.get("title")]
        kept = [k for k, c in enumerate(card.get("citations") or []) if isinstance(c, dict) and c.get("title")]
        cited = []
        for k, s, c in zip(kept, sources(cites), cites):  # k: the citation's index in the edition, as the check numbers it
            row = {"source": s["id"], "ref": s["ref"], "url": s["url"], "resolution": c.get("resolution", "unresolved")}
            field = _page_field(c.get("field"))
            if field and isinstance(c.get("start"), int) and isinstance(c.get("end"), int):
                row["span"] = {"field": field, "start": c["start"], "end": c["end"],
                               "sentence_relation": c.get("relation")}
            passage = rows.get(f"{n}.{k}")
            if isinstance(passage, dict) and isinstance(passage.get("text"), str):
                row["passage"] = {"text": passage["text"], "cut": bool(passage.get("cut"))}
            elif c.get("window_sha256"):
                row["window_sha256"] = c["window_sha256"]
            cited.append(row)
        items.append({"insight": card.get("insight", ""), "why_it_matters": card.get("why", ""),
                      "detail": list(card.get("details") or []), "sources": sources(cites),
                      "verification": {"verdict": VERDICT.get(card.get("state"), "unchecked"), "citations": cited}})
    out = {"schema": "composed-brief/v1", "job": job.get("job"), "composed_at_utc": job.get("finished_at")
           or job.get("started_at"), "lens": ed.get("lens", ""), "items": items,
           "transcript": ed.get("transcript", ""), "voice": (job.get("audio") or {}).get("voice"),
           "audio_state": job.get("audio_state")}
    conn = ed.get("connection")
    if isinstance(conn, dict):
        out["connection"] = {"headline": conn.get("headline", ""), "confidence": conn.get("confidence"),
                             "why": conn.get("why", ""), "sources": []}
    return out


def transcript_text(job: dict) -> str | None:
    return receipts.transcript_text(job.get("result"))


def _read_passages(store, job_id: str) -> dict:
    """The rows of the job's passages.json, or {} when it has none or cannot be read."""
    path = Path(store.job_dir(job_id)) / "passages.json"
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows")
    except (OSError, ValueError, AttributeError):
        return {}
    return rows if isinstance(rows, dict) else {}


def read(store, job_id: str, name: str, source_ids: dict | None = None) -> tuple[bytes | Path, str] | None:
    """The bytes (or, for audio, the file to stream) and content type of one allowed file, or None when it does
    not exist (yet)."""
    try:
        job = store.status(job_id)
    except Exception:
        return None
    if name == "job.json":
        return json.dumps(job, ensure_ascii=False).encode("utf-8"), "application/json"
    if name == "composed.json":
        view = composed_view(job, source_ids, _read_passages(store, job_id))
        return (json.dumps(view, ensure_ascii=False).encode("utf-8"), "application/json") if view else None
    if name == "transcript.txt":
        text = transcript_text(job)
        return (text.encode("utf-8"), "text/plain; charset=utf-8") if text else None
    if name == "receipts.json":
        path = Path(store.job_dir(job_id)) / name
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_bytes(), "application/json"
    m = AUDIO.match(name)
    audio = job.get("audio") or {}
    if not m or job.get("audio_state") != "ready" or audio.get("file") != name:
        return None
    path = Path(store.job_dir(job_id)) / name
    if path.is_symlink() or not path.is_file():
        return None
    return path, AUDIO_TYPES[m.group(2)]
