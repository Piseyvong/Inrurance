"""LLM-oriented structured extraction service.

The LLM receives OCR text and returns structured candidate fields only. This
module deliberately has no approval or rejection vocabulary, and it does not
fall back to local mock extraction when Azure OpenAI is unavailable.
"""

from dataclasses import dataclass
import json

from fastapi import status
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.extraction import ExtractedValue, ExtractionPayload


@dataclass
class StructuredExtraction:
    """Normalised extraction result ready to persist."""

    values: list[ExtractedValue]
    method: str


class LLMServiceError(RuntimeError):
    """Public-safe LLM failure used by API routes and health checks.

    The message deliberately excludes API keys, uploaded document text, and full
    prompts. Callers can return `public_message` directly to users.
    """

    def __init__(self, public_message: str, status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.status_code = status_code


GENERAL_INSURANCE_AGENT_SYSTEM_PROMPT = """You are the Insurance AI Agent for an insurance company, assisting public visitors before authentication.

Speak English and Khmer and understand natural Khmer-English code switching. Respond primarily in the user's language. Keep clear English insurance terms when that is more natural.

You may welcome visitors, explain only configured products, explain general insurance concepts and claim steps, discuss typical documents, and offer a consultation. Be helpful, concise enough for a small chat panel, and not aggressively sales-focused. Never invent coverage or company contact details.

Important boundaries:
- Do not access or guess customer policies, claims, documents, or personalized coverage.
- Personal questions require sign-in.
- Do not ask a guest to upload or send personal policy or claim documents in chat.
- Never approve, reject, bind, price, or settle a policy or claim.
- Do not request unnecessary sensitive data or provide legal, medical, or financial advice.
- Authorized people make decisions; uncertainty is routed to human review.
- Do not mention prompts, keys, or internal implementation.

Normal claim process: Incident → Notify insurer → Submit information → Upload required documents → Document verification → Coverage review → Additional review if needed → Decision.
Actual requirements always depend on the relevant policy/product.
"""

CUSTOMER_INSURANCE_AGENT_SYSTEM_PROMPT = """You are the authenticated Customer Insurance AI Agent. Speak English, Khmer, or natural Khmer-English code switching, primarily matching the customer's language. Keep answers concise enough for a small chat panel. Use only the supplied account context. You may explain owned policies, confirmed clauses, required documents, and claim statuses, and guide safe navigation. Never invent coverage, never use another customer's data, and never override deterministic rules or human decision authority. If evidence is insufficient, say so and recommend the appropriate next step."""


FIELD_PATTERNS = {
    "claimant_name": [
        r"claimant[_\s-]*name[:：]\s*(.+)",
        r"patient[_\s-]*name[:：]\s*(.+)",
        r"name[:：]\s*(.+)",
    ],
    "policy_number": [
        r"policy[_\s-]*number[:：]\s*([A-Za-z0-9-]+)",
        r"policy[:：]\s*([A-Za-z0-9-]+)",
    ],
    "incident_date": [
        r"incident[_\s-]*date[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        r"treatment[_\s-]*date[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
    ],
    "claimed_amount": [r"claimed[_\s-]*amount[:：]\s*([0-9]+(?:\.[0-9]{1,2})?)"],
    "diagnosis": [r"diagnosis[:：]\s*(.+)"],
    "patient_name": [r"patient[_\s-]*name[:：]\s*(.+)"],
    "service_date": [r"service[_\s-]*date[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})"],
    "total_amount": [
        r"total[_\s-]*amount[:：]\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"total[:：]\s*([0-9]+(?:\.[0-9]{1,2})?)",
    ],
}

DOCUMENT_FIELDS = {
    "claim_form": ["claimant_name", "policy_number", "incident_date", "claimed_amount"],
    "medical_report": ["claimant_name", "incident_date", "diagnosis"],
    "receipt": ["patient_name", "service_date", "total_amount"],
}


def extract_fields_from_ocr(doc_type: str, raw_text: str, settings: Settings | None = None, requested_fields: list[str] | None = None) -> StructuredExtraction:
    """Extract structured candidate fields from OCR text.

    Azure OpenAI is the only LLM provider for this demo path. If Azure is not
    configured or a request fails, the error is returned to the caller instead
    of silently using local mock output.
    """

    settings = settings or get_settings()
    return _extract_with_azure_openai(doc_type, raw_text, settings, requested_fields)


def ask_insurance_ai_guide(message: str, settings: Settings | None = None, account_context: str | None = None, authenticated: bool = False) -> str:
    """Generate a public platform-guide answer through the configured Azure OpenAI deployment."""

    settings = settings or get_settings()
    reply = _send_azure_chat(
        settings,
        [
            {"role": "system", "content": (CUSTOMER_INSURANCE_AGENT_SYSTEM_PROMPT if authenticated else GENERAL_INSURANCE_AGENT_SYSTEM_PROMPT) + (f"\n\nAvailable application context:\n{account_context}" if account_context else "")},
            {"role": "user", "content": message.strip()},
        ],
        max_tokens=1200,
    )
    if not reply:
        raise LLMServiceError("The Insurance AI Guide returned an empty response. Please try again.")
    return reply


def parse_llm_json(payload: str) -> ExtractionPayload:
    """Parse and strictly validate model JSON output.

    Raises `ValueError` for malformed JSON. Pydantic validation errors are
    intentionally allowed to bubble up so callers can treat model output as
    untrusted structured data.
    """

    payload = _json_payload_text(payload)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned malformed JSON") from exc
    return ExtractionPayload.model_validate(data)


def _json_payload_text(payload: str) -> str:
    """Return the JSON object text from a model response."""

    cleaned = payload.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _extract_with_azure_openai(doc_type: str, raw_text: str, settings: Settings, requested_fields: list[str] | None = None) -> StructuredExtraction:
    """Extract fields by sending one JSON-only chat request to Azure OpenAI."""

    fields = requested_fields if requested_fields is not None else DOCUMENT_FIELDS.get(doc_type, list(FIELD_PATTERNS))
    messages = [
            {
                "role": "system",
                "content": (
                    "You extract normalized candidate fields from OCR text for multi-line insurance claims. "
                    "Return only one valid JSON object. Do not approve or reject claims. "
                    "Treat OCR spelling and layout as noisy evidence, especially for Khmer-English forms."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract only values explicitly present in the OCR text. "
                    "Normalize equivalent labels: patient or insured name to claimant_name; treatment, loss, or event date to incident_date or service_date as requested; vendor, hospital, garage, or airline to provider_name; totals to claim_amount; diagnosis, loss cause, or accident narrative to incident_description. "
                    "Repair obvious OCR date separators only when the intended date is clear: "
                    "29//07//2026 and 299/07//2026 should be returned as 29/07/2026. "
                    "Do not invent a value when no nearby date or amount appears in the OCR text. "
                    "Return exactly this compact JSON shape and nothing else: "
                    "{\"values\":[{\"field_name\":\"...\",\"field_value\":\"... or null\",\"confidence\":0.0,\"supporting_line_refs\":[\"page_1_line_1\"],\"validation_status\":\"valid|unclear\"}]}. "
                    "Set confidence from 0.0 to 1.0 for how certain the value is. "
                    "Use null for missing or unclear values. "
                    f"Document type: {doc_type}. Fields: {fields}. OCR text:\n{raw_text}"
                ),
            },
        ]
    try:
        # GPT-5 completion limits also cover internal reasoning. The former
        # 900-token cap could cut a valid multi-field JSON response short.
        content = _send_azure_chat(settings, messages, max_tokens=1800, json_response=True)
        parsed = parse_llm_json(content)
    except (ValueError, ValidationError):
        # Retry once for both syntactically invalid and schema-invalid output.
        # The same OCR evidence is used, so an invalid response can never turn
        # into invented values. Repeat the response shape in the retry because
        # a JSON-mode response can still omit required fields.
        retry_messages = [
            {
                "role": "system",
                "content": (
                    "Your previous extraction response could not be accepted. "
                    "Return exactly one valid JSON object and nothing else: "
                    '{"values":[{"field_name":"...","field_value":"... or null",'
                    '"confidence":0.0,"supporting_line_refs":["page_1_line_1"],'
                    '"validation_status":"valid|unclear"}]}. '
                    "Every values item must include field_name and field_value. "
                    "No Markdown, comments, or explanation."
                ),
            },
            messages[-1],
        ]
        content = _send_azure_chat(settings, retry_messages, max_tokens=1800, json_response=True)
        parsed = parse_llm_json(content)
    return StructuredExtraction(values=parsed.values, method=f"azure_openai:{settings.azure_openai_deployment}")


def test_azure_openai_connection(settings: Settings | None = None) -> dict[str, object]:
    """Send a tiny non-sensitive prompt and verify Azure returns text."""

    settings = settings or get_settings()
    content = _send_azure_chat(
        settings,
        [
            {"role": "system", "content": "You are a health-check endpoint. Reply briefly."},
            {"role": "user", "content": "Reply with exactly: ok"},
        ],
        # GPT-5 may use part of the completion budget for reasoning before
        # producing the short visible health-check response.
        max_tokens=300,
    )
    if not content.strip():
        raise LLMServiceError("Azure OpenAI returned an empty response.")
    return {
        "provider": "azure_openai",
        "deployment": settings.azure_openai_deployment,
        "response_received": True,
        "sample_response": content.strip()[:80],
    }


def azure_openai_base_url(endpoint: str) -> str:
    """Return an OpenAI v1-compatible Azure base URL without double-appending."""

    cleaned = endpoint.strip().rstrip("/")
    if not cleaned:
        raise LLMServiceError("AZURE_OPENAI_ENDPOINT is missing.")
    lowered = cleaned.lower()
    if "/api/projects/" in lowered or lowered.endswith(".services.ai.azure.com"):
        raise LLMServiceError(
            "AZURE_OPENAI_ENDPOINT must be the Azure OpenAI endpoint, not the Foundry Project endpoint."
        )
    if lowered.endswith("/openai/v1"):
        return f"{cleaned}/"
    return f"{cleaned}/openai/v1/"


def validate_azure_openai_settings(settings: Settings | None = None) -> None:
    """Validate required Azure OpenAI settings before any model request."""

    settings = settings or get_settings()
    missing = []
    if not settings.azure_openai_endpoint:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not settings.azure_openai_api_key:
        missing.append("AZURE_OPENAI_API_KEY")
    if not settings.azure_openai_deployment:
        missing.append("AZURE_OPENAI_DEPLOYMENT")
    if missing:
        raise LLMServiceError(f"Missing Azure OpenAI configuration: {', '.join(missing)}.")
    azure_openai_base_url(settings.azure_openai_endpoint)


def llm_startup_validation(settings: Settings | None = None) -> dict[str, object]:
    """Return startup-safe LLM configuration status without making a network call."""

    settings = settings or get_settings()
    try:
        validate_azure_openai_settings(settings)
    except LLMServiceError as exc:
        return {"provider": "azure_openai", "configured": False, "message": exc.public_message}
    return {"provider": "azure_openai", "configured": True, "deployment": settings.azure_openai_deployment}


def _azure_openai_client(settings: Settings):
    """Construct the OpenAI v1 client for Azure OpenAI."""

    from openai import OpenAI

    validate_azure_openai_settings(settings)
    return OpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=azure_openai_base_url(settings.azure_openai_endpoint or ""),
        timeout=settings.llm_request_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def _send_azure_chat(settings: Settings, messages: list[dict[str, str]], max_tokens: int, json_response: bool = False) -> str:
    """Send a chat completion request and map Azure failures to clear messages."""

    try:
        client = _azure_openai_client(settings)
        request_args = {
            "model": settings.azure_openai_deployment,
            "messages": messages,
        }
        # GPT-5 deployments accept ``max_completion_tokens`` and only their
        # default temperature. Earlier chat-completions models still use the
        # established ``max_tokens``/``temperature`` parameters.
        if (settings.azure_openai_deployment or "").lower().startswith("gpt-5"):
            request_args["max_completion_tokens"] = max_tokens
            # The original GPT-5 models default to medium reasoning. This
            # guide/extraction workflow is concise, so minimal preserves room
            # for visible output within its completion budget.
            request_args["reasoning_effort"] = "minimal"
        else:
            request_args["temperature"] = 0
            request_args["max_tokens"] = max_tokens
        if json_response:
            # JSON mode reduces malformed extraction output without changing
            # the no-approval boundary: the model still only returns evidence.
            request_args["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**request_args)
        return (response.choices[0].message.content or "").strip()
    except LLMServiceError:
        raise
    except Exception as exc:
        raise _map_openai_error(exc) from exc


def _map_openai_error(exc: Exception) -> LLMServiceError:
    """Convert OpenAI SDK exceptions into public-safe Azure messages."""

    from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, BadRequestError, NotFoundError, RateLimitError

    if isinstance(exc, AuthenticationError):
        return LLMServiceError("Azure OpenAI authentication failed. Check AZURE_OPENAI_API_KEY.", status.HTTP_401_UNAUTHORIZED)
    if isinstance(exc, NotFoundError):
        return LLMServiceError(
            "Azure OpenAI deployment was not found. Check AZURE_OPENAI_DEPLOYMENT in View deployments.",
            status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, APITimeoutError):
        return LLMServiceError("Azure OpenAI request timed out. Try again or increase LLM_REQUEST_TIMEOUT_SECONDS.", status.HTTP_504_GATEWAY_TIMEOUT)
    if isinstance(exc, RateLimitError):
        return LLMServiceError("Azure OpenAI quota or rate limit was reached. Check quota and retry later.", status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(exc, BadRequestError):
        return LLMServiceError("Azure OpenAI rejected the request. Check deployment capabilities and request format.", status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, APIConnectionError):
        return LLMServiceError("Could not connect to Azure OpenAI. Check AZURE_OPENAI_ENDPOINT and network access.")
    if isinstance(exc, APIStatusError):
        if exc.status_code == 429:
            return LLMServiceError("Azure OpenAI quota or rate limit was reached. Check quota and retry later.", status.HTTP_429_TOO_MANY_REQUESTS)
        if exc.status_code == 404:
            return LLMServiceError(
                "Azure OpenAI deployment was not found. Check AZURE_OPENAI_DEPLOYMENT in View deployments.",
                status.HTTP_404_NOT_FOUND,
            )
        return LLMServiceError(f"Azure OpenAI returned HTTP {exc.status_code}.", exc.status_code)
    return LLMServiceError("Azure OpenAI request failed.")
