from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from app.core.config import settings

app = FastAPI(
    title="MaintX — PLC Logic Integrity & Maintenance Accountability API",
    description="Industrial Cybersecurity platform for PLC verification, maintenance authorization, and tamper-evident audit logging.",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Authoritative API health check endpoint."""
    return {
        "status": "healthy",
        "service": "MaintX API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "security_integrity": "TAMPER-EVIDENT",
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "MaintX Industrial Cybersecurity API",
        "docs": "/docs",
        "health": "/health",
    }
