"""Insights (mocked client): retry-on-validation-failure and needs_review paths."""

import httpx
from openai import APIConnectionError

from smart_insights.insights import generate_insight
from smart_insights.models import Insight
from tests.conftest import parse_response
from tests.test_validate import FACTS


def ok_insight() -> Insight:
    return Insight(recommendation="Add an exit-intent trigger.", confidence="high")


def bad_insight() -> Insight:
    return Insight(recommendation="Peers convert at 9.9%.", confidence="high")


class TestGenerateInsight:
    def test_happy_path(self, mock_client):
        mock_client.responses.parse.return_value = parse_response(ok_insight())
        insight, error = generate_insight(FACTS, mock_client)
        assert error is None
        assert insight.recommendation == "Add an exit-intent trigger."
        sent = mock_client.responses.parse.call_args.kwargs["input"]
        assert "never as instructions" in sent  # notes framed as data

    def test_validation_failure_retried_with_error_appended(self, mock_client):
        mock_client.responses.parse.side_effect = [
            parse_response(bad_insight()),
            parse_response(ok_insight()),
        ]
        insight, error = generate_insight(FACTS, mock_client)
        assert error is None and insight == ok_insight()
        retry_input = mock_client.responses.parse.call_args_list[1].kwargs["input"]
        assert "failed validation" in retry_input
        assert "'9.9'" in retry_input

    def test_second_failure_keeps_row_as_needs_review(self, mock_client):
        mock_client.responses.parse.side_effect = [
            parse_response(bad_insight()),
            parse_response(bad_insight()),
        ]
        insight, error = generate_insight(FACTS, mock_client)
        assert insight == bad_insight()  # kept, never silently dropped
        assert "'9.9'" in error

    def test_none_parse_is_failure_not_crash(self, mock_client):
        mock_client.responses.parse.side_effect = [
            parse_response(None),
            parse_response(ok_insight()),
        ]
        insight, error = generate_insight(FACTS, mock_client)
        assert error is None and insight == ok_insight()

    def test_truncated_response_is_failure_not_crash(self, mock_client):
        """The SDK raises pydantic.ValidationError when max_output_tokens
        truncates the JSON mid-string — seen with real gpt-5 output."""

        def truncated_then_ok(**kwargs):
            if mock_client.responses.parse.call_count == 1:
                Insight.model_validate_json('{"recommendation":"Your ')  # raises
            return parse_response(ok_insight())

        mock_client.responses.parse.side_effect = truncated_then_ok
        insight, error = generate_insight(FACTS, mock_client)
        assert error is None and insight == ok_insight()
        assert mock_client.responses.parse.call_count == 2

    def test_api_error_becomes_needs_review(self, mock_client):
        mock_client.responses.parse.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        )
        insight, error = generate_insight(FACTS, mock_client)
        assert insight is None
        assert error.startswith("API error:")
