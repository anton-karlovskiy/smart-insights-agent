"""Shared fixtures: a mock OpenAI client whose responses.parse is scripted.

All tests run offline — no API key, no network (SPEC §6).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def parse_response(parsed):
    """What client.responses.parse returns: only output_parsed is read."""
    return SimpleNamespace(output_parsed=parsed)


@pytest.fixture
def mock_client():
    """Client whose responses.parse side_effect tests script per call."""
    client = MagicMock()
    return client
