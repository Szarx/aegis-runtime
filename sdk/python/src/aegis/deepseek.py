"""Optional DeepSeek clients using the official OpenAI-compatible transport."""

import os

try:
    from openai import AsyncOpenAI, OpenAI
except ImportError:
    raise ImportError("DeepSeek integration requires the SDK deepseek extra") from None

from .integrations.openai.client import ClientProxy

BASE_URL = "https://api.deepseek.com"


def _options(kwargs):
    options = dict(kwargs)
    if options.get("api_key") is None:
        options["api_key"] = os.environ.get("DEEPSEEK_API_KEY")
    if not options["api_key"]:
        raise ValueError("set DEEPSEEK_API_KEY or pass api_key explicitly")
    options.setdefault("base_url", BASE_URL)
    return options


class AegisDeepSeek(ClientProxy):
    def __init__(self, **kwargs):
        super().__init__(OpenAI(**_options(kwargs)), provider="deepseek")


class AegisAsyncDeepSeek(ClientProxy):
    def __init__(self, **kwargs):
        super().__init__(AsyncOpenAI(**_options(kwargs)), provider="deepseek")


__all__ = ["AegisDeepSeek", "AegisAsyncDeepSeek"]
