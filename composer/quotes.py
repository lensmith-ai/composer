"""The quote rule: a brief is written in the model's own words, and what it copies from an article stays short.

A quoted run is a run of words in the brief's own text (each insight, why it matters and detail, the connection's
headline and why, and the spoken transcript) that is copied word for word from one article, as the feed gave it.
Two kinds are found:

  marked     words inside quotation marks ("..." or “...”) that appear in the article: QUOTE_MIN_WORDS or more
  unmarked   COPY_MIN_WORDS or more words in a row that appear in the article without quotation marks; copying
             without quotation marks is still quoting

Words are compared in lower case, without punctuation. Naming an article's title is a citation, not a quote: a run
that lies wholly inside the title is not counted (the exact title is how a brief cites, and sources[].ref is never
scanned).

The rule, for one brief:

  1. a quoted run is at most MAX_QUOTE_WORDS (25) words;
  2. at most MAX_QUOTES_PER_ARTICLE (2) quoted passages from one article (the same words quoted twice, say in an
     insight and again in the transcript, are one passage);
  3. never the article's opening sentence: no quoted run takes the whole of it, or more than 12 words of it.

A short phrase shared with an article (a name, a product, a few words of its summary) is not counted: feed summaries
are often one sentence, and a brief that names what an article is about will share some of its words.

`check` returns the breaches. It reads the article text only in memory and returns counts and positions, never the
article's words, so its result can go into a receipt.
"""
from __future__ import annotations

import re

MAX_QUOTE_WORDS = 25
MAX_QUOTES_PER_ARTICLE = 2
QUOTE_MIN_WORDS = 3     # a marked quote shorter than this is a term, not a quote
COPY_MIN_WORDS = 13     # more than 12 words in a row, copied without quotation marks, is a quote

RULES = {"over_25_words": f"a quoted run is at most {MAX_QUOTE_WORDS} words",
         "over_2_per_article": f"at most {MAX_QUOTES_PER_ARTICLE} quotes from one article per brief",
         "opening_sentence": "never the article's opening sentence"}

_WORD = re.compile(r"\w+(?:'\w+)*")
_QUOTED = re.compile(r"\"([^\"]{1,2000})\"|“([^“”]{1,2000})”")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]*\s+")


def words(text: str) -> list[str]:
    return _WORD.findall((text or "").replace("’", "'").replace("‘", "'").lower())


def _word_spans(text: str) -> list[tuple[int, int]]:
    norm = (text or "").replace("’", "'").replace("‘", "'")
    return [m.span() for m in _WORD.finditer(norm)]


def brief_fields(brief: dict) -> list[tuple[tuple, str]]:
    """(where, text) for every part of the brief written in the model's own words. `where` is ("item", i, field),
    ("connection", field) or ("transcript",)."""
    out = []
    for i, it in enumerate(brief.get("items") or []):
        if not isinstance(it, dict):
            continue
        for key in ("insight", "why_it_matters"):
            if isinstance(it.get(key), str):
                out.append((("item", i, key), it[key]))
        for k, d in enumerate(it.get("detail") or []):
            if isinstance(d, str):
                out.append((("item", i, f"detail[{k}]"), d))
    conn = brief.get("connection")
    if isinstance(conn, dict):
        for key in ("headline", "why"):
            if isinstance(conn.get(key), str):
                out.append((("connection", key), conn[key]))
    if isinstance(brief.get("transcript"), str):
        out.append((("transcript",), brief["transcript"]))
    return out


def articles(sources: list, fetched: dict) -> list[dict]:
    """Every article the brief could quote: its source, position, title words, text words and opening sentence's
    length in words. `fetched` maps source id -> (items, receipt), as the pipeline holds it."""
    out = []
    for s in sources:
        items, receipt = fetched.get(s.id, ([], {}))
        if receipt.get("status") != "ok":
            continue
        for n, it in enumerate(items):
            text = it.get("description") or ""
            first = _SENTENCE_END.split(text.strip(), maxsplit=1)[0] if text.strip() else ""
            out.append({"source": s.id, "item": n, "title": it.get("title") or "",
                        "title_words": words(it.get("title") or ""), "words": words(text),
                        "opening_words": len(words(first))})
    return out


def _contains(hay: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return n > 0 and any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


def _runs(field: list[str], art: list[str], min_len: int, lo: int = 0, hi: int | None = None) -> list[tuple]:
    """Maximal runs of at least min_len words of field[lo:hi] that appear in art: (field start, end, art start)."""
    hi = len(field) if hi is None else hi
    if hi - lo < min_len or len(art) < min_len:
        return []
    index: dict[tuple, list[int]] = {}
    for j in range(len(art) - min_len + 1):
        index.setdefault(tuple(art[j:j + min_len]), []).append(j)
    found, i = [], lo
    while i + min_len <= hi:
        best = None
        for j in index.get(tuple(field[i:i + min_len]), ()):
            k = min_len
            while i + k < hi and j + k < len(art) and field[i + k] == art[j + k]:
                k += 1
            if best is None or k > best[1]:
                best = (j, k)
        if best is None:
            i += 1
            continue
        found.append((i, i + best[1], best[0]))
        i += best[1]
    return found


def find_runs(brief: dict, arts: list[dict]) -> list[dict]:
    """Every quoted run in the brief: where it is, which article, how many words, marked or not, and where in the
    article's text it starts (a word position, never the words)."""
    runs = []
    for where, text in brief_fields(brief):
        toks = words(text)
        spans = _word_spans(text)
        marked_ranges = []
        for m in _QUOTED.finditer(text.replace("’", "'").replace("‘", "'")):
            a, b = m.span()
            idx = [t for t, (s0, s1) in enumerate(spans) if s0 >= a and s1 <= b]
            if idx:
                marked_ranges.append((idx[0], idx[-1] + 1))
        for art in arts:
            seen = []
            for lo, hi in marked_ranges:
                for start, end, a_start in _runs(toks, art["words"], QUOTE_MIN_WORDS, lo, hi):
                    seen.append((start, end, a_start, True))
            for start, end, a_start in _runs(toks, art["words"], COPY_MIN_WORDS):
                if not any(s <= start and end <= e for s, e, _, _ in seen):
                    seen.append((start, end, a_start, False))
            for start, end, a_start, marked in seen:
                if _contains(art["title_words"], toks[start:end]):
                    continue  # the article's title, named: a citation, not a quote
                runs.append({"where": where, "source": art["source"], "article": art["item"],
                             "words": end - start, "marked": marked, "article_start": a_start,
                             "article_end": a_start + (end - start), "opening_words": art["opening_words"]})
    return runs


def _passages(runs: list[dict]) -> list[list[dict]]:
    """Runs of one article grouped into passages: runs whose article words overlap are one passage."""
    groups: list[list[dict]] = []
    for r in sorted(runs, key=lambda r: (r["article_start"], r["article_end"])):
        if groups and r["article_start"] < max(x["article_end"] for x in groups[-1]):
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups


def check(brief: dict, sources: list, fetched: dict) -> dict:
    """{"runs": count, "breaches": [{"where", "rule", "source", "article", "words"}]}; no article text."""
    arts = articles(sources, fetched)
    runs = find_runs(brief, arts)
    breaches = []
    for r in runs:
        if r["words"] > MAX_QUOTE_WORDS:
            breaches.append({"where": r["where"], "rule": "over_25_words", "source": r["source"],
                             "article": r["article"], "words": r["words"]})
        lede = r["opening_words"]
        overlap = max(0, min(r["article_end"], lede) - r["article_start"])
        if lede and overlap >= min(COPY_MIN_WORDS, lede):
            breaches.append({"where": r["where"], "rule": "opening_sentence", "source": r["source"],
                             "article": r["article"], "words": overlap})
    by_article: dict[tuple, list[dict]] = {}
    for r in runs:
        by_article.setdefault((r["source"], r["article"]), []).append(r)
    order = {id(r): n for n, r in enumerate(runs)}
    for (sid, n), rs in by_article.items():
        groups = _passages(rs)
        if len(groups) > MAX_QUOTES_PER_ARTICLE:
            # keep the passages the brief quotes first; the later ones are the breach
            groups.sort(key=lambda g: min(order[id(r)] for r in g))
            for g in groups[MAX_QUOTES_PER_ARTICLE:]:
                for r in g:
                    breaches.append({"where": r["where"], "rule": "over_2_per_article", "source": sid,
                                     "article": n, "words": r["words"]})
    return {"runs": len(runs), "passages": sum(len(_passages(rs)) for rs in by_article.values()),
            "breaches": breaches}


def describe(breach: dict, arts_by_key: dict | None = None) -> str:
    """One plain sentence for the writer's repair request (names the part and the article's title, never its text)."""
    w = breach["where"]
    part = (f"item {w[1] + 1} ({w[2]})" if w[0] == "item" else
            f"the connection ({w[1]})" if w[0] == "connection" else "the transcript")
    title = ""
    if arts_by_key:
        art = arts_by_key.get((breach["source"], breach["article"]))
        title = f" from \"{art['title'][:120]}\"" if art and art.get("title") else ""
    what = {"over_25_words": f"copies {breach['words']} words in a row{title} (at most {MAX_QUOTE_WORDS})",
            "over_2_per_article": f"is a third quote{title} (at most {MAX_QUOTES_PER_ARTICLE} per article)",
            "opening_sentence": f"copies the opening sentence{title}"}[breach["rule"]]
    return f"{part} {what}"


def drop(brief: dict, breaches: list[dict]) -> dict:
    """The brief without the parts that broke the rule: those insights, the connection, or the transcript.
    Returns a receipt note: what was dropped and why (positions and rule names, no text)."""
    items_out = sorted({b["where"][1] for b in breaches if b["where"][0] == "item"})
    conn_out = any(b["where"][0] == "connection" for b in breaches)
    transcript_out = any(b["where"][0] == "transcript" for b in breaches)
    rules: dict[str, list[str]] = {}
    for b in breaches:
        key = (f"item {b['where'][1] + 1}" if b["where"][0] == "item" else b["where"][0])
        rules.setdefault(key, [])
        if b["rule"] not in rules[key]:
            rules[key].append(b["rule"])
    brief["items"] = [it for i, it in enumerate(brief.get("items") or []) if i not in items_out]
    if conn_out:
        brief.pop("connection", None)
    if transcript_out:
        brief.pop("transcript", None)
    return {"dropped_items": [i + 1 for i in items_out], "dropped_connection": conn_out,
            "dropped_transcript": transcript_out, "rules": rules}
