"""Optional OpenAI API entry point; does not modify the global SDK clients."""

try:
    import openai as _openai
except ImportError as error:
    raise ImportError('Install aegis-runtime-sdk[openai] to use aegis.openai') from error

from .integrations.openai import AegisAsyncOpenAI, AegisOpenAI, wrap_openai

__all__ = ["AegisOpenAI", "AegisAsyncOpenAI", "wrap_openai"]
