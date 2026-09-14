# Authentication

Run the wizard once. It detects credentials already in your environment, walks you through
getting any that are missing, runs a free live preflight, and saves a profile only when that
preflight passes:

```bash
genimg setup
```

```text
genimg setup — detect → fetch → validate → save

Google · Gemini
? Pick a Google · Gemini auth path (or skip):
  ✓  Direct API (Gemini key)              ·  GEMINI_API_KEY=AIz… in env
  ✗  Vertex (service account JSON)        ·  needs GOOGLE_APPLICATION_CREDENTIALS or CLAUDE_GCP_CRED
  ✗  Vertex (gcloud user creds, ADC)      ·  run `gcloud auth application-default login`
     Skip Google · Gemini
```

Secrets stay in your environment (the wizard offers to append an `export` line to your shell
rc). Only non-secret settings such as an Azure endpoint or a GCP project are written to
[config.toml](../reference/config.md).

## Automatic detection

With no saved profile, genimg picks the first mode whose environment variables are present,
in the order shown here. `genimg auth --modes` prints the same table from the installed
version.

| Provider | Auth mode | Environment variables | Profile settings |
| --- | --- | --- | --- |
| google | `vertex` | `GOOGLE_APPLICATION_CREDENTIALS`, the path to a service-account JSON (`CLAUDE_GCP_CRED` also accepted) | `project`, `region` |
| google | `direct` | `GEMINI_API_KEY` or `GOOGLE_API_KEY`, a Gemini Developer API (Google AI Studio) key | – |
| google | `vertex_adc` | none: `gcloud auth application-default login` | `project`, `region` |
| openai | `azure` | `AZURE_OPENAI_API_KEY` (or `OPENAI_API_KEY`) plus `AZURE_OPENAI_ENDPOINT` | `endpoint`, `api_version` |
| openai | `native` | `OPENAI_API_KEY` for api.openai.com; `OPENAI_BASE_URL` is honoured for proxies | – |
| codex | `subscription` | none: `codex login` with ChatGPT | – |

Other variables that matter: `GOOGLE_CLOUD_PROJECT` (Vertex project when the profile has
none), `OPENAI_API_VERSION` (Azure api-version override), `CODEX_HOME` (Codex CLI home),
`GENIMG_CONFIG_HOME` (where config.toml lives), `GENIMG_HOME` (where outputs and history live).

## Check what resolved

```bash
genimg auth            # one row per provider: mode, source, endpoint, credential, ready
genimg auth --json     # the same for agents and scripts
genimg auth --check    # plus one tiny live generation per provider (Codex: login only)
```

```text
┏━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┓
┃ provider ┃ mode         ┃ source         ┃ endpoint               ┃ credential          ┃ ready ┃      models ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━┩
│ google   │ direct       │ profile:google │ generativelanguage.…   │ ✓ GEMINI_API_KEY    │   ✓   │  4/4 listed │
│ openai   │ azure        │ profile:work   │ https://myres.openai…  │ ✓ AZURE_OPENAI_API… │   ✓   │  4/6 listed │
│ codex    │ subscription │ codex login    │ Codex CLI              │ ✓ ChatGPT login     │   ✓   │ runtime-sel…│
└──────────┴──────────────┴────────────────┴────────────────────────┴─────────────────────┴───────┴─────────────┘
```

`source` tells you where the choice came from: a named profile, a `--auth` flag, or plain
environment detection.

## Several profiles

A profile is a `[profiles.NAME]` table. Keep as many as you like, for example an Azure resource
for work and a personal key:

```toml
[profiles.work]
provider = "openai"
auth = "azure"
endpoint = "https://myres.openai.azure.com"

[profiles.personal]
provider = "openai"
auth = "native"
```

Pick one per run with `--profile work`. With no flag, the first profile declared for the
model's provider is used. `--auth azure|native` forces an OpenAI mode for a single run
without touching the config.

Next: [check your models and generate a first image](first-image.md).
