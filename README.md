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

**Lensmith Composer reads the feeds you pick, writes a short brief through a lens you choose, and checks each claim against the article it cites.** It is for people who follow a few blogs or news feeds and want a daily summary where every claim shows how well its source backs it. You run it on your own computer, with your own model key.

A lens is a few words of your own, like "what this means for small teams" or "where the risks are." Each insight in the brief cites feed items by their exact titles. Then [claim-seal](https://github.com/lensmith-ai/claim-seal) checks each one. Is the cited title really in the feed? (Plain code, no model.) Does the article back the claim, partly back it, or not? (A model reads both.) Each insight is printed with that label, a link to each article, and the exact words that each article backs.

I use the private version of Composer to write the briefs I read. This repository is the open version.

## Install it

Composer runs on macOS and Linux. On Windows, use WSL2 (Ubuntu) or the container ([docs/setup.md](docs/setup.md)). It is not tested on native Windows.

On a Mac or a Linux computer, paste this in a terminal and press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh
```

It takes one to three minutes. It finds Python 3.10 or newer (or gets a private copy) and puts Composer in one folder, `~/.lensmith-composer`. It asks you one question about Composer: your Anthropic key. Typing is hidden. Press Enter to skip it and you get the recorded demo brief. Then it starts the app, prints a line like `Open: http://127.0.0.1:8765/`, and opens your browser.

At the end it adds a short command named `lensmith`. That is a link in `~/.local/bin` if you have that folder on your PATH. If not, it asks first, and then adds three lines to your shell profile. It tells you what it changed, and `lensmith composer uninstall` takes it away. Next time, type:

```sh
lensmith composer
```

The install asks nothing else about Composer. These extras are there when you want them:

```text
lensmith composer setup --reconfigure parser | provider (model) | checker | narration | schedule | port
```

Pick one part. For example, `lensmith composer setup --reconfigure provider` asks again for your key and model. `parser` reads article pages more cleanly. `provider` is your key and model. `checker` is a second model that checks each claim. `narration` is a spoken voice (Kokoro). `schedule` is a daily brief. `port` is the port Composer uses. Each one asks only about that part and changes nothing else.

Every file the installer downloads is checked against a pinned SHA-256, and you can download the script and read it before you run it. It needs no sudo. The steps, what it changes, what to do if it fails, and how to remove it (`lensmith composer uninstall`) are in [docs/install.md](docs/install.md).

## Try it without installing

You need Python 3.10 or newer. Download or clone this repository and work from its folder.

**See it work, with no key and no install.** This replays the brief recorded on 2026-11-02 from the six bundled feeds. It makes no network request and no model call:

```sh
python3 -m composer demo
```

**Compose your own.** Install in a virtual environment. `pip install .` fetches claim-seal from GitHub at a pinned commit and checks its SHA-256, so it needs the internet but not git. Then set `ANTHROPIC_API_KEY` (from the Anthropic Console), and name your sources and your lens:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install .
export ANTHROPIC_API_KEY=...
composer compose --sources google-ai,deepmind --lens "system improvements" --out brief
```

Composing prints each step, then the brief, and writes its files to the `--out` folder: `edition.json` (the brief), `check.json` (claim-seal's full result, with the sealed rows), `index.html` (the brief as a web page), `receipts.json` (what was read and which model calls were made) and, when there is one, `transcript.txt`. Without `--out`, it makes a new folder under `briefs/`. Any lens works. `--reading-level plain|standard|technical` sets how the brief is written. All the options: `composer compose --help`.

To check your install, run `composer demo --fast` and `python -m unittest discover -s tests -t tests`.

## Install the app from a download

If you have this repository's folder instead of the one command, run `./setup.sh`. It uses one folder, `~/.lensmith-composer`, and touches nothing else: no sudo, no global Python, no PATH change. Then `~/.lensmith-composer/bin/composer up` starts the app. The steps and the refusals are in [docs/install-the-app.md](docs/install-the-app.md) and [docs/setup.md](docs/setup.md).

## How it works

1. You pick sources (any RSS or Atom feed, the Hacker News front page, or a news page with no feed) and a lens.
2. Composer fetches the feeds. That costs nothing, and is usually one request per feed.
3. One model call writes the insights. Each must cite feed items by exact title. If the answer cannot be used, Composer asks once more.
4. claim-seal checks every insight, one model call each, plus one for the connection the brief draws between sources. A quote counts only if it is found word for word in the article.
5. The page shows each insight with its label (supported, partly supported or not), its sources, and the words each source backs.

The long version: [docs/how-a-brief-is-made.md](docs/how-a-brief-is-made.md).

## Your model, your key

Composer calls the model with your own key. Nothing goes through any other service. The default is Anthropic (`claude-sonnet-5-5`). Set `COMPOSER_PROVIDER=openai` for any OpenAI-compatible endpoint. You can name a separate model to check the claims. The key is read when each call is made, and never logged or printed. All the settings: [docs/models.md](docs/models.md).

## What a brief costs

A brief with the default settings makes 7 model calls: 1 to write, 5 to check the insights, and 1 to check the connection. A retry makes 8. One live brief on 2026-11-01 used 14,334 input and 4,679 output tokens, which cost about $0.08 at Anthropic's published Claude Sonnet 5.5 prices ($2 and $10 per million tokens, read 2026-11-01). It took 29 seconds. Your cost moves with the number of sources, the model and any retry. The working is in [docs/cost.md](docs/cost.md).

## Run it every day

1. **Your laptop.** Turn on the daily brief in setup. It runs while `composer up` runs and the computer is awake.
2. **Your own server with a domain.** Always on, readable anywhere. [docs/deploy-vps.md](docs/deploy-vps.md) walks through it, with a trial on your own computer first.
3. **No setup (coming soon).** A daily brief by email, with nothing to install. Watch [lensmith.ai](https://lensmith.ai) for the waitlist.

There is also a static demo with no key and no server, and `composer serve`, a plain page. See [docs/ways-to-run.md](docs/ways-to-run.md).

## Your own sources

Add one with `composer sources add --id ID --label LABEL --kind rss-or-atom --url URL`. It writes `composer-sources.json` in the current folder. Then use its id in `--sources`. `composer sources list` shows what is available. The file format and the safety rules: [docs/adding-sources.md](docs/adding-sources.md).

## What it does not do

- **It does not prove a claim is true.** It checks whether the cited article backs it. A claim that a wrong source supports still passes.
- **The checker is a model and can be wrong.** claim-seal keeps it honest where code can: a quote must be found exactly, and a failed call is "not checked," never a pass. It cannot make the reading correct. A second checker model can catch mistakes the writer shares with itself. It does not make the check perfect.
- **A hostile feed can still try to steer a brief.** What Composer does about that, and where the limits are, is in [SECURITY.md](SECURITY.md).

## Before you publish a brief

If you run your own copy, you are the publisher of what it writes. Please:

- **Check each source's terms.** A public feed is an invitation to read, not a licence to republish. Some sites forbid automated reading or AI use.
- **Do not get around paywalls or log-ins.**
- **Link, credit and keep quotes short.** Composer's limits: at most 25 words per quote, two quotes per article, never the opening sentence.
- **Say it was written by AI.** Every brief page shows "AI-written summary; check the source." Keep it on anything you publish. In the EU, publishing AI-written text about matters of public interest without saying so can break the AI Act (Article 50), unless a person reviews it and takes editorial responsibility.
- **Think twice before publishing a claim marked "not supported,"** especially about a named person or company.
- **Fix and remove fast.** Give readers and publishers a way to reach you.

The rest, including what the six bundled feeds are: [docs/sources-and-your-responsibility.md](docs/sources-and-your-responsibility.md). This is guidance, not legal advice.

## Privacy and security

- **No telemetry.** No analytics, no crash reports, no update checks. Composer talks to the feeds you chose and the model provider you chose, with your key, and nothing else. (On a server, Caddy also talks to its certificate authority.)
- **What is kept.** The brief's own words, the cited titles and links, the verdicts, and SHA-256 fingerprints of the passages checked. Not the articles' text. One exception is described in [docs/what-is-kept.md](docs/what-is-kept.md).
- **Your text leaves your computer** when Composer sends feed items to your model provider. That is how it works.
- **To report a security problem,** use GitHub's "Report a vulnerability" button. Scope, response times and review history: [SECURITY.md](SECURITY.md).

## Releases you can check

Each release lists SHA256SUMS, a CycloneDX SBOM, and GitHub build-provenance attestations for every file the release workflow built, and for the container image. See [docs/verify-a-release.md](docs/verify-a-release.md) and [docs/releasing.md](docs/releasing.md).

## How this was built

I designed Composer and I decide what it does. I did not write the code by hand. My team of AI agents did: Sal, which runs on Hermes, and my agent command center, which uses several models, including Claude and OpenAI's Codex and GPT models.

I have not read every line of the code. I do review what it does and how it behaves, and I use the private version for my own briefs.

Here is what guards it, in place of me reading the code:

- **837 automated tests**, which use invented feeds and scripted model replies, so they need no network and no key. They were last run on 2026-11-09 on Python 3.12: all pass, 4 skipped. CI runs them on Ubuntu and macOS, on Python 3.10 and 3.13.
- **The installer is tested on its own.** A fault suite ran it 64 times across 27 scenarios (a download source down or slow, a file that fails its checksum, no Python, a folder it must refuse). Every run ended as it should. CI also runs the real install on macOS, and it passed on my own Mac on 2026-11-09 (built from commit 926837d).
- **Browser tests** run the demo pages and the app page in Chromium and WebKit at three screen widths.
- **A secret scan** (gitleaks) found nothing in any commit except one made-up marker string in a test, which its config allows. One test fails if private names, server paths or key shapes appear in the files or the history.
- **A security review** on 2026-11-01 attacked Composer as a hostile feed, a hostile web page and a hostile network would. What it found is fixed. A second review attacked the fixes ([SECURITY.md](SECURITY.md)). Both reviewers were AI models. No human has audited the code.
- **One live brief** from a fresh install, with a real Anthropic key and the default model: 7 calls, 29 seconds, about 8 cents. Every insight got a claim-seal verdict, and the seal verified.

I have not run the OpenAI-compatible path live. It is tested only against the documented request and reply shapes. Treat Composer as a working experiment, and open an issue if something looks wrong. More detail: [docs/how-it-was-built.md](docs/how-it-was-built.md).

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
| what is kept, and privacy | [docs/what-is-kept.md](docs/what-is-kept.md) |
| your duties as a publisher | [docs/sources-and-your-responsibility.md](docs/sources-and-your-responsibility.md) |
| what is in the repository, and the tests | [docs/repo-map.md](docs/repo-map.md) |
| releases, and how to check them | [docs/verify-a-release.md](docs/verify-a-release.md), [docs/releasing.md](docs/releasing.md) |
| what has been checked | [docs/how-it-was-built.md](docs/how-it-was-built.md) |

## Contributing and licence

Found a bug or a wrong result? Open an issue; there are templates for a bug, an idea and a demo that does not match. Issues are welcome. Pull requests are not merged: I have not read every line of this code, and I would rather not take changes I cannot check. If you have a fix, describe it in an issue. See [CONTRIBUTING.md](CONTRIBUTING.md). Report a security problem privately, not in an issue (see above).

MIT, see [LICENSE](LICENSE). claim-seal is MIT too. [THIRD-PARTY.md](THIRD-PARTY.md) lists every dependency, its version and its licence. The core install has no GPL code. The optional narration brings two parts under GPL-3.0-or-later (the eSpeak NG library and phonemizer-fork). THIRD-PARTY.md says what that means if you pass a copy on.
