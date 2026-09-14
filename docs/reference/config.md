# config.toml

`~/.config/genimg/config.toml` holds defaults and auth profiles. `genimg setup` writes it;
`genimg config show` prints it; `genimg config edit` opens it in `$EDITOR`. Override the
directory with `GENIMG_CONFIG_HOME`.

```toml
default_model        = "gdm:nb2"   # alias or canonical id; omit to require -m every run
default_quality      = "medium"    # OpenAI: low | medium | high | auto | xhigh | max
default_aspect_ratio = "16:9"      # applied only when the selected model supports it
default_resolution   = "2K"        # 512 | 1K | 2K | 4K, same rule

[profiles.google]                  # NAME is yours; --profile NAME selects it
provider = "google"                # google | openai | codex
auth     = "vertex_adc"            # one of the provider's modes (genimg auth --modes)
project  = "my-gcp-project"        # non-secret settings the mode understands
region   = "global"

[profiles.work]
provider    = "openai"
auth        = "azure"
endpoint    = "https://myres.openai.azure.com"
api_version = "2025-04-01-preview"

[profiles.codex]
provider = "codex"
auth     = "subscription"
```

## Keys

| Key | Type | Meaning |
| --- | --- | --- |
| `default_model` | string | Used when `-m` is omitted. There is no built-in default. |
| `default_quality` | string | OpenAI quality when `-q` is omitted. |
| `default_aspect_ratio` | string | Aspect when `-a` is omitted, if the model supports it. |
| `default_resolution` | string | Resolution when `-r` is omitted, if the model supports it. |
| `profiles.<name>.provider` | string | `google`, `openai` or `codex`. |
| `profiles.<name>.auth` | string | A mode of that provider; see below. |
| `profiles.<name>.project` | string | Google Vertex: GCP project. Falls back to `GOOGLE_CLOUD_PROJECT`, the service-account JSON, then `gcloud`. |
| `profiles.<name>.region` | string | Google Vertex: location (default `global`, or the model's registry region). |
| `profiles.<name>.endpoint` | string | OpenAI Azure: resource URL. Required for `azure`. |
| `profiles.<name>.api_version` | string | OpenAI Azure: api-version (default `2025-04-01-preview`). |

Secrets never go in this file. API keys and service-account paths are read from the
environment; the wizard offers to add `export` lines to your shell rc.

## Auth modes

| Provider | `auth` | Credentials read from env |
| --- | --- | --- |
| google | `direct` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| google | `vertex` | `GOOGLE_APPLICATION_CREDENTIALS` (or `CLAUDE_GCP_CRED`) |
| google | `vertex_adc` | gcloud application-default credentials |
| openai | `native` | `OPENAI_API_KEY` |
| openai | `azure` | `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY`, plus `AZURE_OPENAI_ENDPOINT` when the profile has no `endpoint` |
| codex | `subscription` | the Codex CLI's own `codex login` |

## How a profile is chosen

1. `--profile NAME` (must belong to the model's provider; a misspelt name is an error even
   on `--dry-run`).
2. `--auth MODE` forces an OpenAI mode for one run, reusing that mode's settings from a
   configured profile if there is one. `--profile` wins if both are given.
3. The first `[profiles.*]` table declared for the provider.
4. Environment auto-detection in the provider's declared mode order (`genimg auth --modes`).

`genimg auth` shows which of these resolved in its `source` column.

## Migration from config.json

Versions before 0.1.0 kept a `config.json` with an `enabled_providers` list. On first load
genimg converts it to `config.toml` (`google_vertex_adc` → `[profiles.google] auth = "vertex_adc"`,
`gcp_project` → `project`, `openai_base_url` → `endpoint`, and so on) and renames the old
file to `config.json.migrated`. Nothing is deleted.
