"""Turn LLM items into draft items: prefer master rows, sanity-check the rest."""
from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

from .master import MasterHit
from .schemas import DraftItem, LlmItem

Lookup = Callable[[UUID, str, str | None], Awaitable[MasterHit | None]]


def _kcal_consistent(i: LlmItem, tol: float = 0.15) -> bool:
    calc = 4 * i.protein_g + 9 * i.fat_g + 4 * i.carbs_g
    return abs(calc - i.kcal) <= tol * max(i.kcal, 1.0)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


async def resolve_item(user_id: UUID, item: LlmItem, lookup: Lookup) -> DraftItem:
    hit = await lookup(user_id, item.name, item.chain)
    if hit is not None:
        # Known food: master numbers win; the LLM only supplied the name.
        # Official rows that carry kcal only have inferred P/F/C -> slightly lower trust.
        have_macros = None not in (hit.protein_g, hit.fat_g, hit.carbs_g)
        ratio = hit.kcal / max(item.kcal, 1.0)
        p = hit.protein_g if hit.protein_g is not None else item.protein_g * ratio
        f = hit.fat_g if hit.fat_g is not None else item.fat_g * ratio
        c = hit.carbs_g if hit.carbs_g is not None else item.carbs_g * ratio
        return DraftItem(
            name=hit.name, chain=hit.chain or item.chain, amount_note=item.amount_note,
            kcal=hit.kcal, protein_g=p, fat_g=f, carbs_g=c,
            kcal_min=hit.kcal, kcal_max=hit.kcal,
            confidence=0.95 if (have_macros and not hit.macro_estimated) else 0.85,
            source="user" if hit.is_user else hit.source,  # type: ignore[arg-type]
            macro_estimated=hit.macro_estimated or not have_macros,
            food_id=hit.food_id, alternatives=item.alternatives[:3],
        )

    flags: list[str] = []
    conf = _clamp01(item.confidence)
    if not _kcal_consistent(item):
        flags.append("kcal_mismatch")
        conf = min(conf, 0.5)          # surfaces in the UI as "please check"
    lo, hi = sorted((item.kcal_min, item.kcal_max))
    return DraftItem(
        name=item.name, chain=item.chain, amount_note=item.amount_note,
        kcal=item.kcal, protein_g=item.protein_g, fat_g=item.fat_g, carbs_g=item.carbs_g,
        kcal_min=min(lo, item.kcal), kcal_max=max(hi, item.kcal),
        confidence=conf, source="llm", alternatives=item.alternatives[:3], flags=flags,
    )
