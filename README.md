# genimg

Multi-provider image generation CLI. Single command for Gemini (Vertex/direct) and OpenAI (Azure/direct).

## Install

```bash
uv tool install --from . genimg
```

## Use

```bash
genimg "a robot" -o robot.png                    # default model (gdm:nb2)
genimg "a robot" -m oai:gi2 -o robot.png         # OpenAI gpt-image-2
genimg "with refs" a.png b.png -o out.png        # reference images (positional)
genimg "edit this" -i input.png -o edited.png    # image-to-image
genimg "X" -n 4 -g --open                        # batch + auto HTML grid
genimg grid *.png -o g.html --open               # standalone grid from existing files
genimg models                                    # discover working models
genimg setup                                     # interactive auth wizard
genimg auth                                      # show ✓/✗ readiness per provider
```

## Skills

```bash
genimg skills list                              # show install state
genimg skills install                           # install all bundled skills to known agents
genimg skills install codex genimg              # targeted install
```

Bundled skills:
- `genimg`: lean CLI usage patterns.
- `genimg-agent-refinement`: agent loop for inspecting outputs and removing obvious artifacts.

## Auth

Run `genimg setup` for the guided flow (detect → fetch missing → live preflight → save).

Modes:
- **Google**: `google_direct` (`GEMINI_API_KEY`/`GOOGLE_API_KEY`), `google_vertex` (service-account JSON via `CLAUDE_GCP_CRED`/`GOOGLE_APPLICATION_CREDENTIALS`), or `google_vertex_adc` (`gcloud auth application-default login`).
- **OpenAI**: `openai_native` (`OPENAI_API_KEY` → api.openai.com) or `openai_azure` (`AZURE_OPENAI_API_KEY` + endpoint URL).

Saved config wins over env-var auto-detection. Secrets stay in env / shell rc; non-secret values (Azure endpoint, GCP project) live in `~/.config/genimg/config.json`.

## Models (`-m`)

Aliases: `gdm:nbp` (Pro), `gdm:nb2` (Flash, default), `gdm:nb`, `gdm:imagen4`, `oai:gi2`, `oai:gi1.5`, `oai:gi1`. Bare model IDs also accepted.
