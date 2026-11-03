"""Composer's own folders and files get explicit private modes (SECURITY.md), whatever the umask or a default ACL.

The reported input: a parent folder (0755) carrying the default POSIX ACL "u::rwx,g::r-x,o::r-x,u:65534:rwx,m::rwx".
mkdir() with its default mode (0777) ignores the umask under a default ACL, so setup made six data folders 0775 and
the install then refused itself; open()'s default 0666 made the journal and the lock files 0664 the same way. Now every
folder Composer makes is set to 0700 on the folder as opened (fchmod) once it exists, and every file it creates is
created 0600 (or its own explicit mode), so nothing comes out group- or other-writable."""
import ctypes
import ctypes.util
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import fake_home
from test_lifecycle import install, saved_job

from composer import home as H, lifecycle as L, settings as S
from composer.job_store import JobStore
from composer.lenses import LensStore
from composer.registry import add_to_file, parse_entry

POSIX = os.name == "posix" and hasattr(os, "getuid")
ACL_TYPE_DEFAULT = 0x4000
GRANT = b"u::rwx,g::r-x,o::r-x,u:65534:rwx,m::rwx"


def loose_entries(root: Path) -> list:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            st = os.lstat(Path(dirpath) / name)
            if not stat.S_ISLNK(st.st_mode) and st.st_mode & 0o022:
                out.append(f"{stat.S_IMODE(st.st_mode):04o} {Path(dirpath, name).relative_to(root)}")
    return sorted(out)


def everything(target: Path) -> None:
    """Setup's data, a saved brief moved to the trash and back, journal steps, a lens, a source, a backup and a
    restore, and the key: what Composer itself writes in its folders."""
    data = target / "data"
    job = saved_job(data)
    store = JobStore(data, worker=None)
    store.delete(job)
    store.restore(job)
    store.record("update", "intent", old_version="a", new_version="b", old_generation="g1", new_generation="g1")
    LensStore(S.generation_dir(data) / "lenses").save({"name": "Mine", "instruction": "what changed",
                                                       "reading_level": "plain"})
    add_to_file(S.sources_file(data), parse_entry({"id": "ex", "label": "Example", "kind": "rss-or-atom",
                                                   "url": "https://example.com/feed.xml", "max_items": 5}))
    L.restore(data, L.backup(data))
    S.write_secret(data, "ANTHROPIC_API_KEY", "fake-key-for-test")


@unittest.skipUnless(POSIX, "owners and permission bits: POSIX")
class ExplicitModeTests(unittest.TestCase):
    def test_make_dirs_sets_the_mode_even_when_mkdir_gives_more(self):
        # what a default ACL does to mkdir: the mode argument is not what the folder gets
        real_mkdir = os.mkdir

        def generous(path, mode=0o777, *a, **k):
            real_mkdir(path, mode, *a, **k)
            os.chmod(path, 0o775, **({"dir_fd": k["dir_fd"]} if "dir_fd" in k else {}))

        with fake_home() as home:
            with mock.patch.object(os, "mkdir", generous):
                H.make_dirs(home / "a" / "b" / "c")
                with H.open_home(home) as at:
                    at.child("d").close()
                H.owned_dir(home, "e", "f")
            for rel in ("a", "a/b", "a/b/c", "d", "e", "e/f"):
                with self.subTest(folder=rel):
                    self.assertEqual(stat.S_IMODE(os.stat(home / rel).st_mode), 0o700)
            with self.assertRaises(FileExistsError):
                H.make_dirs(home / "a", exist_ok=False)

    def test_nothing_composer_makes_is_open_to_others_under_an_open_umask(self):
        old = os.umask(0)
        try:
            with fake_home() as home:
                target = install(home)
                everything(target)
                self.assertEqual(loose_entries(target), [])
                L.admit(target, target / "data")
        finally:
            os.umask(old)

    def test_nothing_composer_makes_is_open_to_others_under_a_default_acl(self):
        name = ctypes.util.find_library("acl")
        if not name:
            self.skipTest("libacl is not installed here")
        acl = ctypes.CDLL(name)
        acl.acl_from_text.restype = ctypes.c_void_p
        acl.acl_from_text.argtypes = [ctypes.c_char_p]
        acl.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
        acl.acl_free.argtypes = [ctypes.c_void_p]
        with fake_home() as home:
            parent = home / "acl-parent"
            parent.mkdir(mode=0o755)
            os.chmod(parent, 0o755)
            grant = acl.acl_from_text(GRANT)
            try:
                if not grant or acl.acl_set_file(str(parent).encode(), ACL_TYPE_DEFAULT, grant) != 0:
                    self.skipTest("this filesystem does not take a default POSIX ACL")
            finally:
                if grant:
                    acl.acl_free(grant)
            probe = parent / "probe"
            os.mkdir(probe)  # mkdir's default 0777: the ACL, not the umask, decides
            widened = stat.S_IMODE(os.stat(probe).st_mode)
            os.rmdir(probe)
            self.assertEqual(widened, 0o775, "the default ACL did not take effect; the test would prove nothing")
            target = install(parent)
            everything(target)
            self.assertEqual(loose_entries(target), [])
            L.admit(target, target / "data")


if __name__ == "__main__":
    unittest.main()
