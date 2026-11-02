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


def _write(samples, rate, base):
    import soundfile as sf
    try:
        sf.write(base + ".mp3", samples, rate, format="MP3")
        with open(base + ".mp3", "rb") as handle:
            head = handle.read(3)
        if head == b"ID3" or head[:1] == b"\xff":
            return base + ".mp3", "mp3"
        os.unlink(base + ".mp3")
    except Exception:
        try:
            os.unlink(base + ".mp3")
        except OSError:
            pass
    sf.write(base + ".wav", samples, rate, format="WAV")
    return base + ".wav", "wav"


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
