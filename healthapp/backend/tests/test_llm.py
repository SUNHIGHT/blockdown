import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app import config
from app.llm import choose_model, parse_meal, prepare_image
from app.schemas import LlmItem, LlmParsed


def _jpeg_with_exif(w=3000, h=2000) -> bytes:
    im = Image.new("RGB", (w, h), (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"             # Make
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_routing():
    assert choose_model(False).model == config.MODEL_TEXT == "claude-haiku-5-5"
    assert choose_model(True).model == config.MODEL_VISION == "claude-sonnet-5-5"
    assert choose_model(False).effort == "low"
    assert choose_model(True).effort == "medium"


def test_prepare_image_downsizes_and_strips_exif():
    raw = _jpeg_with_exif()
    assert Image.open(io.BytesIO(raw)).getexif().get(0x010F) == "TestCam"
    out = prepare_image(raw)
    im = Image.open(io.BytesIO(out))
    assert max(im.size) <= config.MAX_IMAGE_EDGE
    assert im.format == "JPEG"
    assert not dict(im.getexif())


class FakeClient:
    """Duck-typed AsyncAnthropic: records the request, returns a canned parse."""
    def __init__(self, stop_reason="end_turn"):
        self.calls = []
        self.stop_reason = stop_reason
        self.messages = SimpleNamespace(parse=self._parse)

    async def _parse(self, **kw):
        self.calls.append(kw)
        item = LlmItem(name="牛丼 並盛", chain="吉野家", amount_note="並盛", kcal=650,
                       protein_g=20, fat_g=22, carbs_g=90, kcal_min=600, kcal_max=700,
                       confidence=0.8, alternatives=[])
        return SimpleNamespace(
            stop_reason=self.stop_reason, _request_id="req_x",
            usage=SimpleNamespace(input_tokens=123, output_tokens=45),
            parsed_output=LlmParsed(items=[item], meal_slot="昼", question=None))


async def test_text_only_uses_haiku_and_no_image_block():
    c = FakeClient()
    r = await parse_meal(c, text="牛丼並盛", hour=12, image=None)
    kw = c.calls[0]
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["output_config"] == {"effort": "low"}
    assert kw["output_format"] is LlmParsed
    blocks = kw["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["text"]
    assert "<user_input>牛丼並盛</user_input>" in blocks[0]["text"]
    assert r.parsed.items[0].name == "牛丼 並盛" and r.input_tokens == 123


async def test_image_uses_sonnet_and_sends_downsized_jpeg_first():
    c = FakeClient()
    await parse_meal(c, text="", hour=19, image=_jpeg_with_exif())
    kw = c.calls[0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["output_config"] == {"effort": "medium"}
    blocks = kw["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["image", "text"]
    assert blocks[0]["source"]["media_type"] == "image/jpeg"
    sent = Image.open(io.BytesIO(base64.b64decode(blocks[0]["source"]["data"])))
    assert max(sent.size) <= config.MAX_IMAGE_EDGE
    assert "写真のみ" in blocks[1]["text"]


async def test_refusal_returns_no_parsed():
    r = await parse_meal(FakeClient("refusal"), text="x", hour=1, image=None)
    assert r.refused and r.parsed is None
