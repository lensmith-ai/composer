# What a brief costs

**7 model calls** with the default settings: 1 to write the brief, 1 to check each of the 5
insights, and 1 to check the connection the brief draws between sources. If the first answer
cannot be used (not valid JSON, or a citation outside the chosen sources), Composer asks once
more, which makes 8. Fetching a feed costs nothing; it is one request each.

**Measured: about $0.08 per brief** with the default model. One live brief (the compose command in the [README quickstart](../README.md#try-it-without-installing),
Google AI blog and Google DeepMind blog, 5 items each, on 2026-11-01) made 7 calls to
`claude-sonnet-5-5` and the API reported 14,334 input and 4,679 output tokens: 1,910 in and
2,594 out to write the brief, and about 2,000 to 2,300 in and 300 to 450 out for each of the
6 checks. At Anthropic's published prices for Claude Sonnet 5.5, $2 per million input tokens
and $10 per million output tokens ([pricing page](https://platform.claude.com/docs/en/about-claude/pricing),
read 2026-11-01), that is $0.0287 + $0.0468 = **$0.0755**. It took 29 seconds from start to finish.
Your cost moves with the number of sources and items, the model, and whether a retry is needed;
each brief's `edition.json` records its own calls and the token counts the API reported.

**A separate checker is optional.** By default the model that writes the brief also checks it. You can name a
second model for the checks (`composer setup` asks; or the `COMPOSER_CHECKER_*` settings in [models.md](models.md)): the writer then
makes the 1 write call and the checker the 6 check calls, each billed at its own model's price, and the brief's
receipts list the two models separately. A different model can catch mistakes the writer shares with itself; it
does not make the check infallible.

The recorded demo brief was written and checked by gpt-5.6-terra (an OpenAI model) on a
flat-rate plan, with the same pipeline but not through this repository's API layer: 7 calls,
41,111 input and 5,183 output tokens. Its token counts are not comparable with Claude's.
