"""Explicit OpenAI integration; imported only through the optional entry point."""

from .client import AegisAsyncOpenAI, AegisOpenAI, wrap_openai

__all__ = ["AegisOpenAI", "AegisAsyncOpenAI", "wrap_openai"]
