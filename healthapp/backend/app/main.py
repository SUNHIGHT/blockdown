from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import anthropic
import asyncpg
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile

from . import config
from .llm import parse_meal
from .master import lookup_master
from .normalize import normalize_chain_name, normalize_food_name
from .resolve import resolve_item
from .schemas import ConfirmMeal, DailyActivityIn, ParseResponse, SleepLogIn, Usage


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=10)
    async with app.state.pool.acquire() as con:
        # pg_trgm silently yields NO trigrams for Japanese if the database locale
        # does not treat kana/kanji as letters (SQL_ASCII or plain "C"). Fail fast.
        if not await con.fetchval("select cardinality(show_trgm('あいう')) > 0"):
            raise RuntimeError(
                "pg_trgm cannot index Japanese: create the DB with ENCODING 'UTF8' and a "
                "UTF-8 locale such as en_US.UTF-8 / C.UTF-8 (Supabase default is fine)."
            )
    app.state.llm = anthropic.AsyncAnthropic()      # reads ANTHROPIC_API_KEY (server env only)
    yield
    await app.state.pool.close()
    await app.state.llm.close()


app = FastAPI(lifespan=lifespan)


async def current_user_id(x_user_id: str = Header(...)) -> UUID:
    """STUB. Replace with real auth (e.g. verify the Supabase JWT and return its
    `sub`). Never trust a client-supplied id in production."""
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(401, "invalid user")


# ----------------------------------------------------------------- parse
@app.post("/meals/parse", response_model=ParseResponse)
async def meals_parse(
    request: Request,
    text: str = Form(""),
    hour: int = Form(..., ge=0, le=23),
    photo: UploadFile | None = None,
    user_id: UUID = Depends(current_user_id),
):
    image: bytes | None = None
    if photo is not None:
        image = await photo.read(config.MAX_UPLOAD_BYTES + 1)
        if len(image) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "image too large")
    if not text.strip() and image is None:
        raise HTTPException(422, "text or photo required")

    try:
        res = await parse_meal(request.app.state.llm, text=text, hour=hour, image=image)
    except anthropic.RateLimitError as e:
        retry = e.response.headers.get("retry-after", "30")
        raise HTTPException(429, "busy, try again", headers={"Retry-After": retry})
    except anthropic.APIConnectionError:
        raise HTTPException(503, "upstream unreachable")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"upstream error {e.status_code}")

    usage = Usage(model=res.model, input_tokens=res.input_tokens,
                  output_tokens=res.output_tokens, request_id=res.request_id)
    if res.parsed is None:
        return ParseResponse(items=[], slot="間食", refused=True, usage=usage)

    pool: asyncpg.Pool = request.app.state.pool

    async def _lookup(uid, name, chain):
        return await lookup_master(pool, uid, name, chain)

    items = [await resolve_item(user_id, i, _lookup) for i in res.parsed.items]
    return ParseResponse(items=items, slot=res.parsed.meal_slot,
                         question=res.parsed.question, usage=usage)


# --------------------------------------------------------------- confirm
@app.post("/meals", status_code=201)
async def meals_confirm(body: ConfirmMeal, request: Request, user_id: UUID = Depends(current_user_id)):
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as con, con.transaction():
        meal_id = await con.fetchval(
            """insert into meals (user_id, local_date, eaten_at, slot, input_kind)
               values ($1,$2,$3,$4,$5) returning id""",
            user_id, body.local_date, body.eaten_at, body.slot, body.input_kind)
        for it in body.items:
            food_id = it.food_id
            if it.save_to_my_foods and it.amount_ratio > 0:
                # store per-1.0-serving numbers so next time "並" means the same thing
                r = it.amount_ratio
                food_id = await con.fetchval(
                    """insert into foods (user_id, chain, chain_norm, name, name_norm,
                                          kcal, protein_g, fat_g, carbs_g, source)
                       values ($1,$2,$3,$4,$5,$6,$7,$8,$9,'user') returning id""",
                    user_id, it.chain, normalize_chain_name(it.chain), it.name,
                    normalize_food_name(it.name), it.kcal / r, it.protein_g / r,
                    it.fat_g / r, it.carbs_g / r)
            await con.execute(
                """insert into meal_items (meal_id, food_id, name, amount_ratio, kcal, protein_g,
                       fat_g, carbs_g, kcal_min, kcal_max, source, confidence, user_corrected)
                   values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                meal_id, food_id, it.name, it.amount_ratio, it.kcal, it.protein_g, it.fat_g,
                it.carbs_g, it.kcal_min, it.kcal_max, it.source, it.confidence, it.user_corrected)
        if body.usage is not None:
            await con.execute(
                """insert into ai_estimates (meal_id, request_id, model, input_tokens, output_tokens, draft, final)
                   values ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb)""",
                meal_id, body.usage.request_id, body.usage.model, body.usage.input_tokens,
                body.usage.output_tokens,
                json.dumps([d.model_dump() for d in body.draft or []], ensure_ascii=False),
                json.dumps([i.model_dump() for i in body.items], ensure_ascii=False))
    return {"meal_id": str(meal_id)}


# ---------------------------------------------------------- health data
@app.post("/sleep_logs", status_code=204)
async def sleep_logs_upsert(body: SleepLogIn, request: Request, user_id: UUID = Depends(current_user_id)):
    if body.wake_at <= body.bed_at:
        raise HTTPException(422, "wake_at must be after bed_at")
    async with request.app.state.pool.acquire() as con:
        await con.execute(
            """insert into sleep_logs (user_id, local_date, bed_at, wake_at, quality, asleep_min, source)
               values ($1,$2,$3,$4,$5,$6,$7)
               on conflict (user_id, local_date) do update
               set bed_at=excluded.bed_at, wake_at=excluded.wake_at,
                   quality=coalesce(excluded.quality, sleep_logs.quality),
                   asleep_min=excluded.asleep_min, source=excluded.source""",
            user_id, body.local_date, body.bed_at, body.wake_at, body.quality, body.asleep_min, body.source)


@app.post("/activity/daily", status_code=204)
async def activity_upsert(body: DailyActivityIn, request: Request, user_id: UUID = Depends(current_user_id)):
    async with request.app.state.pool.acquire() as con:
        await con.execute(
            """insert into daily_activity (user_id, local_date, steps, source) values ($1,$2,$3,$4)
               on conflict (user_id, local_date) do update set steps=excluded.steps, source=excluded.source""",
            user_id, body.local_date, body.steps, body.source)
