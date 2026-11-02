"""Where a folder cannot be removed through open folder descriptors (systems without them, such as Windows), narration
leaves its check folder in place and says so (SECURITY.md). The note must be seen when the caller gives no log of its
own: it goes to standard error, never to a callback that drops it."""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import fake_home

from composer import narration as N


class CleanupNoteTests(unittest.TestCase):
    def test_the_default_check_render_cleanup_note_is_seen(self):
        with fake_home() as home:
            app = home / ".lensmith-composer"
            err = io.StringIO()
            with mock.patch.object(N, "CONFINED", False), contextlib.redirect_stderr(err):
                with self.assertRaises(N.NarrationError):  # the real worker without its runtime: the render fails
                    N.check_render(Path(sys.executable), "model", "voices", home=app, timeout=60)
            left = app / "tmp" / "narration-check"
            self.assertTrue(left.is_dir())
            self.assertIn(f"left {left}", err.getvalue())
            self.assertIn("remove it yourself", err.getvalue())

    def test_a_caller_log_still_gets_it_and_the_helper_default_is_visible(self):
        with fake_home() as home:
            app = home / ".lensmith-composer"
            notes, err = [], io.StringIO()
            with mock.patch.object(N, "CONFINED", False), contextlib.redirect_stderr(err):
                with self.assertRaises(N.NarrationError):
                    N.check_render(Path(sys.executable), "model", "voices", home=app, timeout=60, log=notes.append)
                self.assertEqual(err.getvalue(), "")
                self.assertTrue(any("narration-check" in n for n in notes), notes)
                self.assertFalse(N._remove_owned_tree(app, ("tmp",), "narration-check"))
            self.assertIn("narration-check", err.getvalue())
            self.assertTrue((app / "tmp" / "narration-check").is_dir())


if __name__ == "__main__":
    unittest.main()
