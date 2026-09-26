import asyncio
import json
import logging
import os
import random
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIStatusError
from pydantic import BaseModel, Field, ValidationError

from src.llm.schema import TriageOutput


router = APIRouter()

cost_logger = logging.getLogger("llm_cost")
cost_logger.setLevel(logging.INFO)
cost_logger.propagate = False 

if not cost_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    cost_logger.addHandler(handler)

class TriageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "triage-v1.md"
QUARANTINE_PATH = PROJECT_ROOT / "logs" / "quarantine.jsonl"
PROMPT_VERSION = "triage-v1"

MAX_RETRIES = 2  # explicit choice — see README


# --------------------------------------------------
# LOAD PROMPT
# --------------------------------------------------

def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# --------------------------------------------------
# OLLAMA / GEMMA CLIENT
# --------------------------------------------------

client = AsyncOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    timeout=30.0,   # hard ceiling — SDK default is 10 minutes, too long for an HTTP caller
)


# --------------------------------------------------
# CALL THE MODEL — with timeout + retry policy
# --------------------------------------------------

async def call_model(messages: list[dict]) -> tuple[str, dict]:
    """
    Calls the model with retries on timeout/429/5xx only.
    Never retries 400/401/403 — those are permanent failures.
    Returns (content, usage_info).
    """
    last_exception = None

    for attempt in range(MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=os.getenv("LLM_MODEL"),
                messages=messages,
                temperature=0,
            )
            duration_ms = (time.monotonic() - start) * 1000
            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else None,
                "output_tokens": response.usage.completion_tokens if response.usage else None,
                "duration_ms": round(duration_ms, 2),
            }
            return response.choices[0].message.content or "", usage

        except (APITimeoutError, RateLimitError) as e:
            last_exception = e
            if attempt == MAX_RETRIES:
                raise

            wait_seconds = None
            response_obj = getattr(e, "response", None)
            if response_obj is not None:
                header_val = response_obj.headers.get("Retry-After")
                if header_val:
                    wait_seconds = float(header_val)

            if wait_seconds is None:
                wait_seconds = (2 ** attempt) + random.uniform(0, 0.5)  # 1s, 2s, 4s + jitter

            await asyncio.sleep(wait_seconds)

        except APIStatusError as e:
            if e.status_code in (400, 401, 403):
                raise  # never retry — permanent failure, don't burn quota

            if e.status_code >= 500:
                last_exception = e
                if attempt == MAX_RETRIES:
                    raise
                wait_seconds = (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(wait_seconds)
            else:
                raise

    raise last_exception


# --------------------------------------------------
# COST LOGGING
# --------------------------------------------------

def log_call_cost(usage: dict, needed_repair: bool) -> None:
    cost_logger.info(json.dumps({
        "prompt_version": PROMPT_VERSION,
        "model": os.getenv("LLM_MODEL"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "duration_ms": usage.get("duration_ms"),
        "needed_repair": needed_repair,
    }))


# --------------------------------------------------
# PARSE MODEL OUTPUT
# --------------------------------------------------

def parse_model_json(raw_text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char == "{":
            try:
                parsed, _ = decoder.raw_decode(cleaned[index:])
                if not isinstance(parsed, dict):
                    raise ValueError("Model output must be a JSON object.")
                return parsed
            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON object found in model output.")


# --------------------------------------------------
# PARSE + VALIDATE
# --------------------------------------------------

def validate_model_output(raw_text: str) -> TriageOutput:
    parsed_json = parse_model_json(raw_text)
    return TriageOutput.model_validate(parsed_json)


# --------------------------------------------------
# QUARANTINE FAILED OUTPUT
# --------------------------------------------------

def write_quarantine(
    user_input: str,
    raw_output: str,
    repair_output: str,
    error_message: str
) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "input": user_input,
        "raw_output": raw_output,
        "repair_output": repair_output,
        "error": error_message,
        "prompt_version": PROMPT_VERSION
    }

    with QUARANTINE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


# --------------------------------------------------
# TRIAGE ENDPOINT
# --------------------------------------------------

@router.post("/triage", response_model=TriageOutput)
async def triage(data: TriageInput):

    # --- Stage 4: kill switch — checked before anything else ---
    if os.getenv("LLM_ENABLED", "true").lower() == "false":
        return JSONResponse(
            status_code=503,
            content={"error": "Triage is temporarily disabled."}
        )

    # --- Stage 1: stub mode ---
    if os.getenv("LLM_STUB", "0") == "1":
        return TriageOutput(
            category="billing",
            urgency="high",
            confidence=0.95,
            reason="The message reports a billing issue."
        )

    try:
        system_prompt = load_prompt()
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="The triage prompt file could not be loaded."
        )

    user_message = json.dumps({"text": data.text}, ensure_ascii=False)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    # ----------------------------------------------
    # FIRST MODEL CALL
    # ----------------------------------------------

    try:
        raw_output, usage = await call_model(messages)

    except APIStatusError as e:
        if e.status_code in (400, 401, 403):
            raise HTTPException(
                status_code=502,
                detail=f"The LLM request failed with a non-retryable error ({e.status_code})."
            )
        raise HTTPException(status_code=502, detail="The LLM request failed.")

    except APITimeoutError:
        raise HTTPException(
            status_code=504,
            detail="The LLM request timed out."
        )

    except Exception:
        raise HTTPException(status_code=502, detail="The LLM request failed.")

    # ----------------------------------------------
    # FIRST PARSE + VALIDATION
    # ----------------------------------------------

    try:
        validated_output = validate_model_output(raw_output)
        log_call_cost(usage, needed_repair=False)
        return validated_output

    except (ValueError, ValidationError) as first_error:
        first_error_message = str(first_error)

    # ----------------------------------------------
    # ONE REPAIR ATTEMPT ONLY
    # ----------------------------------------------

    repair_messages = messages + [
        {"role": "assistant", "content": raw_output},
        {"role": "user", "content": json.dumps({
            "previous_output": raw_output,
            "validation_error": first_error_message,
            "instruction": (
                "Your previous answer was rejected "
                "for this reason. Return only corrected "
                "JSON matching the schema. Do not add "
                "any explanation or Markdown."
            )
        }, ensure_ascii=False)}
    ]

    try:
        repair_output, repair_usage = await call_model(repair_messages)

    except Exception:
        repair_output = ""
        try:
            write_quarantine(
                data.text, raw_output, repair_output,
                "Repair model request failed. " + first_error_message
            )
        except OSError:
            pass

        raise HTTPException(
            status_code=422,
            detail="The model output could not be repaired."
        )

    # ----------------------------------------------
    # VALIDATE REPAIR RESPONSE
    # ----------------------------------------------

    try:
        validated_output = validate_model_output(repair_output)
        log_call_cost(repair_usage, needed_repair=True)
        return validated_output

    except (ValueError, ValidationError) as second_error:
        try:
            write_quarantine(
                data.text, raw_output, repair_output,
                "First attempt: " + first_error_message
                + " | Repair attempt: " + str(second_error)
            )
        except OSError:
            pass

        raise HTTPException(
            status_code=422,
            detail=(
                "The model returned invalid data. "
                "The initial and repair responses failed schema validation."
            )
        )