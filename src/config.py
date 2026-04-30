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
    openai_base_url: str | None
    mcp_server_url: str
    log_level: str
    max_tool_iterations: int = 8
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("API_TOKEN")
            or ""
        ).strip()
        if not api_key:
            raise RuntimeError(
                "Set OPENAI_API_KEY (or OPENROUTER_API_KEY / API_TOKEN) in .env."
            )
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        if base_url is None and api_key.startswith("sk-or-"):
            base_url = "https://openrouter.ai/api/v1"
        default_model = (
            "openai/gpt-4o-mini"
            if base_url and "openrouter" in base_url
            else "gpt-4o-mini"
        )
        return cls(
            openai_api_key=api_key,
            openai_model=os.getenv("OPENAI_MODEL", default_model),
            openai_base_url=base_url,
            mcp_server_url=os.getenv(
                "MCP_SERVER_URL",
                "https://order-mcp-74afyau24q-uc.a.run.app/mcp",
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
