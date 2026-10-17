"""Master-table lookup (My foods first, then official/shared rows)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from . import config
from .normalize import normalize_chain_name, normalize_food_name


@dataclass(frozen=True)
class MasterHit:
    food_id: int
    chain: str | None
    name: str
    source: str                 # user / official / packaged / llm
    kcal: float
    protein_g: float | None
    fat_g: float | None
    carbs_g: float | None
    macro_estimated: bool
    similarity: float
    is_user: bool


# `name_norm % $3` uses the GIN trigram index (the similarity() *function* alone
# cannot). The threshold for `%` is set per transaction below.
# Ranking: similarity dominates; the user's own rows get a small bonus so a
# corrected "いつもの" beats a near-identical shared row; official wins ties.
_SQL = """
select id, chain, name, source, kcal, protein_g, fat_g, carbs_g, macro_estimated,
       similarity(name_norm, $3)                         as sim,
       coalesce(user_id = $1, false)                      as is_user
from foods
where (user_id = $1 or user_id is null)
  and ($2::text is null or chain_norm = $2)
  and name_norm % $3
order by similarity(name_norm, $3) + (case when user_id = $1 then 0.05 else 0 end) desc,
         (source = 'official') desc,
         id
limit 1
"""


async def _query(con: asyncpg.Connection, user_id: UUID, chain_norm: str | None,
                 name_norm: str, threshold: float) -> MasterHit | None:
    async with con.transaction():
        await con.execute("select set_config('pg_trgm.similarity_threshold', $1, true)", str(threshold))
        r = await con.fetchrow(_SQL, user_id, chain_norm, name_norm)
    if r is None:
        return None
    f = lambda v: None if v is None else float(v)  # noqa: E731  (numeric -> float)
    return MasterHit(
        food_id=r["id"], chain=r["chain"], name=r["name"], source=r["source"],
        kcal=float(r["kcal"]), protein_g=f(r["protein_g"]), fat_g=f(r["fat_g"]),
        carbs_g=f(r["carbs_g"]), macro_estimated=r["macro_estimated"],
        similarity=float(r["sim"]), is_user=r["is_user"],
    )


async def lookup_master(
    pool: asyncpg.Pool,
    user_id: UUID,
    name: str,
    chain: str | None = None,
) -> MasterHit | None:
    """Best master row for (chain, name), or None.

    1. If a chain is given: search inside that chain at MASTER_SIM_THRESHOLD.
    2. If that finds nothing (the model may have mislabelled the chain): search
       all foods but demand MASTER_SIM_THRESHOLD_NO_CHAIN.
    """
    name_norm = normalize_food_name(name)
    if not name_norm:
        return None
    chain_norm = normalize_chain_name(chain)
    async with pool.acquire() as con:
        hit = await _query(con, user_id, chain_norm, name_norm, config.MASTER_SIM_THRESHOLD)
        if hit is None and chain_norm is not None:
            hit = await _query(con, user_id, None, name_norm, config.MASTER_SIM_THRESHOLD_NO_CHAIN)
        return hit
