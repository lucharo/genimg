"""Subscription image generation through a local, ephemeral Codex CLI run.

Codex 0.153.4 omits image-tool items from exec JSONL. Collect only fresh PNGs
in the generated_images directory belonging to the emitted thread.started ID;
never interpret the agent's prose as an output path or scan other runs.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from PIL import Image

from ..auth import codex as auth_codex
from ..interfaces import GenerateRequest, IImageGen, ProbeResult

TIMEOUT_SECONDS = 300


def _failure_hint(events: list[dict]) -> str:
  # Classify diagnostics without printing a child transcript or credential fragments.
  text = json.dumps(events).lower()
  if any(s in text for s in ("usage limit", "rate limit", "quota", "limit reached")):
    return "Codex subscription limit reached; check your Codex usage before retrying."
  if any(s in text for s in ("refused", "cannot help", "can't help", "content policy")):
    return "Codex refused the image request."
  return "Check native image-tool availability, `codex login status` and CLI version."


def _run(cmd: list[str], prompt: str, workdir: str) -> tuple[int, str]:
  """Bound the whole run and reap only our own process group on cancellation."""
  try:
    proc = subprocess.Popen(
      cmd, cwd=workdir, env=auth_codex.subprocess_env(), stdin=subprocess.PIPE,
      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
      start_new_session=os.name == "posix",
    )
  except OSError as e:
    raise RuntimeError("Could not start Codex. Check `codex --version`.") from e
  completed = False
  try:
    stdout, _ = proc.communicate(prompt, timeout=TIMEOUT_SECONDS)
    completed = True
    return proc.returncode, stdout
  except subprocess.TimeoutExpired as e:
    raise RuntimeError(f"Codex image generation timed out after {TIMEOUT_SECONDS}s; no retry was submitted.") from e
  finally:
    if not completed:
      # The group leader may already have exited while a descendant holds stdout.
      if os.name == "posix":
        try:
          os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
          pass
      else:
        proc.kill()
      proc.communicate()


class CodexImageGen(IImageGen):
  max_parallel = 2

  def probe(self, model: str, region: str | None = None) -> ProbeResult:
    info = auth_codex.auth_info()
    return ProbeResult(model=model, status="ready" if info["ok"] else "auth",
                       detail="ChatGPT login ready; native image generation not probed" if info["ok"] else str(info["hint"]))

  def generate(self, req: GenerateRequest):
    unsupported = [name for name in ("quality", "resolution", "thinking_level", "region", "project")
                   if getattr(req, name) is not None]
    if unsupported or req.mode == "batch":
      raise RuntimeError("codex:image does not support quality, resolution, thinking, region, project or batch controls; Codex selects the image model.")
    info = auth_codex.auth_info()
    if not info["ok"]:
      raise RuntimeError(str(info["hint"]))
    return super().generate(req)

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    refs = [p.expanduser().resolve() for p in ([req.input] if req.input else []) + req.refs]
    for ref in refs:
      if not ref.is_file():
        raise RuntimeError(f"Reference image not found: {ref}")
    prompt = (
      "Use the native image_gen tool exactly once to generate or edit exactly one image. "
      "Do not use APIs, genimg, drawing code or other generation tools. Do not modify project files. "
      "If the native tool is unavailable or refuses the request, stop and explain the failure.\n"
    )
    if refs:
      prompt += ("Edit the first attached image; any remaining images are references.\n" if req.input
                 else "Create a new image guided by the attached references.\n")
      prompt += "The attached images are the input/references, in this order. Use referenced_image_paths: " + json.dumps([str(p) for p in refs]) + ".\n"
    if req.aspect_ratio:
      prompt += f"Requested aspect ratio: {req.aspect_ratio}.\n"
    prompt += "Image request:\n" + req.prompt
    cmd = ["codex", "exec", "--ignore-user-config", "--enable", "image_generation",
           "--disable", "shell_tool", "-c", "project_doc_max_bytes=0",
           "--skip-git-repo-check", "--sandbox", "read-only", "--ephemeral", "--json"]
    for ref in refs:
      cmd.extend(["-i", str(ref)])
    cmd.append("-")
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="genimg-codex-") as workdir:
      returncode, stdout = _run(cmd, prompt, workdir)
    events = []
    for line in stdout.splitlines():
      try:
        event = json.loads(line)
      except ValueError:
        continue
      if isinstance(event, dict):
        events.append(event)
    if returncode or any(e.get("type") in {"turn.failed", "error"} for e in events):
      raise RuntimeError("Codex generation failed. " + _failure_hint(events) + " No API fallback was used.")
    threads = [e.get("thread_id") for e in events if e.get("type") == "thread.started"]
    if len(threads) != 1 or not any(e.get("type") == "turn.completed" for e in events):
      raise RuntimeError("Codex did not complete one image-generation run. Update the Codex CLI and retry.")
    try:
      thread_id = str(uuid.UUID(threads[0]))
    except (ValueError, TypeError, AttributeError) as e:
      raise RuntimeError("Codex returned an invalid thread ID.") from e
    directory = auth_codex.codex_home() / "generated_images" / thread_id
    candidates = [p for p in directory.glob("*.png") if p.is_file() and not p.is_symlink()
                  and p.resolve().parent == directory and p.stat().st_mtime >= started - 1]
    if len(candidates) != 1:
      raise RuntimeError("Codex returned no unique native PNG for this run. " + _failure_hint(events))
    source = candidates[0]
    try:
      with Image.open(source) as img:
        if img.format != "PNG":
          raise ValueError("not PNG")
        img.verify()
      with Image.open(source) as img:
        img.load()
    except (OSError, ValueError, SyntaxError) as e:
      raise RuntimeError("Codex produced an invalid PNG; output was not saved.") from e
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, out)
    return out
