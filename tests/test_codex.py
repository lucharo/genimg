from __future__ import annotations

import base64
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from typer.testing import CliRunner

from genimg import cli, discovery, draw, metadata, registry, setup
from genimg.auth import codex as auth
from genimg.generate import generate
from genimg.interfaces import GenerateRequest
from genimg.providers import codex


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
  """Real child process; only the external Codex runtime is replaced."""
  home = tmp_path / "codex-home"
  home.mkdir()
  binary_dir = tmp_path / "bin"
  binary_dir.mkdir()
  png = io.BytesIO()
  Image.new("RGB", (24, 16), "white").save(png, format="PNG")
  executable = binary_dir / "codex"
  executable.write_text(f"#!{sys.executable}\n" + '''
import base64,json,os,sys,time,uuid
from pathlib import Path
assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','AZURE_OPENAI_API_KEY','AZURE_OPENAI_ENDPOINT'))
if sys.argv[1:] == ['login','status']:
  print('Logged in using ChatGPT',file=sys.stderr)
  sys.exit(0)
assert sys.argv[1]=='exec'
home=Path(os.environ['CODEX_HOME'])
thread=str(uuid.uuid4())
mode=os.environ.get('FAKE_CODEX_MODE','ok')
prompt=sys.stdin.read()
with (home/'calls.jsonl').open('a') as f:
  f.write(json.dumps({'args':sys.argv[1:],'prompt':prompt,'cwd':os.getcwd()})+'\\n')
if mode=='descendant':
  import subprocess
  child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
  (home/'child.pid').write_text(str(child.pid))
  sys.exit(0)
if mode=='timeout':time.sleep(30)
if mode=='exit':sys.exit(2)
if mode=='badthread':thread='../unrelated'
print(json.dumps({'type':'thread.started','thread_id':thread}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'Usage limit reached' if mode=='quota' else 'I cannot help with that request' if mode=='refused' else 'Image saved to /unrelated/stale.png'}}))
if mode not in ('missing','badthread','quota','refused'):
  directory=home/'generated_images'/thread
  directory.mkdir(parents=True)
  p=directory/'exec-test.png'
  p.write_bytes(base64.b64decode(''' + repr(base64.b64encode(png.getvalue()).decode()) + '''))
  if mode=='corrupt':p.write_bytes(b'not an image')
  if mode=='multiple':(directory/'second.png').write_bytes(p.read_bytes())
  if mode=='stale':os.utime(p,(1,1))
print(json.dumps({'type':'turn.failed' if mode=='failed' else 'turn.completed'}))
''')
  executable.chmod(0o755)
  monkeypatch.setenv("PATH", str(binary_dir) + os.pathsep + os.environ.get("PATH", ""))
  monkeypatch.setenv("CODEX_HOME", str(home))
  for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"):
    monkeypatch.setenv(key, "must-not-reach-child")
  monkeypatch.setattr(cli.config, "load", lambda: {"default_resolution": "4K", "default_quality": "max"})
  monkeypatch.setattr(metadata, "META_DIR", tmp_path / "meta")
  return home


@pytest.mark.parametrize("edit", [False, True])
def test_cli_subscription_generation_and_edit(fake_codex, tmp_path, edit):
  out = tmp_path / "nested" / "out.png"
  args = ["a circle", "-m", "codex:image", "-a", "16:9", "-o", str(out)]
  refs = []
  if edit:
    for name in ("input.png", "reference with spaces.png"):
      p = tmp_path / name
      Image.new("RGB", (10, 10)).save(p)
      refs.append(p)
    args = ["a circle", str(refs[1]), *args[1:], "-i", str(refs[0])]
  result = CliRunner().invoke(cli._app, args)
  assert result.exit_code == 0, result.output
  assert "Codex subscription" in result.output
  with Image.open(out) as im:
    assert im.size == (24, 16)
  call = json.loads((fake_codex / "calls.jsonl").read_text())
  expected_args = ["exec", "--ignore-user-config", "--enable", "image_generation", "--disable", "shell_tool",
                   "-c", "project_doc_max_bytes=0", "--skip-git-repo-check", "--sandbox", "read-only", "--ephemeral", "--json"]
  for ref in refs:
    expected_args += ["-i", str(ref)]
  assert call["args"] == [*expected_args, "-"]
  assert "Requested aspect ratio: 16:9" in call["prompt"]
  assert call["prompt"].endswith("Image request:\na circle")
  assert not Path(call["cwd"]).exists()  # owned scratch cleaned
  saved = json.loads(next((tmp_path / "meta").glob("*.json")).read_text())
  assert {k: saved[k] for k in ("provider", "model_id", "quality", "resolution", "cost_usd_estimated", "billing", "billing_source", "model_selection", "aspect_ratio_mode")} == {
    "provider": "codex", "model_id": "codex:image", "quality": None, "resolution": None,
    "cost_usd_estimated": None, "billing": "subscription", "billing_source": "provider_route",
    "model_selection": "runtime", "aspect_ratio_mode": "prompt",
  }
  # Generation has already saved the complete record. History reads it without
  # running Codex again, touching the image or rewriting metadata.
  def snapshot():
    return {p: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in tmp_path.rglob("*") if p.is_file()}

  before = snapshot()
  runner = CliRunner()
  listed = runner.invoke(cli._app, ["history", "--json"])
  assert listed.exit_code == 0, listed.output
  assert json.loads(listed.output) == [saved]
  for flags in ([], ["--summary"], ["--summary", "--json"]):
    viewed = runner.invoke(cli._app, ["history", *flags])
    assert viewed.exit_code == 0, viewed.output
  rejected = runner.invoke(cli._app, ["history", "add", str(out)])
  assert rejected.exit_code == 2, rejected.output
  assert "No such command 'add'" in rejected.output
  assert snapshot() == before


@pytest.mark.parametrize("mode,match", [
  ("exit", "generation failed"), ("failed", "generation failed"),
  ("missing", "no unique native PNG"), ("multiple", "no unique native PNG"),
  ("stale", "no unique native PNG"), ("corrupt", "invalid PNG"),
  ("badthread", "invalid thread ID"), ("timeout", "timed out"),
  ("quota", "subscription limit reached"), ("refused", "Codex refused"),
])
def test_dispatch_fails_without_overwriting_existing_output(fake_codex, tmp_path, monkeypatch, mode, match):
  monkeypatch.setenv("FAKE_CODEX_MODE", mode)
  monkeypatch.setattr(codex, "TIMEOUT_SECONDS", 0.15 if mode == "timeout" else 5)
  out = tmp_path / "keep.png"
  out.write_bytes(b"keep existing output")
  with pytest.raises(RuntimeError, match=match):
    generate(GenerateRequest(prompt="circle", model="codex:image", output=out))
  assert out.read_bytes() == b"keep existing output"
  call = json.loads((fake_codex / "calls.jsonl").read_text())
  assert not Path(call["cwd"]).exists()


def test_variants_keep_prompts_and_numbered_outputs(fake_codex, tmp_path):
  result = generate(GenerateRequest(prompt="base", model="codex:image", output=tmp_path / "out.png",
                                    n=2, prompt_variants=["base", "variant"]))
  assert result.paths == [tmp_path / "out_1.png", tmp_path / "out_2.png"]
  calls = [json.loads(line) for line in (fake_codex / "calls.jsonl").read_text().splitlines()]
  assert sorted(c["prompt"].split("Image request:\n")[1] for c in calls) == ["base", "variant"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")
def test_timeout_kills_descendant_after_parent_exits(fake_codex, tmp_path, monkeypatch):
  monkeypatch.setenv("FAKE_CODEX_MODE", "descendant")
  monkeypatch.setattr(codex, "TIMEOUT_SECONDS", 0.2)
  try:
    with pytest.raises(RuntimeError, match="timed out"):
      generate(GenerateRequest(prompt="circle", model="codex:image", output=tmp_path / "out.png"))
    pid = int((fake_codex / "child.pid").read_text())
    deadline = time.monotonic() + 1
    while True:
      state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
      if not state or state.startswith("Z"):
        break
      assert time.monotonic() < deadline, f"owned descendant {pid} survived timeout ({state})"
      time.sleep(0.02)
  finally:
    pid_file = fake_codex / "child.pid"
    if pid_file.exists():
      try:
        os.kill(int(pid_file.read_text()), signal.SIGKILL)
      except ProcessLookupError:
        pass


@pytest.mark.parametrize("flag,value", [("-q", "max"), ("-r", "4K"), ("--mode", "batch"),
                                       ("--thinking", "high"), ("--region", "global"), ("--auth", "direct")])
def test_unsupported_flags_rejected_before_subprocess(fake_codex, flag, value):
  result = CliRunner().invoke(cli._app, ["circle", "-m", "codex:image", flag, value, "--dry-run"])
  assert result.exit_code == 1, result.output
  assert not (fake_codex / "calls.jsonl").exists()


@pytest.mark.parametrize("login,code,ok", [("Logged in using ChatGPT", 0, True),
                                         ("Logged in using an API key: secret", 0, False),
                                         ("Not logged in", 1, False)])
def test_login_requires_chatgpt_without_exposing_status(login, code, ok):
  with patch.object(auth.shutil, "which", return_value="codex"), patch.object(auth.subprocess, "run", return_value=SimpleNamespace(stdout="", stderr=login, returncode=code)):
    info = auth.auth_info()
  assert info == {"mode": "subscription" if ok else "unset", "source": "codex login", "endpoint": "Codex CLI",
                  "credential": "ChatGPT login" if ok else "-", "ok": ok,
                  "hint": "" if ok else "Run `codex login` with ChatGPT; codex:image requires a subscription login."}
  assert "secret" not in json.dumps(info)


@pytest.mark.parametrize("failure", [None, OSError("cannot spawn"), subprocess.TimeoutExpired("codex", 15)])
def test_unavailable_login_fails_before_generation(tmp_path, failure):
  with patch.object(auth.shutil, "which", return_value="codex" if failure else None), patch.object(auth.subprocess, "run", side_effect=failure), patch.object(codex, "_run") as run:
    with pytest.raises(RuntimeError, match="Codex"):
      generate(GenerateRequest(prompt="circle", model="codex:image", output=tmp_path / "out.png"))
    run.assert_not_called()


def test_auth_discovery_and_studio_use_login_without_generation(fake_codex):
  with patch.object(discovery, "all_canonical", return_value={"codex:image": registry.resolve("codex:image")[1]}):
    probes = discovery.probe_all()
  assert probes["codex:image"].model_dump() == {
    "model": "codex:image", "status": "ready", "detail": "ChatGPT login ready; native image generation not probed"}
  with patch.object(discovery, "load_fresh_cache", return_value=None):
    result = CliRunner().invoke(cli._app, ["auth", "--json"])
  assert result.exit_code == 0, result.output
  assert json.loads(result.output)["codex"]["ok"] is True
  models = draw.available_models({"probes": {"codex:image": {"status": "auth"}}}, {"codex": auth.auth_info()})
  model = next(m for m in models if m["alias"] == "codex:image")
  assert {k: model[k] for k in ("enabled", "qualityOptions", "resolutionOptions", "availability")} == {
    "enabled": True, "qualityOptions": [], "resolutionOptions": [], "availability": "ready"}
  assert draw.pick_size("codex", 1600, 900, "4K", "16:9") == ("16:9", None)
  assert not (fake_codex / "calls.jsonl").exists()


@pytest.mark.parametrize("use", [True, False])
def test_setup_codex_choice(fake_codex, use):
  cfg = {"enabled_providers": [] if use else ["codex"]}
  with patch.object(setup.questionary, "confirm") as confirm:
    confirm.return_value.ask.return_value = use
    assert setup._setup_codex(cfg) is use
  assert cfg == {"enabled_providers": ["codex"] if use else []}


def test_setup_drops_unavailable_codex_and_its_default():
  cfg = {"enabled_providers": ["openai_native", "codex"], "default_model": "codex:image"}
  with patch.object(auth, "auth_info", return_value={"ok": False, "hint": "Log in"}), \
       patch.object(setup.questionary, "confirm") as confirm:
    assert setup._setup_codex(cfg) is False
  confirm.assert_not_called()
  assert cfg == {"enabled_providers": ["openai_native"]}


@pytest.mark.parametrize("available", [False, True])
def test_setup_persists_cleanup_when_codex_was_the_only_provider(tmp_path, monkeypatch, available):
  monkeypatch.setattr(setup.config, "CONFIG_PATH", tmp_path / "config.json")
  setup.config.save({"enabled_providers": ["codex"], "default_model": "codex:image"})
  with patch.object(auth, "auth_info", return_value={"ok": available, "hint": "Log in"}), \
       patch.object(setup.auth_google, "adc_token_present", return_value=False), \
       patch.object(setup.questionary, "select") as select, \
       patch.object(setup.questionary, "confirm") as confirm:
    select.return_value.ask.return_value = "skip"
    confirm.return_value.ask.return_value = False
    result = CliRunner().invoke(cli._app, ["setup"])
  assert result.exit_code == 0, result.output
  assert setup.config.load() == {"enabled_providers": []}


@pytest.mark.parametrize("kill_error", [None, subprocess.TimeoutExpired("taskkill", 5)])
def test_windows_timeout_cleanup_remains_bounded(kill_error, tmp_path):
  proc = MagicMock(pid=123)
  proc.communicate.side_effect = subprocess.TimeoutExpired("codex", 300)
  proc.wait.side_effect = subprocess.TimeoutExpired("codex", 5)
  with patch.object(codex, "os", SimpleNamespace(name="nt")), \
       patch.object(codex.subprocess, "Popen", return_value=proc) as popen, \
       patch.object(codex.subprocess, "run", side_effect=kill_error) as taskkill:
    with pytest.raises(RuntimeError, match="timed out"):
      codex._run(["codex", "exec"], "circle", str(tmp_path))
  taskkill.assert_called_once_with(["taskkill", "/PID", "123", "/T", "/F"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
  proc.communicate.assert_called_once_with(None, timeout=300)
  proc.wait.assert_called_once_with(timeout=5)
  assert popen.call_args.kwargs["stdout"].closed
  assert popen.call_args.kwargs["stdin"].closed


def test_windows_run_reads_captured_output(tmp_path):
  proc = MagicMock(returncode=0)
  with patch.object(codex, "os", SimpleNamespace(name="nt")), \
       patch.object(codex.subprocess, "Popen", return_value=proc) as popen:
    def communicate(prompt, timeout):
      assert prompt is None
      assert popen.call_args.kwargs["stdin"].read() == "circle"
      popen.call_args.kwargs["stdout"].write("native result\n")
      return None, None
    proc.communicate.side_effect = communicate
    assert codex._run(["codex", "exec"], "circle", str(tmp_path)) == (0, "native result\n")
  assert popen.call_args.kwargs["stdin"].closed
  assert popen.call_args.kwargs["stdout"].closed
  proc.kill.assert_not_called()
