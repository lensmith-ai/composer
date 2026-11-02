# Adding your own sources

Yes, you can read any source you like. Composer ships with six public feeds (the Google AI, Google
DeepMind, Hugging Face, Microsoft Research and PyTorch blogs, and arXiv cs.AI). Your own sources go in a file next to where you run Composer,
`composer-sources.json`. Composer reads the bundled list first, then your file. An entry in
your file with the same id as a bundled one replaces it.

You can also keep the file somewhere else and point to it with `--sources-file FILE` or the
`COMPOSER_SOURCES` environment variable.

## From the app page

In the app (`composer up` or `composer serve`), open the menu, then **Sources**, then **Add a source**. Paste the
address of a blog or a feed and tap **Check the address**. Composer reads that address once, then every RSS or Atom
feed the page advertises, then a few usual feed addresses under it (`/feed/`, `/rss.xml`, `/blog/feed/` and so on),
and lists every feed that answered with its newest titles. It picks none for you: a site often offers its whole-site
feed, a comments feed and the blog's own feed side by side, and only the titles tell them apart. Comment feeds are
marked and listed last; addresses that gave exactly the same items are shown once, on the narrowest address. Tap the
one you recognise, give it a name, and **Add to my sources**: Composer reads that feed once more, adds it to your
sources file with a note of when and from which address, and it is in the picker at once, with no restart.

The check uses the same guarded fetch as a brief (below): https only (a pasted `http://` address is tried as
`https://`; if only plain http answers, the page says so and why: a feed read without encryption can be changed on
its way, and the claim check would then vouch for the changed text), public addresses only, checked again on the address actually connected to and after every redirect, no
proxies, at most 2 MB a request, and one 60-second limit for the whole check. It makes at most 14 requests, and only
one check runs at a time. Checking a full entry (any kind, including a news page with up to 40
candidate articles) is held to 60 seconds, 24 requests and 8 MB read in all.

## Packages

The source picker also shows packages: a named starting set of sources you can tap to tick them all, then change.
Composer ships one, **AI labs** (two of the bundled feeds: the Google AI and Google DeepMind blogs). Add your own in
`composer-packages.json` next to your sources file (with `composer up`, `packages.json` in the data folder's current
generation), in this shape:

```json
{
  "schema": "source-packages/v1",
  "packages": [
    {"package_id": "my-morning", "label": "My morning", "description": "The feeds I read first.",
     "provenance": "added by me", "source_ids": ["google-ai", "my-blog"],
     "selection_policy": {"unavailable_members": "refuse", "paid_requires_confirmation": false,
                          "offline_trial_eligible": false}}
  ]
}
```

`unavailable_members` is `refuse` (the chip is off while any of its sources is unavailable) or
`skip_with_disclosure` (it ticks the rest and says what it left out). A package that names a source that is not in
your sources, or a hidden one, is set aside and the Sources page says why; the others still load. The file is read
again when it changes. A package is only a suggestion: the brief uses the sources that are ticked when you compose.

## The quick way

```sh
composer sources add --id my-blog --label "My favourite blog" --url https://example.org/feed.xml
composer sources list
```

Then use it like any other source: pass `--sources my-blog,deepmind` to `composer compose`.

Before you spend a model call, check that a source works. This fetches it once, with no key
and no model, and prints what it found (here, a bundled feed):

```sh
composer sources check deepmind
```

## The three kinds of source

Every source names one of three fixed readers by `kind`. A sources file is data: it can pick a
reader, but it can never run code.

| kind | use it for | what is fetched for one brief |
|---|---|---|
| `rss-or-atom` | any blog, newsletter or news site with a feed (RSS 2.0, RSS 1.0 or Atom) | one request for the feed |
| `hn-json-api` | the Hacker News front page | one request for the list, then one per story (up to `max_items`) |
| `html-index` | a news page with no feed | one request for the page, then one per article (up to `max_items`) |

Tips for finding a feed: try the site's address followed by `/feed`, `/rss`, `/rss.xml` or
`/atom.xml`, or look for a feed link in the page's source.

## The file format

`examples/composer-sources.example.json` has one of each kind:

```json
{
  "schema": "composer-sources/v1",
  "sources": [
    {"id": "my-blog", "label": "My favourite blog", "kind": "rss-or-atom",
     "url": "https://example.org/feed.xml", "max_items": 5},
    {"id": "hn", "label": "Hacker News", "kind": "hn-json-api",
     "url": "https://hacker-news.firebaseio.com/v0/topstories.json", "max_items": 10},
    {"id": "example-news", "label": "Example newsroom", "kind": "html-index",
     "url": "https://example.org/news/", "max_items": 5,
     "discovery": {"allowed_hosts": ["example.org"], "allowed_path_prefixes": ["/news/"],
                   "max_candidates": 20}}
  ]
}
```

The rules each entry must meet (Composer refuses the file and says why otherwise):

- `id`: 1 to 40 lowercase letters, digits and dashes. This is what you type after `--sources`.
- `label`: 1 to 60 characters. This is the name readers see next to each citation.
- `url`: an `https://` address with no `user:password@` part, on a public web site. An address on
  this machine (`localhost`, `127.0.0.1`) or a private network (such as `10.x`, `192.168.x` or
  `169.254.169.254`) is refused, here and again at fetch time on the address actually connected
  to, including after a redirect. To read a feed on your own network on purpose, set
  `COMPOSER_ALLOW_PRIVATE_FETCH=1`.
- `max_items`: 1 to 20 (default 5). More items means a longer prompt, not more model calls.
- `discovery` (only for `html-index`): the hosts and path prefixes an article link must be on.
  Composer checks every link against these before it fetches anything, and keeps at most
  `max_candidates` (1 to 40). This stops a page from sending Composer anywhere else.
- `extraction_tier` (only for `html-index`, optional): `native` is the default parser with no
  extra package. `trafilatura` uses the optional article parser (say yes to it in `composer setup`, or run
  `composer setup --reconfigure parser`; it installs from a hash-locked file). When it is not installed, the pages are read with the built-in
  parser (text only), and the brief's receipt says which parser read each source (`fetch_tier`, `fetch_tiers`) and
  that the optional one was missing.

Every fetch is https only (a redirect to `http://` is refused), follows at most 5 redirects,
reads at most 2 MB and stops after 60 seconds in total, however slowly the answer arrives.
Proxy settings such as `HTTPS_PROXY` are not used for these fetches.
- `note` (optional): your own reminder of what the source is.

## What Composer keeps from a source

For each item: the title, the link, the publication date and up to 800 characters of
description. Text that looks like an instruction to a model is broken up, and hidden characters
are removed, before anything reaches the prompt. The finished brief keeps the titles and links
of what it cites, not the descriptions or the article text (its sentences may quote a few words). If you want to see what was
read, `composer compose --keep-sources` saves it next to the brief; keep that file to yourself.

Respect each site's terms. Some sites block automated readers; `composer sources check` will
show the error if so. Before you share briefs made from a source, read
[Sources and your responsibility](../README.md#sources-and-your-responsibility): check its terms and `robots.txt`,
never add a source behind a paywall or a log-in, keep quotes short, and keep the AI note on what you publish.
