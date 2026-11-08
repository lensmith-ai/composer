"""Lensmith Composer: read a few feeds, write a short brief through a lens you choose, and check
every claim against the article it cites before you read it.

    composer compose --sources google-ai,deepmind --lens "what this means for small teams"
    composer demo        # replays a recorded brief; no key, no network

The checking step is claim-seal (https://github.com/lensmith-ai/claim-seal), used as a pinned
dependency.
"""

__version__ = "0.2.0rc4"
