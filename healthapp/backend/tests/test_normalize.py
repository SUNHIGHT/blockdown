import pytest

from app.normalize import normalize_chain_name, normalize_food_name as n


def test_width_case_kana_are_absorbed():
    assert n("ﾗｰﾒﾝ") == n("ラーメン") == n("らーめん")
    assert n("ＢＬＴサンド") == n("blt さんど")
    assert n("ｺｰﾋｰ") == n("こーひー")


def test_symbols_spaces_brackets_removed():
    assert n("牛丼 並盛") == n("牛丼　並盛") == n("牛丼・並盛") == "牛丼並盛"
    assert n("餃子（6個）") == n("餃子6個") == "餃子6個"


def test_annotations_dropped_but_other_brackets_keep_content():
    assert n("唐揚げ定食【店舗限定】") == "からあげ定食"
    assert n("Wドラゴンチキン【期間限定】") == n("Ｗドラゴンチキン")


def test_synonyms():
    assert n("から揚げ") == n("唐揚げ") == n("からあげ") == n("カラアゲ")
    assert n("玉子焼き") == n("卵焼き") == n("たまご焼き")
    assert n("牛丼 大盛り") == n("牛丼大盛") == "牛丼大盛"


def test_long_vowel_mark_is_kept():
    assert "ー" in n("ラーメン")


@pytest.mark.parametrize("v", [None, "", "   ", "・・・"])
def test_empty_inputs(v):
    assert n(v) == ""


def test_chain_none_when_empty():
    assert normalize_chain_name(None) is None
    assert normalize_chain_name("  ") is None
    assert normalize_chain_name("日高屋") == "日高屋"
    assert normalize_chain_name("ＭＣＤ") == normalize_chain_name("mcd")


def test_idempotent():
    s = n("ｶﾗｱｹﾞ定食【店舗限定】")
    assert n(s) == s
