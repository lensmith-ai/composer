# Bring your own model

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
| `COMPOSER_CHECKER_PROVIDER` | optional: `anthropic` or `openai` for a separate model that checks the claims (unset: the writer checks) |
| `COMPOSER_CHECKER_MODEL`, `COMPOSER_CHECKER_OPENAI_BASE_URL` | that checker's model id and, for `openai`, its endpoint |
| `COMPOSER_CHECKER_API_KEY` | that checker's key (never the writer's key) |

`composer setup` offers a short list of model ids for the service you choose (`composer/data/models.json`;
`claude-sonnet-5-5` stays the default), makes one tiny test call per key that says plainly what is wrong if it
fails, and can name a separate model to check the claims ([docs/setup.md](setup.md)).

The key is read when each call is made. It is never logged or printed. The command line never stores it; the
installed app stores it only if you give it to `composer setup`, in a file only you can read (mode 0600).
