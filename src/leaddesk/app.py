from __future__ import annotations

import csv
import hmac
import io
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any

import httpx
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai import AnswerEngine
from .config import Settings
from .retrieval import detect_intent, rank_articles
from .storage import Storage

STATIC_DIR = Path(__file__).parent / "static"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VALID_LEAD_STATUSES = {"new", "qualified", "contacted", "won", "lost"}


class SlidingWindowLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        current = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] < current - 60:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(current)
        return True


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=500)
    session_id: str = Field(min_length=8, max_length=80)


class LeadRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=40)
    postal_code: str = Field(default="", max_length=20)
    service: str = Field(min_length=2, max_length=100)
    property_size: str = Field(default="", max_length=80)
    preferred_date: str = Field(default="", max_length=40)
    message: str = Field(default="", max_length=1000)
    consent: bool
    source_page: str = Field(default="website-widget", max_length=250)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @model_validator(mode="after")
    def validate_contact_and_consent(self) -> LeadRequest:
        if not self.email and not self.phone:
            raise ValueError("Provide an email address or phone number")
        if not self.consent:
            raise ValueError("Consent is required so the business can respond")
        return self


class KnowledgeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{3,60}$")
    title: str = Field(min_length=3, max_length=160)
    category: str = Field(default="General", max_length=80)
    url: str = Field(default="", max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    content: str = Field(min_length=20, max_length=5000)
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Source URL must begin with https:// or http://")
        return value


class StatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_LEAD_STATUSES:
            raise ValueError("Invalid lead status")
        return value


def score_lead(lead: LeadRequest) -> int:
    score = 25
    score += 15 if lead.email else 0
    score += 15 if lead.phone else 0
    score += 15 if lead.postal_code else 0
    score += 15 if lead.preferred_date else 0
    score += 10 if lead.property_size else 0
    score += 5 if len(lead.message) >= 20 else 0
    return min(score, 100)


async def send_webhook(url: str, lead: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(url, json={"event": "lead.created", "lead": lead})
    except httpx.HTTPError:
        # Webhook failures must not lose the locally stored lead.
        return


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_settings.validate()
    business = active_settings.load_business()
    storage = Storage(active_settings.database_path)
    storage.initialize(active_settings.load_seed_articles())
    answer_engine = AnswerEngine(active_settings.openai_api_key, active_settings.openai_model)
    limiter = SlidingWindowLimiter(active_settings.rate_limit_per_minute)

    app = FastAPI(
        title="LeadDesk AI",
        version="1.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = active_settings
    app.state.storage = storage

    if active_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "X-Admin-Token"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/admin") or request.url.path.startswith("/api/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def require_admin(
        x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    ) -> None:
        if not x_admin_token or not hmac.compare_digest(
            x_admin_token, active_settings.admin_token
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    @app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/widget", include_in_schema=False)
    async def widget() -> FileResponse:
        return FileResponse(STATIC_DIR / "widget.html")

    @app.get("/admin", include_in_schema=False)
    async def admin() -> FileResponse:
        return FileResponse(STATIC_DIR / "admin.html")

    @app.get("/widget.js", include_in_schema=False)
    async def widget_script() -> Response:
        script = """
(() => {
  if (document.getElementById('leaddesk-frame')) return;
  const script = document.currentScript;
  const base = new URL(script.src).origin;
  const frame = document.createElement('iframe');
  frame.id = 'leaddesk-frame';
  frame.src = base + '/widget';
  frame.title = 'Ask us a question';
  frame.setAttribute('aria-label', 'Business chat assistant');
  frame.style.cssText = [
    'position:fixed','right:14px','bottom:14px','width:82px','height:82px',
    'border:0','background:transparent','z-index:2147483000',
    'transition:width .2s,height .2s'
  ].join(';');
  frame.allow = '';
  document.body.appendChild(frame);
  window.addEventListener('message', (event) => {
    if (event.source !== frame.contentWindow || event.data?.type !== 'leaddesk:resize') return;
    if (event.data.expanded) {
      frame.style.width = 'min(390px, calc(100vw - 24px))';
      frame.style.height = 'min(640px, calc(100vh - 24px))';
    } else {
      frame.style.width = '82px';
      frame.style.height = '82px';
    }
  });
})();
""".strip()
        return Response(
            script,
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        if not storage.ping():
            raise HTTPException(status_code=503, detail="Storage is unavailable")
        return {
            "status": "ok",
            "product": "LeadDesk AI",
            "version": "1.1.0",
            "answer_mode": "openai" if active_settings.openai_api_key else "deterministic",
            "storage": "ok",
            "environment": active_settings.app_env,
        }

    @app.get("/api/config")
    async def public_config() -> dict[str, Any]:
        return {
            "business": business,
            "assistant_mode": "ai" if active_settings.openai_api_key else "demo",
        }

    @app.post("/api/chat")
    async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
        host = request.client.host if request.client else "unknown"
        if not limiter.allow(f"{host}:{payload.session_id}"):
            raise HTTPException(status_code=429, detail="Please wait a moment before asking again.")

        articles = storage.list_articles(enabled_only=True)
        matches = rank_articles(payload.question, articles)
        answer, answer_mode = await answer_engine.answer(
            payload.question, matches, business, payload.session_id
        )
        intent = detect_intent(payload.question)
        cited_matches = matches if answer_mode == "openai" else matches[:1]
        sources = [
            {"title": match.article["title"], "url": match.article.get("url", "")}
            for match in cited_matches
        ]
        if active_settings.store_conversations:
            storage.save_conversation(
                {
                    "session_id": payload.session_id,
                    "question": payload.question,
                    "answer": answer,
                    "intent": intent,
                    "answer_mode": answer_mode,
                    "matched_article_ids": [match.article["id"] for match in matches],
                }
            )
        return {
            "answer": answer,
            "intent": intent,
            "sources": sources,
            "answer_mode": answer_mode,
            "show_lead_form": intent in {"pricing", "booking", "location"} or not matches,
        }

    @app.post("/api/leads", status_code=201)
    async def create_lead(
        payload: LeadRequest, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        lead_score = score_lead(payload)
        lead_status = "qualified" if lead_score >= 70 else "new"
        lead = storage.create_lead(payload.model_dump(), lead_score, lead_status)
        if active_settings.lead_webhook_url:
            background_tasks.add_task(send_webhook, active_settings.lead_webhook_url, lead)
        return {
            "id": lead["id"],
            "status": lead_status,
            "message": f"Thanks, {payload.name}. {business['name']} will follow up shortly.",
        }

    @app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
    async def admin_stats() -> dict[str, Any]:
        return storage.stats()

    @app.get("/api/admin/leads", dependencies=[Depends(require_admin)])
    async def admin_leads(limit: int = 100) -> list[dict[str, Any]]:
        return storage.list_leads(min(max(limit, 1), 500))

    @app.put("/api/admin/leads/{lead_id}/status", dependencies=[Depends(require_admin)])
    async def update_lead_status(lead_id: str, payload: StatusRequest) -> dict[str, str]:
        if not storage.update_lead_status(lead_id, payload.status):
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"status": payload.status}

    @app.get("/api/admin/conversations", dependencies=[Depends(require_admin)])
    async def admin_conversations(limit: int = 100) -> list[dict[str, Any]]:
        return storage.list_conversations(min(max(limit, 1), 500))

    @app.get("/api/admin/knowledge", dependencies=[Depends(require_admin)])
    async def admin_knowledge() -> list[dict[str, Any]]:
        return storage.list_articles()

    @app.post("/api/admin/knowledge", dependencies=[Depends(require_admin)], status_code=201)
    async def create_knowledge(payload: KnowledgeRequest) -> dict[str, Any]:
        return storage.upsert_article(payload.model_dump())

    @app.put("/api/admin/knowledge/{article_id}", dependencies=[Depends(require_admin)])
    async def update_knowledge(article_id: str, payload: KnowledgeRequest) -> dict[str, Any]:
        article = payload.model_dump()
        article["id"] = article_id
        return storage.upsert_article(article)

    @app.delete("/api/admin/knowledge/{article_id}", dependencies=[Depends(require_admin)])
    async def delete_knowledge(article_id: str) -> JSONResponse:
        if not storage.delete_article(article_id):
            raise HTTPException(status_code=404, detail="Article not found")
        return JSONResponse({"deleted": True})

    @app.get("/api/admin/leads.csv", dependencies=[Depends(require_admin)])
    async def export_leads() -> StreamingResponse:
        leads = storage.list_leads(limit=5000)
        fieldnames = [
            "id",
            "created_at",
            "name",
            "email",
            "phone",
            "postal_code",
            "service",
            "property_size",
            "preferred_date",
            "message",
            "score",
            "status",
            "source_page",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            safe_lead = {
                key: ("'" + value if isinstance(value, str) and value[:1] in "=+-@" else value)
                for key, value in lead.items()
            }
            writer.writerow(safe_lead)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="leaddesk-leads.csv"'},
        )

    return app


app = create_app()


def run() -> None:
    uvicorn.run("leaddesk.app:app", host="0.0.0.0", port=8000, reload=False)
