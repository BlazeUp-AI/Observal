# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for services.secret_redactor (OBSV-SEC-021)."""

from unittest.mock import patch


class TestSanitizeForProvider:
    def test_redacts_jwt(self):
        from services.secret_redactor import sanitize_for_provider

        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.abc123def456ghi789jkl"
        result = sanitize_for_provider(f"Authorization: Bearer {token}")
        assert token not in result
        assert "[REDACTED" in result

    def test_redacts_db_url_password(self):
        from services.secret_redactor import sanitize_for_provider

        result = sanitize_for_provider("postgres://admin:s3cr3tPass@db.example.com/mydb")
        assert "s3cr3tPass" not in result
        assert "db.example.com" in result  # host preserved

    def test_redacts_api_key_value(self):
        from services.secret_redactor import sanitize_for_provider

        result = sanitize_for_provider("api_key=sk-abc1234567890abcdef1234567890ab")
        assert "sk-abc1234567890abcdef1234567890ab" not in result
        assert "api_key=" in result  # key name preserved

    def test_redacts_pem_block(self):
        from services.secret_redactor import sanitize_for_provider

        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQ==\n-----END RSA PRIVATE KEY-----"
        result = sanitize_for_provider(pem)
        assert "MIIEpAIBAAKCAQ==" not in result
        assert "[REDACTED_PEM]" in result

    def test_non_string_passthrough(self):
        from services.secret_redactor import sanitize_for_provider

        assert sanitize_for_provider(None) is None
        assert sanitize_for_provider(42) == 42

    def test_clean_text_unchanged(self):
        from services.secret_redactor import sanitize_for_provider

        text = "The agent completed the task in 3 tool calls."
        assert sanitize_for_provider(text) == text


class TestLLMJudgeBackendRedaction:
    async def test_secret_not_sent_to_llm(self):
        """LLMJudgeBackend.score must redact secrets before building the prompt."""
        from services.eval.eval_engine import LLMJudgeBackend

        captured: dict = {}

        async def _mock_call_model(prompt: str) -> dict:
            captured["prompt"] = prompt
            return {"score": 0.9, "reason": "ok"}

        backend = LLMJudgeBackend()
        template = {
            "prompt": "Trace: {trace}\nSpan: {span}",
            "id": "tpl-test",
            "name": "Test",
        }
        trace = {"tool_response": "Authorization: Bearer eyJmYWtlLnRva2VuLmhlcmU.abc.def"}
        span = {"error": "DATABASE_URL=postgres://user:s3cr3t@host/db"}

        with patch("services.eval.eval_engine._call_model", side_effect=_mock_call_model):
            await backend.score(template, trace, span)

        assert "eyJmYWtlLnRva2VuLmhlcmU" not in captured["prompt"]
        assert "s3cr3t" not in captured["prompt"]
