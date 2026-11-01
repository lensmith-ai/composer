# Security

Please report a security problem privately through GitHub's "Report a vulnerability" button on
this repository, not in a public issue.

What Composer does to stay safe, and where its limits are:

- **Your key.** The API key is read from the environment when each call is made. It is never
  stored, logged or written to a file. A call that carries the key refuses redirects and refuses
  a plain `http://` endpoint unless it is this machine.
- **Feed text is untrusted.** Every string from a feed is cleaned (hidden characters removed,
  instruction-like phrases broken up) and placed between source markers that the prompt says are
  data. This lowers the odds that a feed can steer the model. It does not rule it out.
- **Fetching.** Only `https://` sources can be registered. Feed and page bodies over 2 MB are
  refused. Feeds that declare XML entities are refused. An `html-index` source only follows
  links on the hosts and paths you list.
- **Output.** The brief file and the page keep the brief's own words, the cited titles and links,
  the verdicts and SHA-256 digests. They do not store the articles' text (a sentence may quote a
  few words, as any summary does). `check.json` also holds the judge's one-line reasons, which
  often quote the source. The page makes no outside request; its Content-Security-Policy allows
  only its own inline script and style.
- **The server.** `composer serve` listens on 127.0.0.1 by default. It will not listen on another
  address unless `COMPOSER_SERVER_PASS` is set, and every compose request must then send that
  phrase. It is a plain standard-library server: put it behind a TLS proxy before exposing it.
- **The seal is not a signature.** It is an unkeyed SHA-256 chain. It shows a later edit only
  when compared with a copy you kept. See claim-seal's README.
