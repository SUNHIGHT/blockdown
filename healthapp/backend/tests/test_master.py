"""Runs against a real Postgres (see conftest). Skipped without TEST_DATABASE_URL."""
import uuid

from app.master import lookup_master
from app.normalize import normalize_chain_name, normalize_food_name


async def _add(pool, name, kcal, *, chain=None, user_id=None, source="official", p=None, f=None, c=None, est=False):
    async with pool.acquire() as con:
        return await con.fetchval(
            """insert into foods (user_id, chain, chain_norm, name, name_norm, kcal, protein_g, fat_g, carbs_g,
                                  macro_estimated, source)
               values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) returning id""",
            user_id, chain, normalize_chain_name(chain), name, normalize_food_name(name),
            kcal, p, f, c, est, source)


async def test_matches_despite_width_kana_and_symbol_noise(pool, user_id):
    fid = await _add(pool, "とんこつラーメン", 670, chain="日高屋", est=True)
    for q in ("ﾄﾝｺﾂﾗｰﾒﾝ", "とんこつ ラーメン", "トンコツラーメン【店舗限定】"):
        hit = await lookup_master(pool, user_id, q, "日高屋")
        assert hit is not None and hit.food_id == fid and hit.kcal == 670
        assert hit.macro_estimated and hit.protein_g is None


async def test_no_match_below_threshold(pool, user_id):
    await _add(pool, "とんこつラーメン", 670, chain="日高屋")
    assert await lookup_master(pool, user_id, "サラダチキン", None) is None
    assert await lookup_master(pool, user_id, "", None) is None


async def test_users_own_row_beats_shared_row(pool, user_id):
    await _add(pool, "プロテイン", 120, source="official")
    mine = await _add(pool, "プロテイン", 140, user_id=user_id, source="user", p=24, f=2, c=4)
    hit = await lookup_master(pool, user_id, "プロテイン", None)
    assert hit.food_id == mine and hit.is_user and hit.kcal == 140


async def test_other_users_rows_are_invisible(pool, user_id):
    other = uuid.uuid4()
    async with pool.acquire() as con:
        await con.execute("insert into users (id) values ($1)", other)
    await _add(pool, "秘密のごはん", 500, user_id=other, source="user")
    assert await lookup_master(pool, user_id, "秘密のごはん", None) is None


async def test_chain_mismatch_falls_back_to_strict_global_search(pool, user_id):
    fid = await _add(pool, "中華そば", 636, chain="日高屋")
    # the model said "来来軒" but the exact name only exists under 日高屋 -> accepted at 0.9
    hit = await lookup_master(pool, user_id, "中華そば", "来来軒")
    assert hit is not None and hit.food_id == fid
    # a merely similar name is NOT accepted through the fallback
    assert await lookup_master(pool, user_id, "中華そば大", "来来軒") is None


async def test_best_similarity_wins(pool, user_id):
    await _add(pool, "味玉とんこつラーメン", 748, chain="日高屋")
    exact = await _add(pool, "とんこつラーメン", 670, chain="日高屋")
    hit = await lookup_master(pool, user_id, "とんこつラーメン", "日高屋")
    assert hit.food_id == exact
