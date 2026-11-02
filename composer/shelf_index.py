"""The shelf index the app page reads at /data/index.json: one line per brief in the store.

The page cannot list a folder, so the list is written down. It is derived, never authored: every field is read from
the job's own record (job.json) and, for audio, from the file being there. A record that will not parse is listed
with "readable": false rather than left out, so the drawer can say a brief exists but cannot be opened.

What the page reads from it:
  - the menu drawer's saved briefs (commit.state "saved", not test jobs): title, when, insight count, sources, audio;
  - the compose screen's "in flight, rejoin" note (state "running");
  - the lens library's "N briefs using this lens" (readable briefs per lens id);
  - an opened brief's title.

Only these fields are written (an allow list): no key, no file path, no source text, no model reply.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .live_files import AUDIO

SCHEMA = "brief-index/v0"
FILE = "brief-index.json"  # in the store's current generation; served as /data/index.json
_JOB = re.compile(r"^job-[0-9a-f]{16}$")
_TITLE_LIMIT = 40


def _date(value: object) -> str:
    text = str(value or "")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return "Saved brief"


def _short(value: object, limit: int = _TITLE_LIMIT) -> str:
    """A label cut between words, never mid-word."""
    text = " ".join(str(value or "").split()).strip(" .")
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(" .") + "…"


def _title(result: object, started_at: object) -> str:
    """The first insight's own words (so the drawer and the opened brief agree), else the connection headline, else
    the day the brief was started."""
    if isinstance(result, dict):
        cards = result.get("cards")
        if isinstance(cards, list) and cards and isinstance(cards[0], dict):
            title = _short(cards[0].get("insight"))
            if title:
                return title
        connection = result.get("connection")
        if isinstance(connection, dict):
            title = _short(connection.get("headline"))
            if title:
                return title
    return _date(started_at)


def _text(value: object, limit: int = 120) -> str | None:
    return str(value)[:limit] if isinstance(value, str) and value else None


def _words(result: dict) -> int:
    transcript = result.get("transcript")
    return len(transcript.split()) if isinstance(transcript, str) else 0


def entry(folder: Path) -> dict:
    """One brief's line, read from its folder."""
    job_id = folder.name
    try:
        job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        if not isinstance(job, dict) or job.get("job") != job_id:
            raise ValueError("not this job's record")
    except (OSError, ValueError):
        return {"job": job_id, "readable": False, "state": "unreadable", "title": "Unreadable brief"}
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    result = job.get("result") if isinstance(job.get("result"), dict) else None
    commit = job.get("commit") if isinstance(job.get("commit"), dict) else {}
    state = job.get("state") if job.get("state") in ("running", "done", "failed") else "failed"
    audio = job.get("audio") if isinstance(job.get("audio"), dict) else {}
    audio_file = audio.get("file") if isinstance(audio.get("file"), str) else None
    has_audio = bool(job.get("audio_state") == "ready" and audio_file and AUDIO.match(audio_file)
                     and (folder / audio_file).is_file() and not (folder / audio_file).is_symlink())
    progress = [p.get("phase") for p in job.get("progress") or [] if isinstance(p, dict) and isinstance(p.get("phase"), str)]
    out = {
        "job": job_id,
        "readable": state != "done" or result is not None,
        "state": state,
        "phase": _text(job.get("phase"), 40),
        "title": _title(result, job.get("started_at")),
        "lens": _text(request.get("lens"), 200),
        "sources": [s for s in request.get("sources") or [] if isinstance(s, str)][:8],
        "voice": _text(request.get("voice"), 40),
        "started_at": _text(job.get("started_at"), 40),
        "finished_at": _text(job.get("finished_at"), 40),
        "composed_at": _text(job.get("finished_at"), 40) if state == "done" else None,
        "items": len(result.get("cards") or []) if result else 0,
        "words": _words(result) if result else 0,
        "audio": has_audio,
        "audio_file": audio_file if has_audio else None,
        "test_job": request.get("test") is True,
        "commit": {"state": "saved" if commit.get("state") == "saved" else "unsaved",
                   "saved_at_utc": _text(commit.get("saved_at_utc"), 40),
                   "expires_at_utc": _text(commit.get("expires_at_utc"), 40)},
        "progress": progress[-20:],
    }
    if state == "failed":
        out["error"] = _text(job.get("error"), 120)
    return out


def build(jobs_dir: Path) -> dict:
    """The whole index for the briefs in `jobs_dir` (the trash is not listed), newest first. It carries no time of its
    own: the same briefs give the same bytes, so rewriting it at start leaves an unchanged generation unchanged."""
    folders = sorted(p for p in Path(jobs_dir).glob("job-*") if p.is_dir() and _JOB.match(p.name))
    briefs = [entry(p) for p in folders]
    briefs.sort(key=lambda b: (b.get("started_at") or "", b["job"]), reverse=True)
    return {"schema": SCHEMA, "count": len(briefs), "briefs": briefs}
