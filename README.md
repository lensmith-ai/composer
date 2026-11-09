# Lensmith Composer

<table>
<tr>
<td width="33%"><img src="docs/readme/brief.png" alt="Phone screen of a finished brief. Its title, Safety decisions need policy-relevant evidence, is at the top, above a drawing of six feeds (Google AI, Google DeepMind, Hugging Face, Microsoft Research, PyTorch and arXiv cs.AI), 5 items each, woven through a screen and the system improvements lens. Below the drawing: Checked 6/6, then a short readout of the edition."></td>
<td width="33%"><img src="docs/readme/cards.png" alt="Phone screen further down the same brief: a row of insight cards. The first card says supported, 2 sources, then its title and why it matters. Below the row: 1 of 5, the six sources with 5 items each, and claim-seal, run again on the recorded answers: 6 of 6 checks agree."></td>
<td width="33%"><img src="docs/readme/card-open.png" alt="The first insight card, opened. It says supported, 2 sources. The words each article backs are underlined and numbered. Under Sources and seals, each article gets a row: the marked words, a fingerprint of the passage checked (or no passage located), and a link to open the article."></td>
</tr>
<tr>
<td>The finished brief: five insights from six feeds, read through one lens. "Checked 6/6" means every check was made.</td>
<td>Each insight is a card you can tap. Its label says how well the cited articles back it.</td>
<td>A card, opened. Underlined words are the ones an article backs. Each source row shows a fingerprint of the passage checked, or says none was located.</td>
</tr>
</table>

<sub>Screenshots of the demo in <code>docs/demo</code>, which replays a brief recorded on 2026-11-02. Every word in them is from that brief. (The page's own label says "the live edition"; this one is a replay.)</sub>

**This is Lensmith Composer. It reads a few feeds, writes a short brief through a lens you choose, and checks every claim against the article it cites before you read it.**

A lens is a few words of your own, like "what this means for small teams" or "where the risks are." Composer asks a model for five short insights through that lens. Each insight has to cite feed items by their exact titles. Then [claim-seal](https://github.com/lensmith-ai/claim-seal) checks each one. Is the cited title really in the feed? (Plain code, no model.) Does the article support the claim, partly support it, or not? (A model reads both.)

Each insight is printed with that label, a link to each article, and the exact words in our sentence that each article backs.

The private version of Composer writes the briefs I read. I click through to the cited articles to see that what a claim says is really there. This repo is the open version, so you can run it with your own key and your own feeds.

## Install it

Composer runs on macOS and Linux. Windows is not supported natively. On a Mac or a Linux computer, paste this in a terminal and press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh
```

It takes one to three minutes. It finds Python 3.10 or newer (or gets a private one), installs Composer into one folder,
`~/.lensmith-composer`, asks you one question (your Anthropic key; typing is hidden; press Enter to skip it and get the
recorded demo brief), starts the app, prints a line like `Open: http://127.0.0.1:8765/` and opens your browser. Next time,
type:

```sh
lensmith composer
```

The install asks nothing else. The extras are there when you want them, any time:

```sh
lensmith composer setup --reconfigure parser | provider (model) | checker | narration | schedule | port
```

`parser` reads article pages more cleanly, `provider` is your key and model, `checker` is the model that checks each
claim, `narration` is a spoken voice (Kokoro), `schedule` is a daily brief, and `port` is the port Composer uses. Each one
asks only about that part and changes nothing else.

Every file the installer downloads is checked against a SHA-256 written into the script, and you can download the
script and read it first. No sudo. The steps, what it changes on your computer, what to do if something fails, and how
to remove it: [docs/install.md](docs/install.md). On Windows, run it inside WSL2 (Ubuntu) or use the container ([docs/setup.md](docs/setup.md)); Composer is not tested on native Windows.

## Try it without installing

You need Python 3.10 or newer. Download or clone this repo, then work from its folder.

**See it work with no key and no install.** This replays a brief composed on 2026-11-02 from the six bundled feeds. It makes no network request and no model call:

```sh
python3 -m composer demo
```

**Compose your own.** Install in a virtual environment (`pip install .` fetches claim-seal from GitHub at a pinned commit and checks its SHA-256, so it needs the internet, but not git). Then set `ANTHROPIC_API_KEY` (from the Anthropic Console) and name the sources and your lens:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install .
export ANTHROPIC_API_KEY=...
composer compose --sources google-ai,deepmind --lens "system improvements" --out brief
```

Check the install with `composer demo --fast` and `python -m unittest discover -s tests -t tests`.

Composing prints each step, then the brief, and writes three files to the `--out` folder (without `--out`, a new folder under `briefs/`): `edition.json` (the brief), `check.json` (claim-seal's full result, with the sealed rows) and `index.html` (the brief as a web page). Any lens works: try `--lens "what this means for small teams"`. `--reading-level plain|standard|technical` sets how the brief is written (the level is a rule in the prompt, and `plain` is also checked on the answer). All the options: `composer compose --help`.

## Install the app from a download

The full app has the phone-width page, saved briefs, a daily brief and optional narration. The one command above installs it. If you have this repo's folder instead, run the install from it. `./setup.sh` goes into one folder, `~/.lensmith-composer`, and touches nothing else: no sudo, no global Python, no PATH change. (The one command also makes a `lensmith` shortcut at the end; see [docs/install.md](docs/install.md).)

```sh
./setup.sh
~/.lensmith-composer/bin/composer up        # prints "Open: http://127.0.0.1:8765/"; Cmd+click it in macOS Terminal
```

`./setup.sh` checks everything first and writes nothing until every check passes. Then it asks its questions one at a time. `composer doctor` checks the install. `composer uninstall` removes what setup made and keeps your briefs unless you add `--delete-data`. Every step, the refusals and what they mean, updates and backups: [docs/install-the-app.md](docs/install-the-app.md) and [docs/setup.md](docs/setup.md).

## Your model, your key

Composer calls the model with your own key. Nothing goes through any other service. The default is Anthropic (`claude-sonnet-5-5`). Set `COMPOSER_PROVIDER=openai` for any OpenAI-compatible endpoint. You can also name a separate model to check the claims. The key is read when each call is made, and never logged or printed. All the settings: [docs/models.md](docs/models.md).

## What a brief costs

7 model calls with the default settings: 1 to write, 1 to check each of the 5 insights, 1 to check the connection between sources. One live brief cost about $0.08 and took 29 seconds. Your cost moves with the number of sources, the model and any retry. How I worked that out: [docs/cost.md](docs/cost.md).

## Run it every day

1. **Your laptop.** Turn on the daily brief in setup. It runs while `composer up` runs and the computer is awake.
2. **Your own server with a domain.** Always on, readable anywhere. [docs/deploy-vps.md](docs/deploy-vps.md) walks through it, with a trial on your own computer first.
3. **No setup.** Sign up on [lensmith.ai](https://lensmith.ai) to get the daily brief by email.

There is also a static demo with no key and no server, and `composer serve`, a plain page. See [docs/ways-to-run.md](docs/ways-to-run.md).

## Your own sources

Any RSS or Atom feed, the Hacker News front page, or a news page with no feed. Add one with `composer sources add` (it writes `composer-sources.json` in the current folder), then use its id in `--sources`. `composer sources list` shows what's available. File format and safety rules: [docs/adding-sources.md](docs/adding-sources.md).

## What it does not do

- **It doesn't prove a claim is true.** It checks whether the cited source backs it. A claim that a wrong source supports still passes.
- **The checker is a model and can be wrong.** claim-seal keeps it honest where code can (a quote must be found exactly, a failed call is "not checked," never a pass). It can't make the reading correct. A separate checker model can catch mistakes the writer shares with itself. It doesn't make the check perfect.
- **A hostile feed can still try to steer a brief.** What Composer does about that, and where the limits are, is in [SECURITY.md](SECURITY.md).

## Before you publish a brief

If you run your own copy, you are the publisher of what it writes. Please:
- **Check each source's terms.** A public feed is an invitation to read, not a licence to republish. Some sites forbid automated reading or AI use.
- **Don't get around paywalls or log-ins.**
- **Link, credit and keep quotes short.** Composer's limits: at most 25 words per quote, two quotes per article, never the opening sentence.
- **Say it was written by AI.** Every brief page shows "AI-written summary; check the source." Keep it on anything you publish. In the EU, publishing AI-written text about matters of public interest without saying so can break the AI Act (Article 50), unless a person reviews it and takes editorial responsibility.
- **Think twice before publishing a claim marked "not supported,"** especially about a named person or company.
- **Fix and remove fast.** Give readers and publishers a way to reach you.

The rest, including what the six bundled feeds are and the `html-index` caveat: [docs/sources-and-your-responsibility.md](docs/sources-and-your-responsibility.md). This is guidance, not legal advice.

## Privacy and security

- No telemetry: no analytics, no crash reports, no update checks. Composer talks to the feeds you chose and the model provider you chose, with your key, and nothing else. (On a server, Caddy also talks to its certificate authority.)
- It stores the brief's own words, the cited titles and links, the verdicts and SHA-256 fingerprints of the passages checked. It doesn't store the articles' text. What is kept, and one exception: [docs/what-is-kept.md](docs/what-is-kept.md).
- Report a security problem privately with GitHub's "Report a vulnerability" button. Scope, response times and review history: [SECURITY.md](SECURITY.md).

## Releases you can check

Each release lists SHA256SUMS, a CycloneDX SBOM, and GitHub build-provenance attestations for every file the release workflow built (plus an SBOM attestation for the wheel and sdist) and for the container image. See [docs/verify-a-release.md](docs/verify-a-release.md) and [docs/releasing.md](docs/releasing.md).

## How it was built

Claude wrote the code and the tests, and drafted this page. I decide what Composer does, and I read the briefs the private version writes.

I don't review the code line by line, so here is what backs it instead:
- 810 offline tests ran on Python 3.10 and 3.13 in clean containers: 0 failed, 13 skipped (they need root, another account or a tool the image lacks). The commands in this README were run there.
- The installer was run 64 times across 27 scenarios (a download source down or slow, a file that fails its checksum, no Python, a folder it must refuse), and every run ended as it should. It was also installed from supplied files with the network switched off.
- A secret scanner (gitleaks) found nothing in any commit except one made-up marker string in a test, which its config allows. One test fails if private names, server paths or key shapes appear in the files or the history.
- A security review on 2026-11-01 attacked it as a hostile feed, a hostile web page and a hostile network would. What it found is fixed, and a second reviewer attacked the fixes ([SECURITY.md](SECURITY.md)). Both reviewers were AI models; no human has audited the code.
- One live brief, from a fresh install in a clean Python 3.13 container with a real Anthropic key and the default model: 7 calls, 29 seconds, about 8 cents. Every insight got a claim-seal verdict and the seal verified.

Not checked: the one-command installer has been run in Linux containers, not yet on a real Mac, and the browser tests use Chromium and the WebKit engine, not Safari itself. The OpenAI-compatible path has not been run live (it is tested against the documented request and reply shapes only). Treat Composer as a working experiment, and open an issue if something's off. Details: [docs/how-it-was-built.md](docs/how-it-was-built.md).

## Docs

| If you want | Read |
|---|---|
| the long version of how a brief is made | [docs/how-a-brief-is-made.md](docs/how-a-brief-is-made.md) |
| the one-command install, in detail | [docs/install.md](docs/install.md) |
| the app install from a download, step by step | [docs/install-the-app.md](docs/install-the-app.md), [docs/setup.md](docs/setup.md) |
| every model setting | [docs/models.md](docs/models.md) |
| the three ways to run it | [docs/ways-to-run.md](docs/ways-to-run.md), [docs/deploy-vps.md](docs/deploy-vps.md) |
| what a brief costs | [docs/cost.md](docs/cost.md) |
| adding sources | [docs/adding-sources.md](docs/adding-sources.md) |
| what is kept and privacy | [docs/what-is-kept.md](docs/what-is-kept.md) |
| your duties as a publisher | [docs/sources-and-your-responsibility.md](docs/sources-and-your-responsibility.md) |
| what is in the repo, and the tests | [docs/repo-map.md](docs/repo-map.md) |
| releases and checking them | [docs/verify-a-release.md](docs/verify-a-release.md), [docs/releasing.md](docs/releasing.md) |
| what was checked | [docs/how-it-was-built.md](docs/how-it-was-built.md) |

## Licence

MIT, see [LICENSE](LICENSE). claim-seal is MIT. See [THIRD-PARTY.md](THIRD-PARTY.md) for every
dependency, its version and its licence. The core install has no GPL code. Optional narration brings two parts under
GPL-3.0-or-later (the eSpeak NG library and phonemizer-fork); THIRD-PARTY.md says what that means if you pass a copy
on.
