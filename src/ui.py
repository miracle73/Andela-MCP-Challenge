"""Gradio chat UI for the Meridian Electronics support bot."""
from __future__ import annotations

import logging

import gradio as gr

from .agent import SupportAgent
from .config import Settings
from .mcp_client import MCPClient
from .observability import configure_logging

logger = logging.getLogger(__name__)


WELCOME = (
    "Hi! I'm Aria, your Meridian Electronics support assistant. I can help you "
    "browse products, check stock and pricing, view your order history, or place "
    "a new order. How can I help today?"
)

EXAMPLES = [
    "Show me your 27-inch monitors",
    "Do you have any mechanical keyboards in stock?",
    "I'd like to check my order history",
    "I want to place an order for an Ultrawide Monitor - Model A",
]


def _build_agent() -> SupportAgent:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    mcp = MCPClient(settings.mcp_server_url)
    return SupportAgent(settings, mcp)


def build_app() -> gr.Blocks:
    agent = _build_agent()

    async def respond(user_message: str, chat_state: list, agent_history: list):
        """Streaming-style turn handler. Returns updates to chat + state."""
        if not user_message or not user_message.strip():
            yield chat_state, agent_history, ""
            return

        # Initialize agent history with system prompt on first turn
        if not agent_history:
            agent_history = agent.initial_history()

        chat_state = chat_state + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": "…"},
        ]
        yield chat_state, agent_history, ""

        try:
            result = await agent.chat(user_message, agent_history)
            chat_state[-1]["content"] = result.reply or "(no reply)"
            agent_history = result.history
            logger.info(
                "ui.turn",
                extra={"extra_fields": result.metrics.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001 — surface to user
            logger.exception("ui.turn.failed")
            chat_state[-1]["content"] = (
                f"Sorry — I hit an error and couldn't complete that request. ({type(exc).__name__})"
            )

        yield chat_state, agent_history, ""

    def reset():
        return [{"role": "assistant", "content": WELCOME}], [], ""

    with gr.Blocks(
        title="Meridian Electronics — Support Chat",
        theme=gr.themes.Soft(primary_hue="indigo"),
        css=".gradio-container {max-width: 880px !important}",
    ) as app:
        gr.Markdown(
            "# Meridian Electronics — Customer Support\n"
            "*Powered by Aria, your AI assistant. Browse products, "
            "check orders, or place an order — verification required for account actions.*"
        )
        chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": WELCOME}],
            type="messages",
            height=520,
            label="Aria",
            avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=aria"),
        )
        agent_history_state = gr.State([])

        with gr.Row():
            txt = gr.Textbox(
                placeholder="Ask about products, orders, or sign in with email + PIN…",
                show_label=False,
                scale=8,
                autofocus=True,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1)
            clear_btn = gr.Button("New chat", scale=1)

        gr.Examples(examples=EXAMPLES, inputs=txt, label="Try asking")

        gr.Markdown(
            "<small>This is a prototype. Test customers and PINs are documented in the "
            "<a href='https://github.com/'>repo README</a>. Do not enter real payment info.</small>"
        )

        send_btn.click(respond, [txt, chatbot, agent_history_state], [chatbot, agent_history_state, txt])
        txt.submit(respond, [txt, chatbot, agent_history_state], [chatbot, agent_history_state, txt])
        clear_btn.click(reset, outputs=[chatbot, agent_history_state, txt])

    return app
