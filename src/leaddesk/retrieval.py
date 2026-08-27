from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9']+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "the",
    "to",
    "we",
    "what",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True, slots=True)
class Match:
    article: dict[str, Any]
    score: float


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOP_WORDS]


def rank_articles(question: str, articles: list[dict[str, Any]], limit: int = 3) -> list[Match]:
    query = Counter(tokenize(question))
    if not query:
        return []

    query_tokens = set(query)
    category_boosts = {
        "pricing": {"price", "pricing", "cost", "quote", "estimate", "fee"},
        "availability": {"area", "location", "serve", "zip", "postal"},
        "appointments": {"book", "booking", "schedule", "appointment", "reschedule"},
    }

    ranked: list[Match] = []
    for article in articles:
        title_tokens = Counter(tokenize(str(article.get("title", ""))))
        keyword_tokens = Counter(tokenize(" ".join(article.get("keywords", []))))
        content_tokens = Counter(tokenize(str(article.get("content", ""))))
        score = 0.0
        for token, frequency in query.items():
            score += min(frequency, title_tokens[token]) * 4.0
            score += min(frequency, keyword_tokens[token]) * 3.0
            score += min(frequency, content_tokens[token]) * 1.0
        category = str(article.get("category", "")).lower()
        if category in category_boosts and query_tokens & category_boosts[category]:
            score += 10.0
        if score:
            ranked.append(Match(article=article, score=score))

    return sorted(ranked, key=lambda match: match.score, reverse=True)[:limit]


def detect_intent(question: str) -> str:
    tokens = set(tokenize(question))
    intent_terms = {
        "pricing": {"price", "pricing", "cost", "quote", "estimate", "fee"},
        "booking": {"book", "booking", "schedule", "appointment", "available", "date"},
        "service": {"clean", "cleaning", "service", "include", "deep", "move"},
        "location": {"area", "location", "serve", "zip", "postal"},
        "policy": {"cancel", "reschedule", "guarantee", "issue", "refund"},
    }
    for intent, terms in intent_terms.items():
        if tokens & terms:
            return intent
    return "general"


def deterministic_answer(matches: list[Match], business: dict[str, Any]) -> str:
    if not matches:
        return (
            "I couldn't find that in the approved business information. "
            f"You can request a quote or contact {business['name']} at {business['phone']}."
        )
    answer = str(matches[0].article["content"]).strip()
    if matches[0].article.get("category") in {"Pricing", "Availability", "Appointments"}:
        answer += " If you'd like, use the quote form and the team can confirm the details."
    return answer
