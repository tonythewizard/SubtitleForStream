from unittest.mock import patch

from app.engine import LLMWorker, parse_revision


def test_malformed_qwen_text_is_rejected_and_following_response_is_usable():
    invalid = ['{"text":[],"mood":"normal"}', '{"text":"Hello.","mood":"unknown"}',
               '{"text":"Hello.","mood":"normal"} trailing', '[]', '{}']
    for response in invalid:
        assert parse_revision(response) is None
    assert parse_revision('{"text":"Hello.","mood":"normal"}') == ("Hello.", "normal")


def test_qwen_stream_is_closed_when_asr_becomes_busy():
    worker = LLMWorker({}, None, lambda _: None)
    closed = []

    def stream(**options):
        try:
            yield {"choices": [{"delta": {"content": "{"}}]}
            worker.asr_busy.set()
            yield {"choices": [{"delta": {"content": "late"}}]}
        finally:
            closed.append(True)

    with patch.object(worker, "logs"):
        model = type("Model", (), {"create_chat_completion": staticmethod(stream)})()
        assert worker.generate_revision(model, "test") is None
    assert closed
