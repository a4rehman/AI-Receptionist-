from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from receptionist.api.routes import router
from receptionist.api.middleware import APIKeyMiddleware
from receptionist.api.rate_limit import RateLimitMiddleware
from receptionist.api.errors import global_exception_handler, validation_exception_handler
from receptionist.api.auth import get_current_user
from receptionist.logging_config import setup_logging
from receptionist.config import get_settings
from sqlalchemy import text
from receptionist.db import engine as db_engine

setup_logging()
_settings = get_settings()

app = FastAPI(
    title="100Solutionz AI Receptionist",
    description="Universal AI Receptionist Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=_settings.api_rate_limit,
                   window_seconds=_settings.api_rate_limit_window)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(422, validation_exception_handler)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-receptionist"}


@app.get("/health/database")
async def health_database(user: dict = Depends(get_current_user)):
    try:
        async with db_engine.async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


@app.get("/health/llm")
async def health_llm(user: dict = Depends(get_current_user)):
    return {"status": "healthy", "llm_provider": _settings.llm_provider}


@app.get("/health/notifications")
async def health_notifications(user: dict = Depends(get_current_user)):
    return {
        "status": "healthy",
        "email_configured": bool(_settings.smtp_host),
        "sms_configured": bool(_settings.twilio_account_sid),
        "whatsapp_configured": bool(_settings.whatsapp_token),
    }
