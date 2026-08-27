import asyncio
from types import SimpleNamespace

from leaddesk.ai import AnswerEngine
from leaddesk.retrieval import Match


class FakeResponses:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.arguments = kwargs
        return SimpleNamespace(output_text="A concise approved answer.")


def test_openai_request_is_stateless_and_source_grounded() -> None:
    responses = FakeResponses()
    engine = AnswerEngine(api_key=None, model="gpt-5.6-luna")
    engine.client = SimpleNamespace(responses=responses)
    business = {
        "name": "Example Services",
        "assistant_name": "Ava",
        "phone": "555-0100",
    }
    matches = [
        Match(
            article={
                "id": "pricing",
                "title": "Approved pricing",
                "content": "Service starts at $100.",
            },
            score=10,
        )
    ]

    answer, mode = asyncio.run(
        engine.answer("What does it cost?", matches, business, "session-openai-test")
    )

    assert answer == "A concise approved answer."
    assert mode == "openai"
    assert responses.arguments["model"] == "gpt-5.6-luna"
    assert responses.arguments["store"] is False
    assert responses.arguments["reasoning"] == {"effort": "none"}
    assert "APPROVED SOURCES" in str(responses.arguments["input"])
    assert responses.arguments["safety_identifier"] != "session-openai-test"

