"""Codex auth profile: the user's own `codex login` with ChatGPT.

Never extracts or forwards credentials; the Codex CLI is spawned with API-key variables
stripped so only the subscription login can serve the request.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import AuthInfo, AuthProfile


def subprocess_env() -> dict[str, str]:
  env = os.environ.copy()
  for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL",
              "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"):
    env.pop(key, None)
  return env


def codex_home() -> Path:
  return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def login_status() -> tuple[bool, str]:
  """(logged in with ChatGPT, hint). stdout is never surfaced: API-key status can leak fragments."""
  executable = shutil.which("codex")
  if not executable:
    return False, "Install the Codex CLI, then run `codex login` with ChatGPT."
  hint = "Run `codex login` with ChatGPT; codex:image requires a subscription login."
  try:
    result = subprocess.run([executable, "login", "status"], env=subprocess_env(),
                            capture_output=True, text=True, timeout=15)
    status = (result.stdout + result.stderr).lower()
    return result.returncode == 0 and "logged in using chatgpt" in status, hint
  except (OSError, subprocess.TimeoutExpired):
    return False, "Could not check Codex login. Run `codex login status` and retry."


class CodexSubscription(AuthProfile):
  provider = "codex"
  mode = "subscription"
  label = "Codex (ChatGPT subscription login)"
  env_vars = ()

  def detect(self) -> bool:
    return login_status()[0]

  def detail(self) -> str:
    ok, hint = login_status()
    return "ChatGPT login active" if ok else hint

  def client(self, **kw: Any) -> None:
    return None  # the generator spawns the CLI itself

  def validate(self) -> tuple[bool, str]:
    ok, hint = login_status()
    return ok, "" if ok else hint

  def info(self) -> AuthInfo:
    ok, hint = login_status()
    return AuthInfo(mode=self.mode if ok else "unset", source="codex login", endpoint="Codex CLI",
                    credential="ChatGPT login" if ok else "-", ok=ok, profile=self.name,
                    hint="" if ok else hint)


MODES: tuple[type[AuthProfile], ...] = (CodexSubscription,)


def auth_info() -> dict[str, object]:
  return CodexSubscription().info().as_dict()
