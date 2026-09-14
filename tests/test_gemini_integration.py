"""Gemini provider paths.

The Gemini branches are reached only when a user brings a Gemini key, so none of
this is exercised by the Claude-path tests. Each test here pins a behaviour that
was wrong before: the SDK raises ValueError (not IndexError/AttributeError) from
`.text`, token usage was hard-coded to zero, a partless stream chunk killed the
stream, and one module asked for a different model generation than every other.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils import topic_engine


# --------------------------------------------------------------------------
# helpers: fakes shaped like the google-generativeai response objects
# --------------------------------------------------------------------------

def _blocked_response():
    """A response whose `.text` raises ValueError, as the real SDK does when the
    candidate has no parts (safety stop, recitation, MAX_TOKENS, empty prompt)."""
    resp = MagicMock()
    type(resp).text = property(
        lambda self: (_ for _ in ()).throw(
            ValueError("Invalid operation: The `response.text` quick accessor requires ...")
        )
    )
    return resp


def _ok_response(text, prompt_tokens=None, candidates_tokens=None):
    resp = MagicMock()
    resp.text = text
    if prompt_tokens is None:
        del resp.usage_metadata
    else:
        resp.usage_metadata = MagicMock(
            prompt_token_count=prompt_tokens,
            candidates_token_count=candidates_tokens,
        )
    return resp


def _patch_model(response):
    """Patch genai.GenerativeModel so generate_content_async returns `response`."""
    model = MagicMock()
    model.generate_content_async = AsyncMock(return_value=response)
    factory = MagicMock(return_value=model)
    return factory, model


# --------------------------------------------------------------------------
# topic_engine._call_llm — blocked responses
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blocked_gemini_response_raises_the_intended_error():
    """The guard caught (IndexError, AttributeError); the SDK raises ValueError,
    so the intended message never fired and Google's raw text propagated."""
    factory, _ = _patch_model(_blocked_response())
    with patch("utils.topic_engine.genai.GenerativeModel", factory), \
         patch("utils.topic_engine.genai.configure"):
        with pytest.raises(ValueError, match="empty or blocked"):
            await topic_engine._call_llm("prompt", "key", "gemini-flash")


@pytest.mark.asyncio
async def test_blocked_gemini_error_names_the_provider():
    """A two-provider relay needs to say which provider refused."""
    factory, _ = _patch_model(_blocked_response())
    with patch("utils.topic_engine.genai.GenerativeModel", factory), \
         patch("utils.topic_engine.genai.configure"):
        with pytest.raises(ValueError, match="gemini"):
            await topic_engine._call_llm("prompt", "key", "gemini-pro")


# --------------------------------------------------------------------------
# topic_engine._call_llm — token usage
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_usage_comes_from_the_response():
    """Usage was hard-coded to zero, so the topics token metric never moved for
    Gemini users while Claude reported real numbers."""
    factory, _ = _patch_model(_ok_response("[]", prompt_tokens=120, candidates_tokens=34))
    with patch("utils.topic_engine.genai.GenerativeModel", factory), \
         patch("utils.topic_engine.genai.configure"):
        _text, usage = await topic_engine._call_llm("prompt", "key", "gemini-flash")
    assert usage == {"input_tokens": 120, "output_tokens": 34}


@pytest.mark.asyncio
async def test_gemini_usage_falls_back_to_zero_when_absent():
    """usage_metadata is not guaranteed; a missing one must not crash the call."""
    factory, _ = _patch_model(_ok_response("[]"))
    with patch("utils.topic_engine.genai.GenerativeModel", factory), \
         patch("utils.topic_engine.genai.configure"):
        _text, usage = await topic_engine._call_llm("prompt", "key", "gemini-flash")
    assert usage == {"input_tokens": 0, "output_tokens": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,expected", [
    ("gemini-flash", "gemini-3-flash"),
    ("gemini-pro", "gemini-3-pro"),
])
async def test_topic_engine_model_selection(provider, expected):
    factory, _ = _patch_model(_ok_response("[]"))
    with patch("utils.topic_engine.genai.GenerativeModel", factory), \
         patch("utils.topic_engine.genai.configure"):
        await topic_engine._call_llm("prompt", "key", provider)
    factory.assert_called_once_with(expected)


# --------------------------------------------------------------------------
# pillar_categories — model generation consistency
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("provider,expected", [
    ("gemini-flash", "gemini-3-flash"),
    ("gemini-pro", "gemini-3-pro"),
])
async def test_generate_pillars_uses_the_same_model_generation_as_everything_else(
    provider, expected
):
    """This function asked for gemini-2.0-*, while every other Gemini call site in
    the repo — including categorize_keywords_llm in this same module — uses
    gemini-3-*."""
    from utils import pillar_categories

    factory, _ = _patch_model(_ok_response('[{"label":"x"}]'))
    with patch("utils.pillar_categories.genai.GenerativeModel", factory), \
         patch("utils.pillar_categories.genai.configure"):
        await pillar_categories.generate_pillars_llm(
            vibe_cluster=[{"handle": "@a", "genre": "g", "linger_count": 3}],
            graveyard=[], interest_clusters=[], api_key="key", provider=provider,
        )
    factory.assert_called_once_with(expected)


@pytest.mark.asyncio
async def test_every_gemini_call_site_uses_one_model_generation():
    """Guards against a call site drifting to another generation again."""
    import re, pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for path in list((root / "utils").glob("*.py")) + list((root / "api").glob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for m in re.finditer(r"[\"']gemini-([0-9.]+)-(flash|pro)[\"']", line):
                if m.group(1) != "3":
                    offenders.append(f"{path.relative_to(root)}:{n}: {m.group(0)}")
    assert not offenders, "Gemini model IDs from another generation:\n" + "\n".join(offenders)


# --------------------------------------------------------------------------
# api/main.py — streaming
# --------------------------------------------------------------------------

def _chunk(text):
    c = MagicMock()
    c.text = text
    return c


def _partless_chunk():
    """A stream chunk carrying no parts — e.g. one bearing only finish_reason or
    usage metadata. `.text` raises rather than returning empty."""
    c = MagicMock()
    type(c).text = property(
        lambda self: (_ for _ in ()).throw(ValueError("requires the response to contain a valid `Part`"))
    )
    return c


def _stream_via(chunks):
    """Patch api.main's GenerativeModel to stream `chunks`, return the SSE lines."""
    from fastapi.testclient import TestClient
    from api.main import app

    async def gen():
        for c in chunks:
            yield c

    async def call(*_a, **_kw):
        return gen()

    model = MagicMock()
    model.generate_content_async = call
    with patch("api.main.genai.GenerativeModel", MagicMock(return_value=model)), \
         patch("api.main.genai.configure"):
        export = {"Activity": {"Video Browsing History": {"VideoList": []}}}
        resp = TestClient(app).post(
            "/api/analyze/llm?provider=gemini-pro",
            files={"file": ("user_data_tiktok.json", json.dumps(export).encode())},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        return list(resp.iter_lines())


def test_partless_chunk_does_not_kill_the_stream():
    """`if chunk.text:` raised, so one partless chunk ended the user's analysis
    mid-sentence with an error instead of being skipped."""
    lines = _stream_via([_chunk("Hello"), _partless_chunk(), _chunk(" world")])

    assert "data: Hello" in lines
    assert "data:  world" in lines, "content after a partless chunk must still stream"
    assert "data: [DONE]" in lines, "stream must terminate normally"
    assert not [l for l in lines if l.startswith("data: Error:")], \
        f"a partless chunk must not surface as an error: {lines}"


def test_empty_text_chunks_are_skipped_not_emitted():
    lines = _stream_via([_chunk(""), _chunk("real")])
    assert "data: real" in lines
    assert "data: [DONE]" in lines


def test_a_genuine_stream_failure_still_reports_an_error():
    """The partless-chunk fix must not swallow real failures."""
    async def boom(*_a, **_kw):
        raise RuntimeError("API key rejected")

    from fastapi.testclient import TestClient
    from api.main import app

    model = MagicMock()
    model.generate_content_async = boom
    with patch("api.main.genai.GenerativeModel", MagicMock(return_value=model)), \
         patch("api.main.genai.configure"):
        export = {"Activity": {"Video Browsing History": {"VideoList": []}}}
        resp = TestClient(app).post(
            "/api/analyze/llm?provider=gemini-pro",
            files={"file": ("user_data_tiktok.json", json.dumps(export).encode())},
            headers={"X-API-Key": "test-key"},
        )
        lines = list(resp.iter_lines())
    assert any("API key rejected" in l for l in lines), lines
