"""Contract every registered provider must honour. Parametrised over the registry so a new
provider is checked the same way as the built-ins, and a capability table that drifts from
the registry or the price table fails here rather than at a user's terminal."""
from __future__ import annotations

import pytest

from genimg import providers, registry
from genimg.auth.base import AuthInfo, AuthProfile
from genimg.interfaces import IImageGen
from genimg.providers.base import ALL_ASPECTS, ALL_RESOLUTIONS, Capabilities

PROVIDERS = providers.all_providers()
MODELS = [(alias, spec) for alias, spec in registry.all_canonical().items()]


@pytest.mark.parametrize("provider", PROVIDERS, ids=lambda p: p.name)
def test_provider_declares_identity_and_modes(provider):
  assert provider.name and provider.label and provider.alias_prefix
  assert provider.billing in ("api", "subscription")
  assert provider.auth_modes, "a provider needs at least one auth mode"
  for cls in provider.auth_modes:
    assert issubclass(cls, AuthProfile)
    assert cls.provider == provider.name
    assert cls.mode and cls.label
  assert len({cls.mode for cls in provider.auth_modes}) == len(provider.auth_modes)
  assert provider.flags <= {"quality", "auth", "thinking", "region", "project"}


@pytest.mark.parametrize("provider", PROVIDERS, ids=lambda p: p.name)
def test_auth_profiles_report_without_network(provider, monkeypatch):
  for var in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "OPENAI_BASE_URL",
              "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "CLAUDE_GCP_CRED"):
    monkeypatch.delenv(var, raising=False)
  monkeypatch.setattr("genimg.auth.google.adc_token_present", lambda: False)
  monkeypatch.setattr("genimg.auth.codex.login_status", lambda: (False, "log in"))
  for cls in provider.auth_modes:
    profile = cls({}, source="env")
    assert profile.detect() is False
    info = profile.info()
    assert isinstance(info, AuthInfo)
    assert info.ok is False and info.hint, f"{cls.__name__} must explain what is missing"
    assert isinstance(profile.detail(), str) and profile.detail()


@pytest.mark.parametrize("alias,spec", MODELS, ids=[a for a, _ in MODELS])
def test_capabilities_are_well_formed_for_every_registry_model(alias, spec):
  provider = providers.get(spec.provider)
  caps = provider.capabilities(spec.model_id)
  assert isinstance(caps, Capabilities)
  assert caps.resolutions <= ALL_RESOLUTIONS
  assert caps.aspect_ratios <= ALL_ASPECTS
  if caps.sizes:
    assert {r for r, _ in caps.sizes} == caps.resolutions
    assert {a for _, a in caps.sizes} == caps.aspect_ratios
    assert caps.supports_size(None, None), "the default pair must be in the size table"
  if "quality" in provider.flags:
    assert caps.qualities
  else:
    assert not caps.qualities
  if "thinking" not in provider.flags:
    assert not caps.thinking_levels
  # The Draw Studio and cost banner call these on every model.
  assert isinstance(caps.resolution_options_by_aspect(), dict)
  assert isinstance(provider.price_table(spec.model_id), dict)


@pytest.mark.parametrize("alias,spec", MODELS, ids=[a for a, _ in MODELS])
def test_priced_models_price_every_declared_option(alias, spec):
  provider = providers.get(spec.provider)
  caps = provider.capabilities(spec.model_id)
  base = provider.price(spec.model_id)
  if provider.billing == "subscription":
    assert base is None
    return
  if base is None:
    pytest.skip(f"{spec.model_id} is deliberately unpriced")
  for q in caps.qualities or (None,):
    for r in caps.resolutions or (None,):
      assert provider.price(spec.model_id, q, r) is not None, (q, r)


@pytest.mark.parametrize("provider", PROVIDERS, ids=lambda p: p.name)
def test_inferred_models_round_trip_through_the_registry(provider):
  """A structural id the provider claims must resolve to that provider, and no provider may
  claim another's registry ids."""
  assert provider.infer_model("not-a-model-id") is None
  claimed = 0
  for alias, spec in MODELS:
    inferred = provider.infer_model(spec.model_id)
    if inferred is not None:
      claimed += 1
      assert inferred.provider == provider.name == spec.provider
      assert registry.resolve(spec.model_id)[1].provider == provider.name
  if not provider.runtime_selects_model:
    assert claimed, f"{provider.name} should recognise the shape of its own registry ids"


@pytest.mark.parametrize("provider", PROVIDERS, ids=lambda p: p.name)
def test_make_returns_a_generator_and_probe_default_is_registered(provider):
  assert isinstance(provider.make(None), IImageGen)
  model_id, _region = provider.probe_default()
  assert registry.resolve(model_id)[1].provider == provider.name


def test_registry_lookup_errors_name_the_known_providers():
  with pytest.raises(ValueError, match="registered: codex, google, openai"):
    providers.get("bedrock")
