from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, get_session
from .routers import campaigns, customers, integrations, messages, segments
from .seed import seed_initial_data

app = FastAPI(title="CRM Marketing Prototype", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(messages.router)
app.include_router(integrations.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_initial_data()


@app.get("/", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard", tags=["dashboard"])
def dashboard_summary() -> dict[str, int]:
    with get_session() as session:
        from .crud import dashboard_summary

        summary = dashboard_summary(session)
        return summary.dict()
