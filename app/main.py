from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.subscriptions import router as subscriptions_router
from app.api.routes.webhooks import router as webhooks_router

app = FastAPI(
    title="Event-Driven Automation Engine",
    version="0.1.0",
    description="Durable at-least-once event delivery reference implementation.",
)
app.include_router(health_router)
app.include_router(subscriptions_router)
app.include_router(webhooks_router)
