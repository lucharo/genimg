# No built-in default model

**Status:** accepted

genimg ships **no** hardcoded default model. When `-m` is omitted and no `default_model` is saved in config, the CLI errors with guidance (pass `-m`, or set one via `genimg models set-default` / `genimg setup`) instead of silently generating with a model the user never chose.

Why: as a public tool, a hardcoded default that points at a preview/allowlisted id (e.g. a `-preview` Gemini image model) would `404` on a fresh key, so the very first `genimg "…"` fails out of the box. Requiring an explicit choice trades one-command friction for zero surprise. `genimg setup` offers to set a default so the guided path still ends with a working zero-flag command.

Note for future contributors: the absence of a default is deliberate — do not re-introduce a hardcoded fallback.
