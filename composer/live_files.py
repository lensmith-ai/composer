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


def composed_view(job: dict, source_ids: dict | None = None) -> dict | None:
    """The page's composed-brief/v1 view of a finished job's edition, or None before the text is ready.
    `source_ids` maps a source label to its id."""
    ed = job.get("result")
    if not isinstance(ed, dict):
        return None
    ids = source_ids or {}

    def sources(citations):
        out = []
        for c in citations or []:
            if isinstance(c, dict) and c.get("title"):
                out.append({"id": ids.get(c.get("label"), c.get("label")), "label": c.get("label"),
                            "ref": c.get("title"), "url": c.get("url") or None})
        return out

    items = []
    for card in ed.get("cards") or []:
        if not isinstance(card, dict):
            continue
        cites = card.get("citations") or []
        items.append({"insight": card.get("insight", ""), "why_it_matters": card.get("why", ""),
                      "detail": list(card.get("details") or []), "sources": sources(cites),
                      "verification": {"verdict": VERDICT.get(card.get("state"), "unchecked"),
                                       "citations": [{"source": s["id"], "ref": s["ref"], "url": s["url"],
                                                      "resolution": c.get("resolution", "unresolved")}
                                                     for s, c in zip(sources(cites), [c for c in cites if
                                                                                      isinstance(c, dict) and c.get("title")])]}})
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
        view = composed_view(job, source_ids)
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
