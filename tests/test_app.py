from fastapi.testclient import TestClient


def test_public_pages_and_health(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    assert client.get("/widget").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["answer_mode"] == "deterministic"
    assert health.json()["storage"] == "ok"
    assert health.json()["version"] == "1.1.0"
    assert health.headers["x-content-type-options"] == "nosniff"


def test_chat_returns_grounded_answer_and_saves_conversation(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/chat",
        json={"question": "How much does standard cleaning cost?", "session_id": "session-12345"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "$129" in body["answer"]
    assert body["intent"] == "pricing"
    assert body["answer_mode"] == "deterministic"
    assert body["sources"][0]["title"] == "Pricing and estimates"
    assert len(body["sources"]) == 1
    assert body["show_lead_form"] is True

    conversations = client.get("/api/admin/conversations", headers=admin_headers).json()
    assert len(conversations) == 1
    assert conversations[0]["matched_article_ids"]


def test_unknown_question_does_not_invent_an_answer(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "Do you repair antique grandfather clocks?",
            "session_id": "session-67890",
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert "couldn't find" in body["answer"]
    assert body["sources"] == []
    assert body["show_lead_form"] is True


def test_lead_validation_scoring_and_admin_workflow(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    invalid = client.post(
        "/api/leads",
        json={"name": "Taylor", "service": "Deep cleaning", "consent": False},
    )
    assert invalid.status_code == 422

    response = client.post(
        "/api/leads",
        json={
            "name": "Taylor Morgan",
            "email": "taylor@example.com",
            "phone": "512-555-0112",
            "postal_code": "78701",
            "service": "Deep cleaning",
            "property_size": "3 bedrooms",
            "preferred_date": "2026-09-04",
            "message": "Please include fragrance-free products for the visit.",
            "consent": True,
            "source_page": "test",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "qualified"

    assert client.get("/api/admin/leads").status_code == 401
    leads = client.get("/api/admin/leads", headers=admin_headers).json()
    assert len(leads) == 1
    assert leads[0]["score"] == 100

    lead_id = leads[0]["id"]
    updated = client.put(
        f"/api/admin/leads/{lead_id}/status",
        headers=admin_headers,
        json={"status": "contacted"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"

    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    assert stats["leads"] == 1


def test_csv_export_neutralizes_spreadsheet_formulas(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    client.post(
        "/api/leads",
        json={
            "name": "=HYPERLINK(\"bad\")",
            "email": "safe@example.com",
            "service": "Standard cleaning",
            "consent": True,
        },
    )
    response = client.get("/api/admin/leads.csv", headers=admin_headers)
    assert response.status_code == 200
    assert "'=HYPERLINK" in response.text


def test_knowledge_crud_changes_chat_answers(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/admin/knowledge",
        headers=admin_headers,
        json={
            "title": "Window cleaning",
            "category": "Add-ons",
            "url": "https://example.com/windows",
            "keywords": ["window", "windows"],
            "content": "Interior window cleaning is available as a separately quoted add-on.",
            "enabled": True,
        },
    )
    assert created.status_code == 201
    article_id = created.json()["id"]

    chat = client.post(
        "/api/chat",
        json={"question": "Can you clean windows?", "session_id": "session-windows"},
    ).json()
    assert "separately quoted add-on" in chat["answer"]

    deleted = client.delete(f"/api/admin/knowledge/{article_id}", headers=admin_headers)
    assert deleted.status_code == 200


def test_widget_script_and_knowledge_url_validation(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    script = client.get("/widget.js")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("application/javascript")
    assert "leaddesk:resize" in script.text

    invalid_article = client.post(
        "/api/admin/knowledge",
        headers=admin_headers,
        json={
            "title": "Unsafe source",
            "url": "javascript:alert(1)",
            "content": "This content is intentionally long enough for schema validation.",
        },
    )
    assert invalid_article.status_code == 422
