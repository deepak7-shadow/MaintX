from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.machines import router as machines_router
from app.api.maintenance import router as maintenance_router
from app.api.plc import router as plc_router
from app.api.changes import router as changes_router
from app.api.risk import router as risk_router
from app.api.audit import router as audit_router
from app.api.verification import router as verification_router

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

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(machines_router)
app.include_router(maintenance_router)
app.include_router(plc_router)
app.include_router(changes_router)
app.include_router(risk_router)
app.include_router(audit_router)
app.include_router(verification_router)


# ── Health & Root ─────────────────────────────────────────────────────────────
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
        "endpoints": {
            "auth": "/api/auth/me",
            "machines": "/api/machines",
            "maintenance": "/api/maintenance",
            "plc": "/api/plc",
            "changes": "/api/changes",
            "risk": "/api/risk",
            "audit_log": "/api/logs",
        },
    }
