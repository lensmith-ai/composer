"""Downloads and temporary files are always written to a fresh file. A .part (or temporary) name that already exists,
for example a hard link to a file outside the app folder, is unlinked first, never opened and truncated: the outside
file keeps its bytes. (A link check alone cannot see a hard link; only a fresh file can.)"""
import hashlib
import io
import os
import unittest
from unittest import mock

from install_helpers import fake_home

from composer import home as H, narration as N

BLOB = b"model bytes"


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return "https://example.org/model"


def tiny_pins():
    return {N.MODEL_FILE: (hashlib.sha256(BLOB).hexdigest(), len(BLOB))}


@unittest.skipUnless(os.name == "posix", "hard links and symbolic links: POSIX")
class FreshFileTests(unittest.TestCase):
    def setUp(self):
        self._home = fake_home()
        self.home = self._home.__enter__()
        self.addCleanup(self._home.__exit__, None, None, None)
        self.app = self.home / ".lensmith-composer"
        (self.app / "models" / "kokoro").mkdir(parents=True, mode=0o700)
        self.outside = self.home / "outside.bin"
        self.outside.write_bytes(b"KEEP OUTSIDE")

    def download(self):
        with mock.patch.object(N, "PINNED", tiny_pins()):
            N.download(self.app, log=lambda *_: None, opener=lambda url, timeout: Response(BLOB))

    def test_a_part_file_hard_linked_outside_is_not_written_through(self):
        os.link(self.outside, self.app / "models" / "kokoro" / (N.MODEL_FILE + ".part"))
        self.download()
        self.assertEqual(self.outside.read_bytes(), b"KEEP OUTSIDE")
        self.assertEqual((self.app / "models" / "kokoro" / N.MODEL_FILE).read_bytes(), BLOB)

    def test_a_part_file_that_is_a_symbolic_link_is_not_followed(self):
        os.symlink(self.outside, self.app / "models" / "kokoro" / (N.MODEL_FILE + ".part"))
        self.download()
        self.assertEqual(self.outside.read_bytes(), b"KEEP OUTSIDE")
        self.assertEqual((self.app / "models" / "kokoro" / N.MODEL_FILE).read_bytes(), BLOB)

    def test_the_path_based_download_keeps_the_same_rule(self):
        os.link(self.outside, self.app / "models" / "kokoro" / (N.MODEL_FILE + ".part"))
        with mock.patch.object(N, "CONFINED", False):
            self.download()
        self.assertEqual(self.outside.read_bytes(), b"KEEP OUTSIDE")

    def test_atomic_write_never_reuses_its_temporary_name(self):
        target = self.app / "note.txt"
        os.link(self.outside, self.app / f".note.txt.{os.getpid()}.tmp")
        H.atomic_write(target, "inside", mode=0o600)
        self.assertEqual(self.outside.read_bytes(), b"KEEP OUTSIDE")
        self.assertEqual(target.read_text(encoding="utf-8"), "inside")
        with H.open_home(self.app) as at:
            os.link(self.outside, self.app / f".other.txt.{os.getpid()}.tmp")
            at.write("other.txt", "inside")
        self.assertEqual(self.outside.read_bytes(), b"KEEP OUTSIDE")


if __name__ == "__main__":
    unittest.main()
