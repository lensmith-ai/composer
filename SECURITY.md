# Security

Please report a security problem privately through GitHub's "Report a vulnerability" button on
this repository, not in a public issue.

## Reporting

- **Where:** the "Report a vulnerability" button (Security tab), which opens a private advisory only the
  maintainers can read. Please include the version (`composer --version`), how you run it (command line, page,
  Docker Compose with Caddy) and the steps that show the problem.
- **When you will hear back:** an acknowledgement within 3 days, and a fix or a plan with a date within 14 days.
  We credit reporters in the advisory and the changelog unless you ask us not to.
- **Supported versions:** the latest release gets security fixes. Before 1.0, that is the latest 0.y release only.

  | version | security fixes |
  |---|---|
  | latest 0.y release | yes |
  | anything older | no; please update |

- **In scope:** the `composer` package and command, its web page and server, the container image, `compose.yaml`
  and the `Caddyfile` as shipped, the deploy guide as written (docs/deploy-vps.md), and the release workflow and
  its artifacts (checksums, SBOM, attestations).
- **Out of scope:** problems that need someone who can already run commands on your machine or server; your own
  changes to the shipped files; the model provider's or a feed's own service; a brief that says what a hostile feed
  wanted (see "What a hostile feed can still do" below: that is a known limit, not a bug).
- **Safe harbour:** research done in good faith, on your own install, that avoids other people's data and
  services, and that you report to us privately first, is welcome; we will not pursue it.

What Composer does to stay safe, and where its limits are:

- **Where Composer works (the trust contract).** Composer trusts your own account and root, and no other account.
  Before setup (`./setup.sh` and `composer setup`, with or without `--data`), update, rollback, restore, uninstall,
  backup, recovery after an interrupted update or restore (`composer up` runs it first), `composer doctor`'s checks
  that write or start something, `composer serve`'s job store, and narration's downloads, checks and clean-ups
  write, remove or start anything, Composer checks, only reading, that no other account can change what it is about
  to use:
  - *Above the folder.* The app folder (and the data folder) and every folder above it, up to `/`, on the path as
    given and on its real path, must belong to you or root and be writable by no one else: no group or other write
    bit. A folder every account can write, such as `/tmp`, is always refused.
  - *Symbolic links on the way.* The path as given may not go through a symbolic link at all. A link leads through
    folders that are on neither the path as given nor its real path (and so would go unchecked), so Composer and
    setup.sh refuse it and name the real path to give instead.
  - *Inside the folder, all the way down.* Every folder and file Composer writes into, runs or reads as its own
    configuration must belong to you or root, and no folder or file may be writable by group or others: `bin` and
    the launcher, `app` and every `app/<version>` with its environment, `python`, `bootstrap`, `narration`,
    `models`, `cache`, `tmp`, the marker and the install manifest, and the data folder with everything in it (its
    settings, key, generations, backups and recovery journal). An existing install or data folder that breaks this
    is refused, never adopted as it is, with the fix (`chmod -R go-w <folder>`, `chown`). The check runs over the
    whole app folder and data folder at setup, update, rollback, restore, uninstall, backup, doctor and recovery,
    and again on each folder
    where Composer walks into it (through the folder it actually opened) and on the folders it hands to a program
    it starts (`TMPDIR`, the caches) just before that program starts.
  - *Before anything changes.* Setup, update, rollback, restore, uninstall, backup and recovery run all of these
    checks before they take the run lock or write, remove or recover anything, so a refusal has changed nothing
    (`composer doctor` reports a refusal as its "trust" check and stops there: it reads no settings, key or sources
    file from those folders, makes no model, checker or source call with them, even with `--online`, and writes
    and starts nothing; settings another account wrote could otherwise send your key to an endpoint it chose). No
    command calls a model or a source, or uses your key, with settings from a folder that failed this check. The run lock is
    opened inside the data folder as opened, never through a link; uninstall removes by name inside the app folder
    it opened, and backup writes inside the backups folder it opened (a `--out` folder must pass the same check).
    Recovery acts only inside the data folder: it rebuilds the folders an unfinished restore names from their
    checked names, and refuses a recovery record that names any other place.

  Composer never makes a group- or other-writable folder or file of its own, whatever your umask or a default ACL on
  a folder above: it gives each one an explicit mode (folders 0700, set again on the folder as opened once it exists;
  files 0600, the launcher 0700). The programs it starts (venv, pip, the narration
  runtime) run under a umask with no group or other write bit; a default POSIX ACL on a folder above the app folder
  still decides what those programs make, and Composer then refuses the result at its next check, with the fix
  (`chmod -R go-w <folder>`), rather than use it. Inside the folder it writes and removes through open folder descriptors, never follows a
  link where it keeps its own folders (only `app/current` is a link), and writes downloads, temporary files and
  narration audio (the local runtime's included) as fresh files renamed into place. An update never removes a
  version folder it did not make itself in that run (rollback, the explicit command, removes the version it rolled
  back from). This is the rule OpenSSH applies to `~/.ssh` ("StrictModes"), applied to every folder Composer uses.
  *Defended:* another account on the same machine changing, swapping or linking anything under the app or data
  folder, above it, or on a link on the way to it, to make Composer write, remove or run something else.
  *Assumed:* the guarantee holds where the filesystem, its access-control model and its mounts enforce the owners
  and permission bits Composer checks. Linux POSIX ACLs were checked: a grant to another account shows in the group
  write bit (the ACL mask), and Composer refuses it; a default ACL on a folder above is inherited by what is made
  below it, and Composer's explicit modes mask such a grant off on everything it makes itself. macOS and NFSv4 ACLs, network and FUSE filesystems, and
  filesystems without POSIX owners are not certified; an access-control entry the permission bits do not show, or
  a mount another account administers, is outside what Composer can see.
  *Not defended:* a program already running as you (it can change your files and Composer's directly, so a race
  against it crosses no boundary), root, and systems without POSIX owners and permission bits (on Windows the check
  does not run, and a version or narration folder that cannot be removed through a folder descriptor is left in
  place with a note on standard error).
  *Places you name, outside the contract:* some commands write only where you point them, never in the app or data
  folder, and those places are not checked: `composer compose --out` (a new or empty folder), `composer demo --site`
  and `--page`, `composer sources add --file`, and `composer serve`, which keeps the sources, packages and lenses you
  save on its page in `composer-sources.json`, `composer-packages.json` and `composer-lenses/` in the current folder,
  or next to the file you name with `--sources-file` (or `COMPOSER_SOURCES`). Run these in a folder of your own.
  The same user-named sources file is read, not checked, by `composer compose`, `composer sources check` and
  `composer serve`, and also by `composer up` and `composer doctor --online` when the data folder has no sources
  file of its own (the usual case after setup): then they read `COMPOSER_SOURCES`, or else `composer-sources.json`
  in the current folder, on top of the bundled list. Its feeds are fetched with no key, and nothing in it is run; it
  decides which public addresses are read and whose text reaches your brief. So start `composer up` and
  `composer doctor --online` from a folder of your own too.
  `composer serve`'s job store (`--out`, default `~/.lensmith-composer/data`) is checked like the data folder, and
  serve writes to exactly the path it checked.
- **Your key.** The API key is read from the environment when each call is made. It is never
  stored, logged or written to a file, and an error message that repeats it is cut before it is
  shown. A call that carries the key refuses redirects and refuses a plain `http://` endpoint
  unless it is this machine. A successful reply is checked too, against this policy: it "holds the
  key" when it contains the whole key or any run of 12 or more of its characters (its start, its
  end or anywhere inside). The only part of a key not protected is one of these exact published
  prefixes at its start: `sk-ant-api03-`, `sk-ant-admin01-`, `sk-proj-`, `sk-svcacct-`,
  `sk-or-v1-`; any other key is protected from its first character. A reported model id that holds
  the key is replaced by the configured one, a token count whose digits hold it is recorded as
  unknown, and a reply whose text holds it is refused, so none of them reaches a brief or its
  receipts. The check reads the reply as sent: it does not look for a key the endpoint has
  re-encoded.
- **Feed text is untrusted.** Every string from a feed is cleaned (hidden characters removed,
  instruction-like phrases broken up) and placed between source markers that the prompt says are
  data. This lowers the odds that a feed can steer the model. It does not rule it out.
- **Fetching.** Only `https://` sources can be registered, and every fetch stays on https (a
  redirect to `http://` is refused; at most 5 redirects). Composer will not connect to this
  machine or a private network (loopback, `10.x`, `192.168.x`, link-local such as
  `169.254.169.254` where cloud servers keep credentials): a name is resolved once, every
  address it gives must be public, and Composer connects only to those addresses, so a redirect
  or a name that changes its answer (DNS rebinding) cannot get there either. Proxy settings
  (`HTTPS_PROXY` and the like) are not used for feeds, because a proxy resolves names itself.
  `COMPOSER_ALLOW_PRIVATE_FETCH=1` turns the address rule off, for a feed on your own network.
  Feed and page bodies over 2 MB are refused, as are bodies shorter than they said and gzip
  streams that stop early, and a fetch stops after 60 seconds in total however slowly anything
  arrives (name lookup, connecting, handshake, headers or body).
  Feeds that declare XML entities are refused, in any encoding. Markup is read with scans that
  take time in proportion to its size, so a page full of unclosed tags cannot stall a brief. An
  `html-index` source only follows links on the hosts and paths you list, on the same port as
  the page, with no dot segments, `;`, encoded slashes or control characters in the path, and a redirect of an
  article to another host, port or folder is refused before anything is requested from it (the index page may only
  move within its own host and port); each redirect hop counts as a request against the check's request limits. When the app finds no
  feed at a pasted address it can offer an `html-index` source for the page: the server builds it
  from the address alone (that one host, the page's own folder as the only prefix, 10 links and 5
  articles at most, never the front page), shows the links and article titles it read, and saves
  nothing until you confirm; the browser's copy of the offer is not used for the scope.
  A feed entry whose description is empty or filler ("TBD", "coming soon") is read from its own page for a brief:
  https only, the same host and port as the feed ("www." ignored), every redirect hop held to that site and counted,
  at most 10 requests and 45 seconds for one source, the first timeout stops asking that site, and a page that
  cannot be read means the entry is left out with the reason in the receipt. Feed discovery follows links on the
  pasted page only to the same site, reads at most two of them as web pages, and tries at most six feeds from each.
- **Output.** The brief file and the page keep the brief's own words, the cited titles and links,
  the verdicts and SHA-256 digests. They do not store the articles' text (a sentence may quote a
  few words, as any summary does). For a brief composed from the app page, the few words (at most 25, and at most
  300 characters) of each located passage are kept in `passages.json` in that brief's own folder, owner-readable only,
  for the claim popover; the brief file, the receipts and `check.json` never carry them. `check.json` also holds the judge's one-line reasons, which
  often quote the source. The page makes no outside request; its Content-Security-Policy allows
  only its own inline script and style. Every feed string is set as text, never as markup, and
  only an `http(s)` address becomes a link.
- **The server.** `composer serve` listens on 127.0.0.1 by default. There it answers only
  requests addressed to this machine by name (127.0.0.1, localhost or [::1]), so a web site that
  points its own name at your machine (DNS rebinding) gets nothing, and a compose request must
  come from its own page as JSON, so another site open in your browser cannot start a brief and
  spend your credit. It will not listen on another address unless `COMPOSER_SERVER_PASS` is set,
  and every compose request must then send that phrase. It serves two fixed paths and no files
  from disk. It is a plain standard-library server: put it behind a TLS proxy before exposing it.
- **Running it on a server** (compose.yaml, docs/deploy-vps.md). Composer has no accounts: the login is Caddy's
  (HTTP basic authentication over HTTPS, with a bcrypt hash of one password), on every path, and Caddy never passes
  it to the app. The app's container publishes no port; only Caddy's 80 and 443 are open, and the app runs as an
  unprivileged user on a read-only filesystem with no extra privileges. Your model key is never a container
  environment variable. One login for one person: sharing it shares your API credit. Caddy does not slow down
  repeated wrong passwords, so use a long random one. Exposing the app without Caddy and the login is not supported.
- **Release integrity.** From the first release on, every file attached to a GitHub Release and the container image
  carry GitHub artifact attestations (build provenance and SBOM) made by this repository's release workflow, and
  SHA256SUMS lists every file. `gh attestation verify` checks where a file came from; a checksum alone only shows the
  download is complete.
- **The seal is not a signature.** It is an unkeyed SHA-256 chain. It shows a later edit only
  when compared with a copy you kept. See claim-seal's README.
- **What a hostile feed can still do.** It cannot run code on your machine or in the page, it
  cannot reach this machine or your private network, and the model's answer cannot add a link:
  every link in a brief is the address the feed gave for a title it cited, and only http(s)
  addresses are kept. A feed can redirect a fetch to another public https site. It can try to
  steer the brief: its text
  is in the prompt, and a model can be persuaded. The worst case is a brief that says what the
  feed wanted, with that feed's titles cited; the check can then rate it supported, because the
  feed does say it. Read briefs from sources you do not trust with that in mind.

## Review history

**2026-11-01**, before the repository was made public: an adversarial review of every file, with
each attack run on the reviewer's own machine. Fixed, each with a regression test in
`tests/test_security.py`:

- `composer serve` accepted a compose request sent from any web site (as `text/plain`, which a
  browser sends without asking) and requests for any host name (DNS rebinding), so a page you
  visited could start briefs on your key. It now checks Host, Origin and the content type.
- A source, or a redirect from it, could make Composer fetch from this machine or a private
  network (such as a cloud server's credential address) and pass the answer to the model. Fetches
  are now https only and refused for non-public addresses, checked on the connected socket.
- Several markup scans took time in proportion to the square of the page size: a 2 MB page of
  unclosed tags could stall a brief for hours. They are now linear.
- The time limit was per read, so a server sending one byte at a time (in the handshake, the
  headers or the body) could hold a brief open indefinitely. A fetch now stops after 60 seconds
  in total.
- The refusal of XML entity declarations was a byte search that a UTF-16 feed passed (the XML
  parser's own expansion limit still stopped an entity bomb). The parser itself now refuses them.
- Smaller hardening: the pages print only http(s) addresses as links; a feed can no longer
  write the prompt's own source markers; and a model endpoint that echoes your key back in an
  error message no longer gets it printed or sent to the page.
- claim-seal, the one dependency, was installed with git from a pinned commit, so nothing
  checked the download (and `pip install .` failed on a machine without git). It is now GitHub's
  archive of the same commit, and pip refuses it unless its SHA-256 matches.

**2026-11-01, second opinion** (an independent reviewer attacking the fixes above). Fixed, with
tests: a configured proxy could resolve a name to a private address after Composer had checked
it (proxies are now not used for feeds); the meta-description scan was still quadratic for one
tag with many repeated attributes (tags are now read by a one-pass scanner, no regex); slow name
lookups and connection attempts could outlast the total time limit (both now get only the time
left, and every address is checked before any connection); a body shorter than its
Content-Length or a cut-off gzip stream was accepted (now refused); a key echoed exactly at the
200-character cut of an error message could leave a prefix (it is now removed before the cut);
and the server's Host check accepted text after an IPv6 address in brackets, and duplicate
headers (it now accepts exactly one local authority and one of each header).

## The one-command installer (`install.sh`)

`curl -fsSL <address> | sh` trusts exactly one thing you cannot check from inside: the HTTPS fetch of the script
itself. Everything after that is pinned inside the script: the SHA-256 of the installer kit, of uv, of Python, of the
macOS Python installer, and of the wheels of Composer, certifi and claim-seal (and of setuptools, used only to build
claim-seal from its source if no wheel is available). Each file is checked before it is run or extracted, from whichever
source it came; a file that does not match is thrown away and the next source is tried. pip installs the wheels with
`--require-hashes --no-index`. A file you hand it (`COMPOSER_FILES_DIR`, `COMPOSER_KIT` and the others) is copied
into the installer's own folder and the copy is the one that is checked and used. If you would rather read it first,
download it, compare its SHA-256 with the one printed on the download page, then run it; `sh install.sh --show-pins`
prints every pin. When uv has to download Python itself (every other source failed), uv checks that file against the same
SHA-256 (tested: a changed file is refused). Python is started with `-I` (one exception: the preflight runs Composer's own code from the kit folder, and honours your
`PYTHONPATH`), so a file named `venv.py` or `pip` in the folder you run the command from is never imported.

It uses no `sudo`, except on macOS when you add `--install-python-pkg` and no other Python can be had: it then
downloads python.org's installer, checks its SHA-256 and its signature, and runs it with `sudo` (that installer may edit
your shell profile itself). Outside the app folder it writes only a log file and a temporary folder in
`TMPDIR` (the folder is removed, the log stays; it holds no key) and, at the end, the `lensmith` shortcut: one link in
`~/.local/bin` or `~/bin` when that is yours and on your PATH, or, only if you say yes (or pass `--path`), three marked alias
lines in your shell profile. It never makes a command called `composer` and never replaces another program named `lensmith`;
`lensmith composer uninstall` removes exactly the link and the three lines it added. Your Anthropic key is typed hidden on the terminal, kept in
one shell variable, handed to setup only through its environment (never an argument), and stored mode 0600.
Reviewed independently on 2026-11-08 (an outside reviewer's blocker and should-fix findings were fixed with tests).
