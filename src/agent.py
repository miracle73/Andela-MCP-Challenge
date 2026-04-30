"""Conversational agent — LLM tool-calling loop over the MCP toolset.

Design notes:
- The agent is stateless across instances. Conversation history is passed in
  on each turn, so the UI owns session state and we can scale horizontally.
- We cap tool-call iterations to prevent runaway loops if the model gets
  confused or a tool keeps erroring.
- All tool results are passed back to the model verbatim — including errors —
  so the model can apologize/retry/explain rather than us swallowing the error.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from .config import Settings
from .mcp_client import MCPClient
from .observability import TraceMetrics, time_block
from .prompts import PROMPT_VERSION, build_system_prompt
from .security import annotate_if_suspicious, validate_user_message

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    reply: str
    metrics: TraceMetrics
    history: list[dict[str, Any]] = field(default_factory=list)


class SupportAgent:
    def __init__(self, settings: Settings, mcp: MCPClient) -> None:
        self.settings = settings
        self.mcp = mcp
        self.openai = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._tools_cache: list[dict[str, Any]] | None = None

    async def _tools(self) -> list[dict[str, Any]]:
        if self._tools_cache is None:
            self._tools_cache = await self.mcp.discover_tools()
        return self._tools_cache

    @staticmethod
    def initial_history() -> list[dict[str, Any]]:
        return [{"role": "system", "content": build_system_prompt()}]

    async def chat(
        self,
        user_message: str,
        history: list[dict[str, Any]],
    ) -> TurnResult:
        """Run one turn of the agent loop. `history` MUST include the system message."""
        cleaned = validate_user_message(user_message)
        safe_user_text = annotate_if_suspicious(cleaned)
        history = list(history) + [{"role": "user", "content": safe_user_text}]
        tools = await self._tools()
        metrics = TraceMetrics()

        for iteration in range(self.settings.max_tool_iterations):
            with time_block(metrics):
                completion = await self.openai.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=history,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                )

            usage = completion.usage
            if usage:
                metrics.prompt_tokens += usage.prompt_tokens or 0
                metrics.completion_tokens += usage.completion_tokens or 0

            choice = completion.choices[0]
            msg = choice.message
            assistant_entry: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                assistant_entry["content"] = msg.content
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            history.append(assistant_entry)

            if not msg.tool_calls:
                logger.info(
                    "agent.turn.complete",
                    extra={"extra_fields": {"prompt_version": PROMPT_VERSION, "iterations": iteration + 1, **metrics.to_dict()}},
                )
                return TurnResult(reply=msg.content or "", metrics=metrics, history=history)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                text, is_error = await self.mcp.call_tool(name, args)
                metrics.tool_calls.append({"name": name, "is_error": is_error})
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": text,
                })

        final = (
            "I'm having trouble completing that request right now — I had to "
            "stop after several attempts. Could you rephrase, or try again in a moment?"
        )
        history.append({"role": "assistant", "content": final})
        logger.warning(
            "agent.turn.iteration_limit",
            extra={"extra_fields": {"limit": self.settings.max_tool_iterations, **metrics.to_dict()}},
        )
        return TurnResult(reply=final, metrics=metrics, history=history)
