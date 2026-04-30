"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENAI_API_KEY", "sk-test-stub")


@pytest.fixture
def settings():
    from src.config import Settings
    return Settings(
        openai_api_key="sk-test-stub",
        openai_model="gpt-4o-mini",
        openai_base_url=None,
        mcp_server_url="https://order-mcp-74afyau24q-uc.a.run.app/mcp",
        log_level="WARNING",
    )
