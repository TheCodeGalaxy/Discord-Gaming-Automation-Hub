"""Tests for domain exception hierarchy."""

from __future__ import annotations

import pytest

from gaming_hub.core.exceptions import (
    CalendarError,
    ConfigurationError,
    DiscordError,
    GamingHubError,
    NotFoundError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Exception inheritance structure."""

    @pytest.mark.unit
    def test_all_inherit_from_gaming_hub_error(self) -> None:
        """All custom exceptions should inherit from GamingHubError."""
        assert isinstance(ConfigurationError(""), GamingHubError)
        assert isinstance(ProviderError(""), GamingHubError)
        assert isinstance(ProviderTimeoutError(""), GamingHubError)
        assert isinstance(ProviderRateLimitError(""), GamingHubError)
        assert isinstance(NotFoundError(""), GamingHubError)
        assert isinstance(ValidationError(""), GamingHubError)
        assert isinstance(DiscordError(""), GamingHubError)
        assert isinstance(CalendarError(""), GamingHubError)

    @pytest.mark.unit
    def test_provider_exception_hierarchy(self) -> None:
        """Provider-specific exceptions should inherit from ProviderError."""
        assert isinstance(ProviderTimeoutError(""), ProviderError)
        assert isinstance(ProviderRateLimitError(""), ProviderError)

    @pytest.mark.unit
    def test_message_and_details(self) -> None:
        """GamingHubError should store message and optional details."""
        exc = GamingHubError("test message", details={"key": "value"})
        assert str(exc) == "test message"
        assert exc.message == "test message"
        assert exc.details == {"key": "value"}

    @pytest.mark.unit
    def test_empty_details_default(self) -> None:
        """GamingHubError should default to empty details dict."""
        exc = GamingHubError("no details")
        assert exc.details == {}

    @pytest.mark.unit
    def test_provider_error_with_context(self) -> None:
        """ProviderError should store provider and status_code context."""
        status_code = 503
        exc = ProviderError(
            "API error",
            provider="cheapshark",
            status_code=status_code,
            details={"endpoint": "/deals"},
        )
        assert exc.provider == "cheapshark"
        assert exc.status_code == status_code
        assert exc.details["endpoint"] == "/deals"

    @pytest.mark.unit
    def test_provider_timeout(self) -> None:
        """ProviderTimeoutError should be a ProviderError with provider info."""
        exc = ProviderTimeoutError("Request timed out", provider="epic")
        assert isinstance(exc, ProviderError)
        assert exc.provider == "epic"

    @pytest.mark.unit
    def test_provider_rate_limit(self) -> None:
        """ProviderRateLimitError should store the 429 status code."""
        status_code = 429
        exc = ProviderRateLimitError(
            "Too many requests",
            provider="steam",
            status_code=status_code,
        )
        assert isinstance(exc, ProviderError)
        assert exc.status_code == status_code

    @pytest.mark.unit
    def test_specific_exceptions(self) -> None:
        """All specific exception types should be instantiable."""
        assert isinstance(NotFoundError("not found"), GamingHubError)
        assert isinstance(ValidationError("invalid"), GamingHubError)
        assert isinstance(DiscordError("discord error"), GamingHubError)
        assert isinstance(CalendarError("calendar error"), GamingHubError)

    @pytest.mark.unit
    def test_exception_init_without_details(self) -> None:
        """ConfigurationError should work without details."""
        exc = ConfigurationError("bad config")
        assert exc.message == "bad config"
        assert exc.details == {}
