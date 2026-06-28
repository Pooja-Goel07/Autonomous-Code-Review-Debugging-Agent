"""FastAPI application entry point for the Code Review Agent backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.repos import router as repos_router
from app.api.reviews import router as reviews_router
from app.api.webhooks import router as webhook_router
from app.core.config import settings

app = FastAPI(
    title="Autonomous Code Review Agent",
    description="AI-powered code review and debugging agent API",
    version="0.1.0",
)

# CORS — allow the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(repos_router, prefix="/repos", tags=["repos"])
app.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Simple health endpoint for monitoring and load balancer probes."""
    return {"status": "ok", "version": "0.1.0"}

