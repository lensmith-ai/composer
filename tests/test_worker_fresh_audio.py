"""The local narration worker writes its audio (the setup check and every brief's narration) to a fresh file and
renames it into place (SECURITY.md, fresh files): an existing file of the final name, or one hard-linked to a file
elsewhere, is replaced, never written through. soundfile writes by path and truncates what is there, so it is handed
a new temporary name made exclusively. The real soundfile and Kokoro runtime are not installed in the tests: a
stand-in soundfile that writes by path, as the real one does, is used."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (a trusted temporary folder)

WORKER = Path(__file__).resolve().parent.parent / "composer" / "narration" / "worker.py"


def load_worker():
    spec = importlib.util.spec_from_file_location("composer_narration_worker_under_test", WORKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stand_in_soundfile(mp3: bool):
    """soundfile.write by path, truncating whatever the path names (as the real one does)."""
    written = []

    def write(path, samples, rate, format=None):
        written.append((path, format))
        with open(path, "wb") as handle:  # opens and truncates the existing file, through any hard link
            if format == "MP3":
                handle.write(b"ID3 fake mp3" if mp3 else b"RIFF not an mp3 at all")
            else:
                handle.write(b"RIFF fake wav")
    return types.SimpleNamespace(write=write), written


@unittest.skipUnless(hasattr(os, "link"), "hard links")
class FreshAudioTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="composer-audio-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        self.out = self.root / "narration-check"
        self.out.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.worker = load_worker()

    def sentinel(self, name: str, final: str) -> Path:
        path = self.outside / name
        path.write_bytes(b"KEEP " + name.encode())
        os.link(path, self.out / final)
        return path

    def test_a_hard_linked_wav_is_replaced_not_written_through(self):
        keep = self.sentinel("wav-sentinel", "check-af_heart.wav")
        keep_mp3 = self.sentinel("mp3-sentinel", "check-af_heart.mp3")
        sf, written = stand_in_soundfile(mp3=False)
        with mock.patch.dict(sys.modules, {"soundfile": sf}):
            path, fmt = self.worker._write([0.0], 24000, str(self.out / "check-af_heart"))
        self.assertEqual((path, fmt), (str(self.out / "check-af_heart.wav"), "wav"))
        self.assertEqual(keep.read_bytes(), b"KEEP wav-sentinel")
        self.assertEqual(keep_mp3.read_bytes(), b"KEEP mp3-sentinel")
        self.assertEqual(Path(path).read_bytes(), b"RIFF fake wav")
        self.assertTrue(all(Path(p).name.startswith(".") and p.endswith(".tmp") for p, _ in written), written)
        self.assertEqual(sorted(os.listdir(self.out)), ["check-af_heart.mp3", "check-af_heart.wav"])

    def test_a_hard_linked_mp3_is_replaced_not_written_through(self):
        keep = self.sentinel("mp3-sentinel", "voice.mp3")
        sf, _ = stand_in_soundfile(mp3=True)
        with mock.patch.dict(sys.modules, {"soundfile": sf}):
            path, fmt = self.worker._write([0.0], 24000, str(self.out / "voice"))
        self.assertEqual(fmt, "mp3")
        self.assertEqual(keep.read_bytes(), b"KEEP mp3-sentinel")
        self.assertEqual(Path(path).read_bytes(), b"ID3 fake mp3")

    def test_a_planted_temporary_name_is_never_reused(self):
        keep = self.outside / "tmp-sentinel"
        keep.write_bytes(b"KEEP")
        os.link(keep, self.out / f".voice.wav.{os.getpid()}.tmp")
        os.symlink(keep, self.out / f".voice.mp3.{os.getpid()}.tmp")
        sf, _ = stand_in_soundfile(mp3=False)
        with mock.patch.dict(sys.modules, {"soundfile": sf}):
            self.worker._write([0.0], 24000, str(self.out / "voice"))
        self.assertEqual(keep.read_bytes(), b"KEEP")
        self.assertEqual(sorted(os.listdir(self.out)), ["voice.wav"])


if __name__ == "__main__":
    unittest.main()
