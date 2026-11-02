"""Offline re-verification for a saved claim-seal check document, one brief or every saved brief.

`composer seal verify DIR` checks one; `composer doctor --seals` and the scheduler's daily seal re-check (while
`composer up` runs) check every saved brief with recheck_saved().
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class SealError(ValueError):
    """A saved check is missing or cannot be re-verified."""


def verify_check_document(document: object, *, verifier=None) -> tuple[bool, str | None]:
    if not isinstance(document, dict) or not isinstance(document.get("claim_evidence"), dict):
        raise SealError("check document has no re-verifiable claim_evidence")
    evidence = document["claim_evidence"]
    if verifier is None:
        try:
            import claim_seal
        except ImportError:
            raise SealError("claim-seal is not installed") from None
        verifier = claim_seal.verify_seal
    verified = bool(verifier(evidence))
    seal = ((evidence.get("verification") or {}).get("seal") or {}).get("value")
    return verified, seal if isinstance(seal, str) else None


def verify_check_path(path: Path) -> tuple[bool, str | None]:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "check.json"
    try:
        document = json.loads(candidate.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SealError(f"no check.json at {candidate}") from None
    except json.JSONDecodeError:
        raise SealError(f"check document is not valid JSON: {candidate}") from None
    return verify_check_document(document)


def recheck_saved(data: Path, *, verify=None) -> dict:
    """Re-verify the seal of every saved brief in the current data generation.

    {"checked": n verified, "failed": ["job-... (why)", ...], "unsealed": [job folders saved before seals were
    kept]}. A brief fails when its stored draft no longer matches the digest it was checked with, when its check
    document cannot be read, when the seal chain does not recompute, or when the seal it states is not the one
    the check document holds. Raises SealError when claim-seal is not installed."""
    from . import settings as S
    if verify is None:
        try:
            import claim_seal
        except ImportError:
            raise SealError("claim-seal is not installed") from None
        verify = claim_seal.verify_seal
    out = {"checked": 0, "failed": [], "unsealed": []}
    if not (Path(data) / "current").exists():
        return out
    gen = S.generation_dir(Path(data), create=False)
    for marker in sorted((gen / "jobs").glob("job-*/saved.json")):
        folder = marker.parent
        try:
            job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out["failed"].append(f"{folder.name} (unreadable)")
            continue
        draft = job.get("result")
        digest = hashlib.sha256(json.dumps(draft, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if job.get("draft_sha256") and digest != job["draft_sha256"]:
            out["failed"].append(f"{folder.name} (the brief changed after it was checked)")
            continue
        check = folder / "check.json"
        if not check.is_file():
            out["unsealed"].append(folder.name)
            continue
        try:  # the same re-verification as `composer seal verify`
            verified, sealed_value = verify_check_document(json.loads(check.read_text(encoding="utf-8")),
                                                           verifier=verify)
        except (OSError, json.JSONDecodeError, SealError):
            verified, sealed_value = False, None
        stated = ((draft or {}).get("check") or {}).get("seal")
        if not verified or (stated and stated != sealed_value):
            out["failed"].append(f"{folder.name} (seal does not verify)")
            continue
        out["checked"] += 1
    return out


def summary(result: dict) -> str:
    """One line for a log or a status page."""
    text = f"{result['checked']} saved brief(s) re-verified"
    if result["failed"]:
        text = f"FAILED: {', '.join(result['failed'])[:300]}; " + text
    if result["unsealed"]:
        text += f"; {len(result['unsealed'])} carry no seal record (saved before seals were kept)"
    return text
