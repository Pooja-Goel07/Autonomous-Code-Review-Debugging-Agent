"""FastAPI application entry point for the Code Review Agent backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.webhooks import router as webhook_router
from app.core.config import settings

app = FastAPI(
    title="Autonomous Code Review Agent",
    description="AI-powered code review and debugging agent API",
    version="0.1.0",
)

# CORS — allow the frontend origin (Stage 4 will use this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Simple health endpoint for monitoring and load balancer probes."""
    return {"status": "ok", "version": "0.1.0"}
