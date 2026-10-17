"""End-to-end through FastAPI with the LLM faked and a real Postgres."""
import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.llm import LlmResult
from app.schemas import LlmItem, LlmParsed

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def client(monkeypatch):
    from app import config, main, master  # noqa: F401
    schema = (config.__file__.rsplit("/", 1)[0] + "/../sql/001_schema.sql")

    async def reset():
        con = await asyncpg.connect(URL)
        await con.execute("drop schema public cascade; create schema public;")
        await con.execute(open(schema).read())
        await con.close()
    asyncio.run(reset())

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "DATABASE_URL", URL)

    async def fake_parse_meal(client, *, text, hour, image):
        item = LlmItem(name="プロテイン", chain=None, amount_note="1杯", kcal=130, protein_g=24,
                       fat_g=2, carbs_g=4, kcal_min=120, kcal_max=140, confidence=0.7, alternatives=[])
        return LlmResult(parsed=LlmParsed(items=[item], meal_slot="間食", question=None),
                         model="claude-haiku-5-5", input_tokens=10, output_tokens=5, request_id="req_t")
    monkeypatch.setattr(main, "parse_meal", fake_parse_meal)
    with TestClient(main.app) as c:
        yield c


def _uid():
    u = uuid.uuid4()

    async def add():
        con = await asyncpg.connect(URL)
        await con.execute("insert into users (id) values ($1)", u)
        await con.close()
    asyncio.run(add())
    return str(u)


def test_parse_requires_input_and_auth(client):
    u = _uid()
    assert client.post("/meals/parse", data={"hour": 12}, headers={"X-User-Id": u}).status_code == 422
    assert client.post("/meals/parse", data={"hour": 12, "text": "x"}).status_code == 422  # header missing


def test_parse_confirm_then_learned_food_is_matched(client):
    h = {"X-User-Id": _uid()}
    r = client.post("/meals/parse", data={"hour": 15, "text": "プロテイン"}, headers=h)
    assert r.status_code == 200
    draft = r.json()
    assert draft["items"][0]["source"] == "llm" and draft["slot"] == "間食"
    assert draft["usage"]["model"] == "claude-haiku-5-5"

    item = draft["items"][0] | {"amount_ratio": 1.3, "kcal": 169, "protein_g": 31.2, "fat_g": 2.6,
                                "carbs_g": 5.2, "user_corrected": True, "save_to_my_foods": True}
    body = {"local_date": "2026-10-17", "eaten_at": "2026-10-17T15:00:00+09:00", "slot": "間食",
            "input_kind": "text", "items": [item], "usage": draft["usage"], "draft": draft["items"]}
    r = client.post("/meals", json=body, headers=h)
    assert r.status_code == 201 and r.json()["meal_id"]

    # the corrected food was stored per 1.0 serving and now wins over the LLM estimate
    r = client.post("/meals/parse", data={"hour": 15, "text": "プロテイン"}, headers=h)
    it = r.json()["items"][0]
    assert it["source"] == "user" and it["food_id"] is not None
    assert round(it["kcal"]) == 130 and it["confidence"] == 0.95


def test_sleep_and_steps_upsert(client):
    h = {"X-User-Id": _uid()}
    s = {"local_date": "2026-10-17", "bed_at": "2026-10-16T23:40:00+09:00",
         "wake_at": "2026-10-17T07:05:00+09:00", "source": "healthkit", "asleep_min": 430}
    assert client.post("/sleep_logs", json=s, headers=h).status_code == 204
    s["wake_at"] = "2026-10-17T07:20:00+09:00"; s["quality"] = 4; s["asleep_min"] = 445
    assert client.post("/sleep_logs", json=s, headers=h).status_code == 204   # same day -> update
    bad = s | {"wake_at": "2026-10-16T22:00:00+09:00"}
    assert client.post("/sleep_logs", json=bad, headers=h).status_code == 422
    naive = s | {"wake_at": "2026-10-17T07:20:00"}               # no timezone -> rejected
    assert client.post("/sleep_logs", json=naive, headers=h).status_code == 422
    assert client.post("/activity/daily", json={"local_date": "2026-10-17", "steps": 8123}, headers=h).status_code == 204
    assert client.post("/activity/daily", json={"local_date": "2026-10-17", "steps": 9000}, headers=h).status_code == 204

    async def read():
        con = await asyncpg.connect(URL)
        row = await con.fetchrow("select count(*) n, max(duration_min) d, max(quality) q, max(asleep_min) a from sleep_logs")
        steps = await con.fetchval("select steps from daily_activity")
        daily = await con.fetchrow("select sleep_min, steps from v_daily")
        await con.close()
        return row, steps, daily
    row, steps, daily = asyncio.run(read())
    assert row["n"] == 1 and row["d"] == 460 and row["q"] == 4 and row["a"] == 445   # 23:40 -> 07:20
    assert steps == 9000
    assert daily["sleep_min"] == 445 and daily["steps"] == 9000          # asleep minutes win over bed->wake
