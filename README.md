# Lensmith Composer

<table>
<tr>
<td width="33%"><img src="docs/readme/brief.png" alt="Phone screen of a finished brief. The top insight, Model capability and safety need paired release tracks, sits above a drawing of two feeds, Google AI blog and Google DeepMind blog, 5 items each, woven through a screen and the system improvements lens. Below it: Checked 6/6."></td>
<td width="33%"><img src="docs/readme/cards.png" alt="Phone screen further down the same brief: a row of insight cards. The first card says partly supported, 2 sources, then its title and why it matters. Below the row: 1 of 5, the two sources with 5 items each, and claim-seal, run again on the recorded answers: 6 of 6 checks agree."></td>
<td width="33%"><img src="docs/readme/card-open.png" alt="The first insight card, opened. It says partly supported, 2 sources. The words each article backs are underlined and numbered. Under Sources and seals, each article gets a row: what it says, claim-seal re-check: agrees, a fingerprint, and a link to open the article."></td>
</tr>
<tr>
<td>The finished brief: five insights from two feeds, read through one lens. "Checked 6/6" means every check was made.</td>
<td>Each insight is a card you can tap. Its label says how well the cited articles back it.</td>
<td>A card, opened. Underlined words are the ones an article backs, and each source shows claim-seal's verdict.</td>
</tr>
</table>

<sub>Screenshots of the demo in <code>docs/demo</code>, which replays a brief recorded on 2026-10-25. Every word in them is from that brief.</sub>

> **AI;DR (AI, didn't read)**
> Claude wrote this code and this README. I haven't read either line by line.
> What people have checked: the private version of Composer writes briefs I read, and I click through to the cited articles to see that what a claim says is really there.
> What tools have checked, for this repository: 87 offline tests pass on Python 3.10 and 3.13 in clean containers; the commands in this README were run there (the compose command, which needs a key, on 3.13 only); a secret scanner (gitleaks) found nothing in any commit; and one test fails if private names, server paths or key shapes appear anywhere in the files or the history.
> What was checked live: one brief, written from a fresh install in a clean Python 3.13 container with a real Anthropic key and the default model. It made 7 calls in 29 seconds and cost about 8 cents; every insight got a claim-seal verdict and the seal verified. The OpenAI-compatible path has not been run live; it is tested against the documented request and reply shapes only. Treat it as a working experiment, and open an issue if something's off. (Arya)

**Composer reads a few feeds, writes a short brief through a lens you choose, and checks every
claim against the article it cites before you read it.**

A lens is a few words of your own, such as "what this means for small teams" or "where the
risks are". Composer asks a model for five short insights through that lens. Each insight must
cite the feed items it uses by their exact titles. Then [claim-seal](https://github.com/lensmith-ai/claim-seal)
checks each one: a cited title must really be in the feed (plain code, no model), and then a
model reads the claim next to its source and says whether the source supports it, partly
supports it, or does not. Each insight is printed with that label, a link to each article, and
the exact words in our sentence that each article backs.

What it does not do: it does not prove a claim is true. It checks whether the cited source
backs it. A claim that a wrong source supports still passes. The checker is a model and can be
wrong; claim-seal keeps it honest where code can (a quote must be found exactly, a failed call
is "not checked", never a pass), but it cannot make the reading correct.

## Quickstart (on your computer)

You need Python 3.10 or newer. Download or clone this repository, then work from its folder.

**See it work with no key and no install.** This replays a brief composed on 2026-10-25 from
the two bundled feeds. It makes no network request and no model call:

```sh
python3 -m composer demo
```

**Install it** (in a virtual environment). `pip install .` fetches claim-seal from GitHub at a
pinned commit, so this step needs the internet:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install .
composer demo --fast
python -m unittest discover -s tests -t tests
```

**Compose your own brief.** Set `ANTHROPIC_API_KEY` in your environment (from the Anthropic
Console), then name the sources and your lens:

```sh
composer compose --sources google-ai,deepmind --lens "system improvements" --out brief
```

It prints each step and then the brief, and writes three files to the `--out` folder (without
`--out`, a new folder under `briefs/`): `edition.json` (the brief), `check.json` (claim-seal's
full result, with the sealed rows) and `index.html` (the brief as a web page). Any lens works:
try `--lens "what this means for small teams"`. All the options:

```sh
composer compose --help
```

## Bring your own model

Composer calls the model with your own key. Nothing goes through any other service.

| setting | what it does |
|---|---|
| `ANTHROPIC_API_KEY` | your Anthropic key (the default provider) |
| `COMPOSER_MODEL` | the model id; default `claude-sonnet-5-5` |
| `COMPOSER_PROVIDER` | `anthropic` (default) or `openai` for any OpenAI-compatible endpoint |
| `COMPOSER_OPENAI_BASE_URL` | for `openai`: the endpoint, such as `https://api.openai.com/v1` or a local server |
| `OPENAI_API_KEY` | for `openai`: the key |
| `COMPOSER_MAX_TOKENS` | the reply ceiling per call (default 16000) |
| `COMPOSER_ANTHROPIC_FALLBACK` | `off` turns off the API's server-side refusal fallback, which is on by default for the models that accept it |

The key is read when each call is made. It is never stored, logged or written to a file.

## Three ways to run it

1. **Local (your computer, your key).** The command line above. Briefs land in `briefs/`.
2. **Static demo (no key, no server).** `docs/demo/` replays the recorded brief in a window onto
   Composer's own screen: the compose sentence, the sources being read, the sand-and-words
   animation through each step, the weave, then the finished edition, where each card opens to
   show which of its words each article backs. `docs/demo/brief.html` is the same brief as a plain
   page. Host the `docs/` folder on any static host (GitHub Pages works) or open
   `docs/demo/index.html` from disk. It makes no outside request and calls no model; with reduced
   motion it shows the finished edition. Rebuild the folder with:

   ```sh
   composer demo --site docs/demo
   ```

3. **Always-on server (your key, your machine or server).** `composer serve` shows the latest
   brief and a form to compose a new one. It listens on 127.0.0.1:8765 by default. Without a
   key it still shows the recorded brief, and Compose says that a key is needed.

   ```sh
   composer serve
   ```

   To let other machines reach it, set `COMPOSER_SERVER_PASS` to a long phrase first and start
   it with `--host 0.0.0.0`; it refuses to listen beyond this machine without one, because
   anyone who can compose spends your API credit. Put a TLS proxy in front of it. One brief runs
   at a time.

## What a brief costs

**7 model calls** with the default settings: 1 to write the brief, 1 to check each of the 5
insights, and 1 to check the connection the brief draws between sources. If the first answer
cannot be used (not valid JSON, or a citation outside the chosen sources), Composer asks once
more, which makes 8. Fetching the two bundled feeds costs nothing; it is one request each.

**Measured: about $0.08 per brief** with the default model. One live brief (the command above,
Google AI blog and Google DeepMind blog, 5 items each, on 2026-11-01) made 7 calls to
`claude-sonnet-5-5` and the API reported 14,334 input and 4,679 output tokens: 1,910 in and
2,594 out to write the brief, and about 2,000 to 2,300 in and 300 to 450 out for each of the
6 checks. At Anthropic's published prices for Claude Sonnet 5.5, $2 per million input tokens
and $10 per million output tokens ([pricing page](https://platform.claude.com/docs/en/about-claude/pricing),
read 2026-11-01), that is $0.0287 + $0.0468 = **$0.0755**. It took 29 seconds from start to finish.
Your cost moves with the number of sources and items, the model, and whether a retry is needed;
each brief's `edition.json` records its own calls and the token counts the API reported.

The recorded demo brief was written and checked by gpt-5.6-terra (an OpenAI model) on a
flat-rate plan, before this repository had its own API layer: 7 calls, 37,489 input and 4,065
output tokens. Its token counts are not comparable with Claude's.

## Adding your own sources

Yes: any RSS or Atom feed, the Hacker News front page, or a news page with no feed. Add one with
`composer sources add` (it writes `composer-sources.json` in the current folder) and use its id
in `--sources`. See [docs/adding-sources.md](docs/adding-sources.md) for the file format, the
three kinds of source and their safety rules. To see what is available:

```sh
composer sources list
```

## What is kept, and what is not

- The brief (`edition.json`, `index.html`) keeps the brief's own words, the cited article titles
  and links, the verdicts, and SHA-256 fingerprints of the passages checked. It does not store
  the articles' text. Like any summary, a sentence may quote a few words of a title or
  description.
- `check.json` is claim-seal's full record: verdicts, the sealed claim-evidence rows (positions
  and digests, never source text) and the judge model's one-line reasons. Those reasons often
  quote the source, so read `check.json` before you share it.
- The feed text is held in memory for the one brief. `--keep-sources` saves it, for debugging.
- The recorded demo brief (`composer/data/recorded-run.json`) follows the same rule.

## What is in this repository

| path | what it is |
|---|---|
| `composer/adapters/` | the three source readers: `rss_or_atom`, `hn_json_api`, `html_index` |
| `composer/sanitize.py` | cleans feed text before it reaches a prompt |
| `composer/prompt.py` | the writing prompt and the check on the model's answer |
| `composer/providers.py` | the model layer: Anthropic Messages API and OpenAI-compatible endpoints |
| `composer/pipeline.py` | one brief from start to finish |
| `composer/cli.py`, `composer/server.py` | the `composer` command and `composer serve` |
| `composer/page.py`, `composer/web/` | the one-file brief page |
| `composer/window.py`, `composer/web/window/` | the animated replay window and its scripts and styles |
| `composer/sources.json` | the two bundled feeds |
| `composer/data/recorded-run.json` | the recorded brief the demo replays |
| `docs/demo/` | the static demo: the animated replay (`index.html`) and the plain page (`brief.html`) |
| `tests/` | offline tests: fixtures only, no network, no key |

## Tests

Every test runs offline, from invented fixture feeds and scripted model replies. The model
layer is tested with a scripted transport, and the whole pipeline (fetch, screen, write, check,
seal) runs end to end with claim-seal replaying recorded judge answers. Without claim-seal
installed, the 8 pipeline tests are skipped and the rest still run.

```sh
python -m unittest discover -s tests -t tests
```

`tests/test_banned.py` fails if the working tree or the git history holds a server path, an
internal id shape, a key shape, or one of a list of private names (stored as salted hashes). To
add your own terms without publishing them, point `COMPOSER_DENYLIST` at a file outside the
repository, one regular expression per line.

## Licence

MIT, see [LICENSE](LICENSE). claim-seal is MIT. See [THIRD-PARTY.md](THIRD-PARTY.md) for every
dependency, its version and its licence.
