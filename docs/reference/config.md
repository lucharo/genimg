# config.toml

`~/.config/genimg/config.toml` holds your defaults and auth profiles.

| To | Run |
| --- | --- |
| Create it | `genimg setup` |
| Print it | `genimg config show` |
| Open it in `$EDITOR` | `genimg config edit` |
| Keep it elsewhere | `export GENIMG_CONFIG_HOME=DIR` |

```toml
default_model        = "gdm:nb2"   # used when --model is omitted
default_quality      = "medium"
default_aspect_ratio = "16:9"      # skipped if the model can't use it
default_resolution   = "2K"        # same

[profiles.google]                  # the name is yours: --profile google
provider = "google"
auth     = "vertex_adc"
project  = "my-gcp-project"

[profiles.work]
provider = "openai"
auth     = "azure"
endpoint = "https://myres.openai.azure.com"
```

Keys and service-account paths stay in your environment, never in this file.

## Auth modes

| `provider` | `auth` | Route | Credentials | Settings |
| --- | --- | --- | --- | --- |
| `openai` | `direct` | OpenAI API | `OPENAI_API_KEY` | |
| `openai` | `azure` | Azure OpenAI | `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY` | `endpoint`, `api_version` |
| `google` | `direct` | Gemini API | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | |
| `google` | `vertex` | Vertex AI | `GOOGLE_APPLICATION_CREDENTIALS` or `CLAUDE_GCP_CRED` | `project`, `region` |
| `google` | `vertex_adc` | Vertex AI | `gcloud auth application-default login` | `project`, `region` |
| `codex` | `subscription` | ChatGPT plan | `codex login` | |

Without `endpoint`, genimg reads `AZURE_OPENAI_ENDPOINT`. Without `project`, it reads
`GOOGLE_CLOUD_PROJECT`, then the service-account JSON's `project_id` (`vertex`) or gcloud's active
project (`vertex_adc`).

## Which profile runs

- `genimg auth` shows the winner in its `source` column.

The first match wins:

1. `--profile NAME`
2. `--auth MODE` (OpenAI), reusing that mode's profile settings
3. The provider's first profile
4. Environment auto-detection
