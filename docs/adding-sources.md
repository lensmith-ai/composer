# Adding your own sources

Yes, you can read any source you like. Composer ships with two public feeds (the Google AI blog
and the Google DeepMind blog). Your own sources go in a file next to where you run Composer,
`composer-sources.json`. Composer reads the bundled list first, then your file. An entry in
your file with the same id as a bundled one replaces it.

You can also keep the file somewhere else and point to it with `--sources-file FILE` or the
`COMPOSER_SOURCES` environment variable.

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
show the error if so.
