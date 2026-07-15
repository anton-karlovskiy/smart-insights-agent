"""Smart Insights Agent: one next-best-action recommendation per OptinMonster customer website.

Deterministic Python owns every statistic and decision; the LLM is used only
at two isolated points (preprocess, insights) and only to reshape prose it is
given — never to author facts or numbers. See SPEC.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

# The one model constant: swapping models is this one line.
MODEL = "gpt-5"


def _load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); never overrides real env vars.
    Kept inline to hold dependencies to openai + pydantic."""
    env_file = Path(path)
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def get_client() -> OpenAI:
    """Create the real OpenAI client. The two LLM modules take a client
    parameter so tests inject a mock and never reach this."""
    _load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your "
            "key, or export it in the environment."
        )
    from openai import OpenAI

    return OpenAI()
