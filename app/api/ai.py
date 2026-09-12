"""HTTP layer for the AI query endpoint.

Responsible for request/response handling and translating `AIService`
failures into HTTP status codes. No prompt engineering, tool dispatch, or
OpenAI SDK usage lives here -- see `app.services.ai` and
`app.services.ai_tools`.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.db.session import session_scope
from app.models.ai import AIQueryRequest, AIQueryResponse, ToolCallRecord
from app.services.ai import AIProviderUnavailableError, AIService, ToolRoundLimitExceededError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=AIQueryResponse)
def query_ai(request: AIQueryRequest) -> AIQueryResponse:
    """Answer a natural-language question about persisted economic data,
    using OpenAI native tool calling over our deterministic engine.

    Read-only end to end: every tool available to the model only reads
    from PostgreSQL (never FRED, never a write) -- see
    `app.services.ai_tools` for the three exposed tools.
    """
    if not settings.openai_api_key or not settings.openai_model:
        raise HTTPException(status_code=503, detail="AI integration is not configured on this server.")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    try:
        service = AIService()
        with session_scope() as session:
            result = service.query(request.message, session)
    except AIProviderUnavailableError:
        raise HTTPException(status_code=503, detail="The AI provider is currently unavailable.")
    except ToolRoundLimitExceededError:
        raise HTTPException(
            status_code=503,
            detail="The AI assistant could not complete this request within its tool-call limit.",
        )

    return AIQueryResponse(
        answer=result.answer,
        tools_used=[ToolCallRecord(name=call.name, arguments=call.arguments) for call in result.tools_used],
    )
