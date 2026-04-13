"""Shared pytest fixtures and setup.

Loads environment variables from the project's .env file so integration
tests can reach Voyage, Pinecone, and Gemini. Non-integration tests
don't touch env at all, so a missing .env only fails `-m integration`.
"""

from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=False)
