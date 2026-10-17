from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

Slot = Literal["朝", "昼", "夜", "間食", "トレ前", "トレ後"]
Source = Literal["user", "official", "packaged", "llm"]


# ---------- what the LLM returns (structured output) ----------
class LlmItem(BaseModel):
    name: str
    chain: str | None
    amount_note: str
    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    kcal_min: float
    kcal_max: float
    confidence: float
    alternatives: list[str]


class LlmParsed(BaseModel):
    items: list[LlmItem]
    meal_slot: Literal["朝", "昼", "夜", "間食"]
    question: str | None


# ---------- /meals/parse response (what the Flutter app receives) ----------
class DraftItem(BaseModel):
    name: str
    chain: str | None = None
    amount_note: str = ""
    amount_ratio: float = 1.0          # the app's size chips multiply this
    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    kcal_min: float
    kcal_max: float
    confidence: float
    source: Source
    macro_estimated: bool = False       # official kcal but P/F/C inferred
    food_id: int | None = None          # master row that matched
    alternatives: list[str] = []
    flags: list[str] = []


class Usage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_id: str | None = None


class ParseResponse(BaseModel):
    items: list[DraftItem]
    slot: Slot
    question: str | None = None
    refused: bool = False
    usage: Usage


# ---------- POST /meals (confirm) ----------
class ConfirmItem(BaseModel):
    name: str
    food_id: int | None = None
    amount_ratio: float = 1.0
    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    kcal_min: float | None = None
    kcal_max: float | None = None
    source: Source
    confidence: float | None = None
    user_corrected: bool = False
    save_to_my_foods: bool = False
    chain: str | None = None


class ConfirmMeal(BaseModel):
    local_date: date
    eaten_at: AwareDatetime
    slot: Slot
    input_kind: Literal["text", "photo", "barcode", "manual", "copy"] = "text"
    items: list[ConfirmItem] = Field(min_length=1)
    usage: Usage | None = None
    draft: list[DraftItem] | None = None   # stored in ai_estimates for accuracy review


# ---------- health data ----------
class SleepLogIn(BaseModel):
    local_date: date                     # the day you woke up
    bed_at: AwareDatetime
    wake_at: AwareDatetime
    quality: int | None = Field(default=None, ge=1, le=5)
    asleep_min: int | None = Field(default=None, ge=0, le=1440)   # actually asleep (excludes awake time)
    source: Literal["manual", "healthkit", "healthconnect"] = "healthkit"


class DailyActivityIn(BaseModel):
    local_date: date
    steps: int = Field(ge=0)
    source: Literal["manual", "healthkit", "healthconnect"] = "healthkit"
