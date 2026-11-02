"""Narration worker: runs INSIDE the narration runtime (python -I worker.py), never imported by Composer.

It reads one JSON request on stdin and prints one JSON answer on stdout:

  {"mode": "check", "model": PATH, "voices": PATH, "out_dir": DIR, "want": [voice, ...]}
      load the model pair, list its voices, render one short sentence with each wanted voice that exists
  {"mode": "render", "model": PATH, "voices": PATH, "voice": V, "text": T, "out": PATH_WITHOUT_SUFFIX}
      render T with voice V; write PATH.mp3, or PATH.wav when this platform's soundfile cannot write MP3

The model files are only opened for reading. Only kokoro_onnx, soundfile and the standard library are used.
"""
import json
import os
import sys
import time


def _fresh(path):
    """A new, empty file at a temporary name next to `path`, made here: whatever already has that name (a leftover,
    or a hard link to a file elsewhere) is unlinked first, and the new file is never opened through a link."""
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, ".%s.%d.tmp" % (name, os.getpid()))
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    os.close(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644))
    return tmp


def _write(samples, rate, base):
    """Write the audio as MP3 (or WAV where this soundfile cannot write MP3), always into a fresh file that is then
    renamed into place: an existing file of the final name, or one hard-linked to it, is replaced, never written
    through."""
    import soundfile as sf
    for suffix, fmt in ((".mp3", "MP3"), (".wav", "WAV")):
        final = base + suffix
        tmp = _fresh(final)
        try:
            sf.write(tmp, samples, rate, format=fmt)
            if fmt == "MP3":
                with open(tmp, "rb") as handle:
                    head = handle.read(3)
                if not (head == b"ID3" or head[:1] == b"\xff"):
                    raise ValueError("this soundfile did not write MP3")
            os.replace(tmp, final)
            return final, fmt.lower()
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            if fmt == "WAV":
                raise


def main():
    req = json.loads(sys.stdin.read())
    if req.get("nice") and hasattr(os, "nice"):
        try:
            os.nice(int(req["nice"]))  # narration runs at low priority, after the brief's text is final
        except OSError:
            pass
    from kokoro_onnx import Kokoro
    started = time.monotonic()
    engine = Kokoro(req["model"], req["voices"])
    available = sorted(engine.get_voices())
    if req["mode"] == "check":
        want = [v for v in req.get("want", []) if isinstance(v, str)]
        rendered, formats = [], set()
        for voice in want:
            if voice not in available:
                continue
            samples, rate = engine.create("Composer checks this voice.", voice=voice, speed=1.0, lang="en-us")
            path, fmt = _write(samples, rate, os.path.join(req["out_dir"], "check-" + voice))
            if os.path.getsize(path) > 0:
                rendered.append(voice)
                formats.add(fmt)
            os.unlink(path)
        print(json.dumps({"ok": rendered == want, "rendered": rendered,
                          "missing": [v for v in want if v not in available], "formats": sorted(formats),
                          "seconds": round(time.monotonic() - started, 2)}))
        return 0
    if req["mode"] == "render":
        if req["voice"] not in available:
            print(json.dumps({"ok": False, "error": "voice not in this model's voices"}))
            return 1
        samples, rate = engine.create(req["text"], voice=req["voice"], speed=1.0, lang="en-us")
        path, fmt = _write(samples, rate, req["out"])
        print(json.dumps({"ok": True, "file": path, "format": fmt, "audio_seconds": round(len(samples) / rate, 2),
                          "seconds": round(time.monotonic() - started, 2)}))
        return 0
    print(json.dumps({"ok": False, "error": "unknown mode"}))
    return 2


if __name__ == "__main__":
    sys.exit(main())
