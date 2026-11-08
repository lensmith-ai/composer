# How a brief is made

The long version. The short version is in the [README](../README.md).

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
