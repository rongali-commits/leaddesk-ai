from leaddesk.retrieval import detect_intent, rank_articles


def test_title_and_keyword_matches_are_prioritized() -> None:
    articles = [
        {"id": "a", "title": "General", "keywords": [], "content": "Prices appear here."},
        {
            "id": "b",
            "title": "Pricing and estimates",
            "keywords": ["cost", "price"],
            "content": "A confirmed quote is supplied.",
        },
    ]
    matches = rank_articles("What does it cost?", articles)
    assert matches[0].article["id"] == "b"


def test_intent_detection() -> None:
    assert detect_intent("Can I schedule a cleaning for Friday?") == "booking"
    assert detect_intent("Do you serve this postal code?") == "location"

