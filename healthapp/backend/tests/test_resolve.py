from app.master import MasterHit
from app.resolve import resolve_item
from app.schemas import LlmItem
import uuid

U = uuid.uuid4()


def _item(**kw):
    base = dict(name="牛丼 並盛", chain="吉野家", amount_note="並盛", kcal=650, protein_g=20,
                fat_g=22, carbs_g=90, kcal_min=600, kcal_max=700, confidence=0.8, alternatives=["a", "b", "c", "d"])
    base.update(kw)
    return LlmItem(**base)


async def _none(u, n, c):
    return None


async def test_llm_fallback_keeps_estimate_and_trims_alternatives():
    d = await resolve_item(U, _item(), _none)
    assert d.source == "llm" and d.confidence == 0.8 and d.flags == []
    assert len(d.alternatives) == 3


async def test_inconsistent_kcal_is_flagged_and_confidence_capped():
    d = await resolve_item(U, _item(kcal=300), _none)   # 4*20+9*22+4*90 = 638 vs 300
    assert "kcal_mismatch" in d.flags and d.confidence <= 0.5


async def test_range_always_contains_point_estimate():
    d = await resolve_item(U, _item(kcal=720, kcal_min=600, kcal_max=700), _none)
    assert d.kcal_min <= d.kcal <= d.kcal_max


async def test_master_hit_overrides_numbers_and_marks_source():
    async def hit(u, n, c):
        return MasterHit(7, "日高屋", "中華そば", "official", 636, None, None, None, True, 0.97, False)
    d = await resolve_item(U, _item(name="中華そば", chain="日高屋", kcal=700), hit)
    assert d.kcal == 636 and d.kcal_min == d.kcal_max == 636
    assert d.source == "official" and d.macro_estimated and d.food_id == 7
    assert d.confidence == 0.85
    # P/F/C scaled from the LLM split to the official kcal
    assert abs((4 * d.protein_g + 9 * d.fat_g + 4 * d.carbs_g) - 636) < 640 * 0.2


async def test_user_row_is_reported_as_user_source():
    async def hit(u, n, c):
        return MasterHit(9, None, "いつものプロテイン", "user", 130, 24, 2, 4, False, 1.0, True)
    d = await resolve_item(U, _item(), hit)
    assert d.source == "user" and d.confidence == 0.95 and not d.macro_estimated
