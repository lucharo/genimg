"""Provider registry. Import order is display order; each module registers its provider."""
from .base import Capabilities, Provider, all_providers, get, names, register
from .codex import CodexImageGen, CodexProvider
from .google import GeminiImageGen, GoogleProvider
from .openai import OpenAIImageGen, OpenAIProvider

register(GoogleProvider())
register(OpenAIProvider())
register(CodexProvider())

__all__ = [
  "Capabilities", "Provider", "all_providers", "get", "names", "register",
  "CodexImageGen", "GeminiImageGen", "OpenAIImageGen",
  "CodexProvider", "GoogleProvider", "OpenAIProvider",
]
