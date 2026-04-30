"""Runtime configuration loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    mcp_server_url: str
    log_level: str
    max_tool_iterations: int = 8
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required. Set it in .env or your environment."
            )
        return cls(
            openai_api_key=api_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            mcp_server_url=os.getenv(
                "MCP_SERVER_URL",
                "https://order-mcp-74afyau24q-uc.a.run.app/mcp",
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
