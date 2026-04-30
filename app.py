"""Entrypoint — runs the Gradio app for local dev and HuggingFace Spaces."""
from __future__ import annotations

from src.ui import build_app

app = build_app()

if __name__ == "__main__":
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )
