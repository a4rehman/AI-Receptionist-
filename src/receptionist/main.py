from fastapi import FastAPI
from receptionist.api.routes import router
from receptionist.api.middleware import APIKeyMiddleware
from receptionist.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="100Solutionz AI Receptionist",
    description="Universal AI Receptionist Platform",
    version="0.1.0",
)

app.add_middleware(APIKeyMiddleware)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-receptionist"}
