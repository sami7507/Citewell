"""Tests for transient-error retries, the fallback model, error detail, and the landing sections/footer."""

import time
from unittest.mock import MagicMock, patch

import groq
import httpx
import pytest

from citewell import config
from citewell.chunking.chunker import Chunk
from citewell.generation.generator import GenerationError, Generator, _build_context_block, _describe_api_error
from citewell.retrieval.retriever import RetrievalResult
from citewell.utils.rate_limit import call_with_retry
from frontend.components import friendly_document_name, render_footer, render_info_sections


def _status_error(status, message="boom"):
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/x"))
    return groq.APIStatusError(message, response=response, body={"error": {"message": message}})


def _result(text="Rent is $2,400.", n=1):
    chunk = Chunk(text=text, source="d.pdf", page_number=1, chunk_id=f"x{n}", chunk_strategy="t", metadata={})
    return RetrievalResult(chunk=chunk, score=0.9)


def _ok(content="The rent is $2,400 (Source 1)."):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


# --- call_with_retry ---

def test_retry_recovers_from_a_transient_server_error(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    fn = MagicMock(side_effect=[_status_error(503), "ok"])
    assert call_with_retry(fn, max_retries=3) == "ok"
    assert fn.call_count == 2


def test_retry_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    fn = MagicMock(side_effect=_status_error(400))
    with pytest.raises(groq.APIStatusError):
        call_with_retry(fn, max_retries=3)
    assert fn.call_count == 1


def test_retry_gives_up_after_the_limit_without_a_final_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    fn = MagicMock(side_effect=_status_error(500))
    with pytest.raises(groq.APIStatusError):
        call_with_retry(fn, max_retries=3)
    assert fn.call_count == 3
    assert len(sleeps) == 2  # waits between attempts only


def test_retry_caps_a_very_long_suggested_wait(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    request = httpx.Request("POST", "https://api.groq.com/x")
    rate_error = groq.RateLimitError("Please try again in 90s.", response=httpx.Response(429, request=request), body=None)
    fn = MagicMock(side_effect=[rate_error, "ok"])
    assert call_with_retry(fn, max_retries=3, max_delay=20.0) == "ok"
    assert sleeps == [20.0]


# --- generator: fallback model and diagnostics ---

def test_fallback_model_answers_when_the_main_model_keeps_failing(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODEL", "backup-model")
    generator = Generator(api_key="fake", model="main-model")

    def fake_create(**kwargs):
        if kwargs["model"] == "main-model":
            raise _status_error(503, "over capacity")
        return _ok()

    with patch.object(generator.client.chat.completions, "create", side_effect=fake_create):
        answer = generator.generate("q", [_result()])

    assert answer.model == "backup-model"
    assert "2,400" in answer.answer


def test_error_message_includes_the_http_status_and_provider_detail(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODEL", "")
    generator = Generator(api_key="fake", model="main-model")

    with patch.object(generator.client.chat.completions, "create", side_effect=_status_error(404, "model not found")):
        with pytest.raises(GenerationError, match=r"HTTP 404: model not found"):
            generator.generate("q", [_result()])


def test_error_reports_the_main_model_even_when_the_backup_is_unavailable(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODEL", "missing-backup")
    generator = Generator(api_key="fake", model="main-model")

    def fake_create(**kwargs):
        if kwargs["model"] == "main-model":
            raise _status_error(400, "main model rejected the request")
        raise _status_error(404, "backup does not exist")

    with patch.object(generator.client.chat.completions, "create", side_effect=fake_create):
        with pytest.raises(GenerationError, match="main model rejected the request") as info:
            generator.generate("q", [_result()])
    assert "backup does not exist" not in str(info.value)


def test_environment_changes_in_one_test_do_not_leak_into_the_next():
    import os
    from citewell.services.secrets import bridge_secrets_to_env
    bridge_secrets_to_env({"GROQ_MODEL": "leaky-model"})
    assert config.GROQ_MODEL == "leaky-model"  # visible inside this test


def test_config_is_back_to_normal_after_a_polluting_test():
    assert config.GROQ_MODEL != "leaky-model"


def test_describe_api_error_is_short_and_single_line():
    text = _describe_api_error(_status_error(413, "Request too large\n" + "x" * 500))
    assert text.startswith("HTTP 413:")
    assert "\n" not in text and len(text) < 220


def test_bad_key_does_not_try_the_fallback_model(monkeypatch):
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODEL", "backup-model")
    generator = Generator(api_key="fake", model="main-model")
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.groq.com/x"))

    with patch.object(generator.client.chat.completions, "create",
                      side_effect=groq.AuthenticationError("bad", response=response, body=None)) as create:
        with pytest.raises(GenerationError, match="key was rejected"):
            generator.generate("q", [_result()])
    assert create.call_count == 1


def test_context_budget_shrinks_each_passage_when_many_are_sent(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONTEXT_CHARS_PER_CHUNK", 6000)
    monkeypatch.setattr(config, "MAX_CONTEXT_CHARS_TOTAL", 4000)
    results = [_result(text="word " * 2000, n=i) for i in range(4)]  # 10,000 characters each
    block = _build_context_block(results)
    assert block.count("[excerpt truncated]") == 4
    assert len(block) < 4000 + 4 * 200  # roughly the total budget plus labels


# --- landing sections and footer ---

def test_info_sections_cover_privacy_and_the_advice_disclaimer():
    html = render_info_sections()
    assert "How it works" in html and "What you get" in html
    assert "Privacy" in html and "not legal or financial advice" in html


def test_footer_links_are_all_real_and_external_ones_open_safely():
    import re
    footer = render_footer()
    hrefs = re.findall(r'href="([^"]+)"', footer)
    assert len(hrefs) >= 10
    for href in hrefs:
        assert href.startswith(("https://", "mailto:")) or href == "#cw-top", f"placeholder link: {href}"
    assert footer.count('rel="noopener noreferrer"') == sum(h.startswith("https://") for h in hrefs)


def test_footer_has_back_to_top_columns_and_disclaimer_in_one_line_of_html():
    footer = render_footer()
    assert 'href="#cw-top"' in footer and "Back to top" in footer
    for heading in ("Project", "Built with", "Connect"):
        assert f'cw-footer-head">{heading}<' in footer
    assert "not legal or financial advice" in footer
    assert "\n" not in footer and "\n" not in render_info_sections()


def test_page_anchor_matches_the_back_to_top_target():
    from frontend.components import render_page_anchor
    assert render_page_anchor() == '<div id="cw-top"></div>'


def test_friendly_document_name_reads_10k_properly():
    assert friendly_document_name("sample_10k_excerpt.pdf") == "Sample 10-K excerpt"
