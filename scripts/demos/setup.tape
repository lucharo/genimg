# Run the setup wizard against a throwaway config (free: each check is models.list or
# `codex login status`, never a generation). Render: CROP_HEIGHT=752 scripts/demos/render.sh setup
# Needs GOOGLE_API_KEY (or GEMINI_API_KEY), OPENAI_API_KEY and a `codex login`. The hidden block
# drops the Azure and service-account variables so no endpoint, project or key path reaches a frame.
Output ".vhs/setup-frames/"
Set Width 1620
Set Height 1040
Source "scripts/demos/common.tape"

Hide
Type `unset AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT OPENAI_BASE_URL GOOGLE_APPLICATION_CREDENTIALS CLAUDE_GCP_CRED` Enter
Type `export GENIMG_CONFIG_HOME="$(mktemp -d /tmp/genimg-demo.XXXXXX)/.config/genimg" && clear` Enter
Show

Type "genimg setup"
Sleep 800ms
Enter

# Google: the first choice is Vertex, so step down to the Gemini key.
Wait+Screen@20s /Pick a Google/
Sleep 1.5s
Down
Sleep 900ms
Enter

# OpenAI: the first choice is Azure, so step down to the OpenAI key.
Wait+Screen@20s /Pick a OpenAI/
Sleep 1.5s
Down
Sleep 900ms
Enter

Wait+Screen@20s /Use Codex/
Sleep 1.5s
Type "y"

# Default model: codex:image, gdm:nbp, then gdm:nb2.
Wait+Screen@20s /Default model/
Sleep 2s
Down
Sleep 500ms
Down
Sleep 900ms
Enter

Wait+Screen@20s /inspect:/
Sleep 6s
