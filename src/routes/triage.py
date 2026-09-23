import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.llm.schema import TriageOutput


router = APIRouter()


class TriageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/triage", response_model=TriageOutput)
async def triage(data: TriageInput):

    # Stage 1: Stub mode
    if os.getenv("LLM_STUB", "0") == "1":
        return TriageOutput(
            category="billing",
            urgency="high",
            confidence=0.95,
            reason="The message reports a billing issue."
        )

    # Real LLM connection will be added in a later stage
    raise HTTPException(
        status_code=501,
        detail="Real LLM mode is not implemented yet."
    )