
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from src.llm.schema import TriageOutput


router = APIRouter()


class TriageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROMPT_PATH = PROJECT_ROOT / "prompts" / "triage-v1.md"

QUARANTINE_PATH = PROJECT_ROOT / "logs" / "quarantine.jsonl"

PROMPT_VERSION = "triage-v1"


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
)


# --------------------------------------------------
# CALL THE MODEL
# --------------------------------------------------

async def call_model(messages: list[dict]) -> str:
    response = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=messages,
        temperature=0
    )

    return response.choices[0].message.content or ""


# --------------------------------------------------
# PARSE MODEL OUTPUT
# --------------------------------------------------

def parse_model_json(raw_text: str) -> dict:
    # Remove common Markdown JSON fences
    cleaned = re.sub(
        r"```(?:json)?\s*",
        "",
        raw_text,
        flags=re.IGNORECASE
    )
    cleaned = cleaned.replace("```", "").strip()

    # Find the beginning of a JSON object.
    # This allows us to handle text like:
    # "Sure! Here's the JSON: {...}"
    decoder = json.JSONDecoder()

    for index, char in enumerate(cleaned):
        if char == "{":
            try:
                parsed, _ = decoder.raw_decode(cleaned[index:])

                if not isinstance(parsed, dict):
                    raise ValueError(
                        "Model output must be a JSON object."
                    )

                return parsed

            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON object found in model output.")


# --------------------------------------------------
# PARSE + VALIDATE
# --------------------------------------------------

def validate_model_output(raw_text: str) -> TriageOutput:
    parsed_json = parse_model_json(raw_text)

    # Enforces the Stage 1 Pydantic schema,
    # including enum values and confidence range.
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

    QUARANTINE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    record = {
        "input": user_input,
        "raw_output": raw_output,
        "repair_output": repair_output,
        "error": error_message,
        "prompt_version": PROMPT_VERSION
    }

    with QUARANTINE_PATH.open(
        "a",
        encoding="utf-8"
    ) as file:
        file.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )


# --------------------------------------------------
# TRIAGE ENDPOINT
# --------------------------------------------------

@router.post("/triage", response_model=TriageOutput)
async def triage(data: TriageInput):

    # Optional Stage 1 stub mode
    print("LLM_STUB VALUE:", os.getenv("LLM_STUB"))
    if os.getenv("LLM_STUB", "0") == "1":
        return TriageOutput(
            category="billing",
            urgency="high",
            confidence=0.95,
            reason="The message reports a billing issue."
        )

    # Load versioned system prompt
    try:
        system_prompt = load_prompt()

    except OSError:
        raise HTTPException(
            status_code=500,
            detail="The triage prompt file could not be loaded."
        )

    # Keep untrusted input separate from system prompt
    user_message = json.dumps(
        {"text": data.text},
        ensure_ascii=False
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    # ----------------------------------------------
    # FIRST MODEL CALL
    # ----------------------------------------------

    try:
        raw_output = await call_model(messages)
        print("FIRST MODEL OUTPUT:", raw_output)

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="The LLM request failed."
        )

    # ----------------------------------------------
    # FIRST PARSE + VALIDATION
    # ----------------------------------------------

    try:
        validated_output = validate_model_output(raw_output)

        # Only validated data is returned
        return validated_output

    except (ValueError, ValidationError) as first_error:
        first_error_message = str(first_error)

    # ----------------------------------------------
    # ONE REPAIR ATTEMPT ONLY
    # ----------------------------------------------

    repair_messages = messages + [
        {
            "role": "assistant",
            "content": raw_output
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "previous_output": raw_output,
                    "validation_error": first_error_message,
                    "instruction": (
                        "Your previous answer was rejected "
                        "for this reason. Return only corrected "
                        "JSON matching the schema. Do not add "
                        "any explanation or Markdown."
                    )
                },
                ensure_ascii=False
            )
        }
    ]

    try:
        repair_output = await call_model(repair_messages)
        print("REPAIR MODEL OUTPUT:", repair_output)

    except Exception:
        # A failed repair call is still a failed attempt.
        repair_output = ""

        try:
            write_quarantine(
                data.text,
                raw_output,
                repair_output,
                "Repair model request failed. "
                + first_error_message
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

        return validated_output

    except (ValueError, ValidationError) as second_error:

        # Both attempts failed. Quarantine the outputs.
        try:
            write_quarantine(
                data.text,
                raw_output,
                repair_output,
                (
                    "First attempt: "
                    + first_error_message
                    + " | Repair attempt: "
                    + str(second_error)
                )
            )
        except OSError:
            pass

        # Never return raw model text to the caller.
        raise HTTPException(
            status_code=422,
            detail=(
                "The model returned invalid data. "
                "The initial and repair responses failed "
                "schema validation."
            )
        )