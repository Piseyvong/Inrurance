from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.chat import router as chat_router
from app.routers.claims import router as claims_router
from app.routers.documents import router as documents_router
from app.routers.health import router as health_router
from app.routers.review import officer_router, router as review_router
from app.routers.policies import router as policies_router
from app.routers.portal import router as portal_router
from app.services.llm_extraction import llm_startup_validation

app = FastAPI(title="Insurance Claims AI Assistant")

settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(claims_router)
app.include_router(documents_router)
app.include_router(review_router)
app.include_router(officer_router)
app.include_router(policies_router)
app.include_router(portal_router)


@app.on_event("startup")
def validate_llm_configuration_on_startup():
    """Store public-safe LLM configuration status for startup diagnostics."""

    app.state.llm_startup = llm_startup_validation()
