"""Use the user's Codex ChatGPT login; never extract or forward credentials."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def subprocess_env() -> dict[str, str]:
  env = os.environ.copy()
  for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL",
              "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"):
    env.pop(key, None)
  return env


def codex_home() -> Path:
  return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def auth_info() -> dict[str, object]:
  executable = shutil.which("codex")
  ok = False
  hint = "Install the Codex CLI, then run `codex login` with ChatGPT."
  if executable:
    hint = "Run `codex login` with ChatGPT; codex:image requires a subscription login."
    try:
      result = subprocess.run(
        [executable, "login", "status"], env=subprocess_env(),
        capture_output=True, text=True, timeout=15,
      )
      # Do not expose stdout/stderr: API-key login status can contain credential fragments.
      status = (result.stdout + result.stderr).lower()
      ok = result.returncode == 0 and "logged in using chatgpt" in status
    except (OSError, subprocess.TimeoutExpired):
      hint = "Could not check Codex login. Run `codex login status` and retry."
  return {
    "mode": "subscription" if ok else "unset", "source": "codex login",
    "endpoint": "Codex CLI", "credential": "ChatGPT login" if ok else "-",
    "ok": ok, "hint": "" if ok else hint,
  }
