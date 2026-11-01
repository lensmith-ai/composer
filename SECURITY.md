# Security

Please report a security problem privately through GitHub's "Report a vulnerability" button on
this repository, not in a public issue.

What Composer does to stay safe, and where its limits are:

- **Your key.** The API key is read from the environment when each call is made. It is never
  stored, logged or written to a file, and an error message that repeats it is cut before it is
  shown. A call that carries the key refuses redirects and refuses a plain `http://` endpoint
  unless it is this machine.
- **Feed text is untrusted.** Every string from a feed is cleaned (hidden characters removed,
  instruction-like phrases broken up) and placed between source markers that the prompt says are
  data. This lowers the odds that a feed can steer the model. It does not rule it out.
- **Fetching.** Only `https://` sources can be registered, and every fetch stays on https (a
  redirect to `http://` is refused; at most 5 redirects). Composer will not connect to this
  machine or a private network (loopback, `10.x`, `192.168.x`, link-local such as
  `169.254.169.254` where cloud servers keep credentials): the address the connection actually
  reached is checked before anything is sent, so a redirect or a name that changes its address
  (DNS rebinding) cannot get there either. `COMPOSER_ALLOW_PRIVATE_FETCH=1` turns this off, for
  a feed on your own network. Feed and page bodies over 2 MB are refused, and a fetch stops
  after 60 seconds in total however slowly the bytes arrive (handshake, headers or body).
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
