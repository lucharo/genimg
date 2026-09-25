# Design decisions

Four choices shape the code. Keep them unless you mean to change the decision itself.

## No built-in default model

Without `--model` or a saved default, genimg stops and says how to pick a model. A hardcoded default
could name a model a fresh key cannot reach, and the very first command would fail. `genimg setup`
offers to save a default, so the guided path still ends in a command with no flags.

## No organisation-specific defaults

genimg never falls back to a hardcoded GCP project or credential. The Vertex project comes from
`--project`, then the profile's `project` setting, then `GOOGLE_CLOUD_PROJECT`, then the
service-account file or gcloud. If none is set, genimg says what to set. A hardcoded fallback would
be wrong for every user but its author.

## Providers are plugins, auth lives in profiles

Each backend is a `Provider` that owns its auth modes, model capabilities, prices and model-id
inference, so the CLI, the grid and Draw Studio read the same tables. A few provider-name branches
remain outside the providers: OpenAI pricing in `cost.py`, the OpenAI `--mode batch` error in
`cli.py`, the suggested model in `setup.py` and Draw Studio's offline fallback in `draw.py`.

Each provider and auth mode pair is an `AuthProfile`. Users pin one as a `[profiles.NAME]` table in
`config.toml`, which never holds secrets. Without one, genimg uses the first mode whose detection
succeeds: an API key in the environment, a gcloud ADC token, or a Codex login.

The full records are in `internal/adr/` in the repository.

## Skills install through `npx skills`

`npx skills add lucharo/genimg` is the only install path; `genimg skills` prints that command and
`genimg skills path` shows where the bundled copies live. genimg once had its own install, update
and uninstall verbs, but they managed the same directory as the user's own skills, such as
`genimg-preferences`, and could delete them. The skills CLI installs per agent and per project, and
leaves unrelated skills alone.
