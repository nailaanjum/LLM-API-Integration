import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.llm.schema import TriageOutput


router = APIRouter()


class TriageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


# Find the project root folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Location of the versioned prompt
PROMPT_PATH = PROJECT_ROOT / "prompts" / "triage-v1.md"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# Connect to Ollama through its OpenAI-compatible API
client = AsyncOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
)


@router.post("/triage")
async def triage(data: TriageInput):

    print("DEBUG: LLM_STUB =", os.getenv("LLM_STUB"))
    print("DEBUG: INPUT =", data.text)

    # Stage 1 stub mode
    # 1 = ON, 0 = OFF
    if os.getenv("LLM_STUB", "0") == "1":
        return TriageOutput(
            category="billing",
            urgency="high",
            confidence=0.95,
            reason="The message reports a billing issue."
        )

    # -------------------------
    # REAL LLM MODE
    # -------------------------

    # Load the system prompt from triage-v1.md
    system_prompt = load_prompt()

    # Keep user's data separate from system instructions
    user_message = json.dumps(
        {"text": data.text},
        ensure_ascii=False
    )

    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            temperature=0
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM request failed: {str(exc)}"
        )

    model_text = response.choices[0].message.content or ""

    # Stage 2: return the model's raw response
    return PlainTextResponse(model_text)