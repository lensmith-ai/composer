# Install the app (setup.sh)

The shortest way is one command; see [docs/install.md](install.md). What follows is the same install, run from a folder. The short version is in the [README](../README.md#install-the-app-from-a-download).

The full app (the phone-width page, saved briefs, a daily brief, optional narration) installs into ONE folder,
`~/.lensmith-composer`, and touches nothing else: no sudo, no global Python, no PATH change. (The one-command installer also makes a
`lensmith` shortcut at the end: a link in `~/.local/bin`, or, if you say yes, 3 lines in your shell profile; see [docs/install.md](install.md).)

```sh
./setup.sh
~/.lensmith-composer/bin/composer up        # prints "Open: http://127.0.0.1:8765/"; Cmd+click it in macOS Terminal
```

Setup prints "Step N of 7" as it goes, with the download's own progress. If it has to download Python it first says
why (for example, "Found python3 3.9.6 at /usr/bin/python3; Composer needs 3.10 or newer."). On a slow connection a
download can take several minutes; if one fails, setup shows the real error and what to do next, and
`UV_HTTP_TIMEOUT=600 sh setup.sh` gives it more time (the default is 300 seconds per request).

`./setup.sh` checks everything first and writes nothing until every check passes. It uses your Python 3.10+ (or,
only if you say yes, downloads a pinned, checksum-verified uv into that folder, which brings its own Python), makes
a private environment there, and asks, one question at a time: your model provider and key (typed without being
shown, stored in a file only you can read), starting sources, optional narration (it shows the size and the
licences first, and reuses a Kokoro you already have, read-only, when it passes a check), an optional article
parser for news pages without a feed, a daily brief, and a port. In the app you can add a source by pasting a blog's
address (it finds the feeds and you pick one), start from a package of sources, and make and edit your own lenses
(name, what to look for, register, reading level; each edit is a new revision, and a brief records the one it
used). `./setup.sh --answers answers.toml` asks nothing. `composer doctor` checks the install one line at a time;
`composer uninstall` removes what setup made and keeps your briefs unless you add `--delete-data`. Composer works
only in folders no other account can change; if setup refuses yours (a home reached through a link, as on Fedora
Silverblue; a group-writable folder under umask 002; a FAT or exFAT disk), the refusal says what to do, and
[docs/setup.md](setup.md) lists the common cases. Everything, including updates, backups and what each command
may touch: [docs/setup.md](setup.md).
