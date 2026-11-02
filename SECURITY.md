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
  `html-index` source only follows links on the hosts and paths you list.
- **Output.** The brief file and the page keep the brief's own words, the cited titles and links,
  the verdicts and SHA-256 digests. They do not store the articles' text (a sentence may quote a
  few words, as any summary does). `check.json` also holds the judge's one-line reasons, which
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
