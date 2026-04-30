"""Observability unit tests — focus on the redaction guarantee."""
import json
import logging

from src.observability import JsonFormatter, TraceMetrics, _redact, configure_logging, time_block


class TestRedaction:
    def test_masks_pin_in_json(self):
        assert "****" in _redact('{"pin": "7912"}')

    def test_masks_pin_with_single_quotes_style(self):
        assert "****" in _redact('"pin":"1488"')

    def test_passes_unrelated_text_through(self):
        text = "customer wants a 27 inch monitor"
        assert _redact(text) == text


class TestJsonFormatter:
    def test_emits_valid_json(self, capsys):
        configure_logging("INFO")
        log = logging.getLogger("test")
        log.info("auth.attempt", extra={"extra_fields": {"email": "x@y.com", "pin": "1234"}})
        out = capsys.readouterr().out.strip().splitlines()[-1]
        payload = json.loads(out)
        assert payload["msg"] == "auth.attempt"
        assert "1234" not in out  # PIN must be redacted


class TestTraceMetrics:
    def test_total_tokens(self):
        m = TraceMetrics(prompt_tokens=10, completion_tokens=4)
        assert m.total_tokens == 14

    def test_time_block_accumulates(self):
        m = TraceMetrics()
        with time_block(m):
            pass
        assert m.latency_ms >= 0
