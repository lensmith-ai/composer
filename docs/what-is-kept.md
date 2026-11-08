# What is kept, what is not, and privacy

## What is kept, and what is not

- The brief (`edition.json`, `index.html`) keeps the brief's own words, the cited article titles
  and links, the verdicts, and SHA-256 fingerprints of the passages checked. It does not store
  the articles' text. Like any summary, a sentence may quote a few words of a title or
  description.
- `check.json` is claim-seal's full record: verdicts, the sealed claim-evidence rows (positions
  and digests, never source text) and the judge model's one-line reasons. Those reasons often
  quote the source, so read `check.json` before you share it.
- The feed text is held in memory for the one brief. `--keep-sources` saves it, for debugging.
- The one exception: for a brief composed from the app page, the few words (at most 25) of each located passage are
  written to `passages.json` in that brief's own folder on your computer, for a later claim view (this version's app page does not show them yet). They are
  never in the edition, `receipts.json` or `check.json`.
- The recorded demo brief (`composer/data/recorded-run.json`) follows the same rule.


## Privacy

Composer has no telemetry: no analytics, no crash reports, no update checks. It talks to the feeds you chose and
the model provider you chose, with your key, and nothing else. On a server, Caddy also talks to its certificate
authority.
