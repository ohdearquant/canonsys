"""HTTP header construction utilities for API authentication."""

from typing import Literal

from pydantic import SecretStr

AUTH_TYPES = Literal["bearer", "x-api-key", "basic", "none"]

__all__ = ("AUTH_TYPES", "HeaderFactory")


class HeaderFactory:
    """Factory for constructing HTTP headers with various auth schemes.

    Supports Bearer token, x-api-key, and no-auth patterns.
    Handles SecretStr unwrapping and validation automatically.

    Example:
        >>> headers = HeaderFactory.get_header("bearer", api_key="sk-xxx")
        >>> headers
        {'Content-Type': 'application/json', 'Authorization': 'Bearer sk-xxx'}
    """

    @staticmethod
    def get_content_type_header(
        content_type: str = "application/json",
    ) -> dict[str, str]:
        """Build Content-Type header dict."""
        return {"Content-Type": content_type}

    @staticmethod
    def get_bearer_auth_header(api_key: str) -> dict[str, str]:
        """Build Authorization header with Bearer scheme."""
        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def get_x_api_key_header(api_key: str) -> dict[str, str]:
        """Build x-api-key header for providers requiring this scheme."""
        return {"x-api-key": api_key}

    @staticmethod
    def get_basic_auth_header(api_key: str) -> dict[str, str]:
        """Build Authorization header with Basic scheme."""
        import base64

        encoded = base64.b64encode(api_key.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    @staticmethod
    def get_header(
        auth_type: AUTH_TYPES,
        content_type: str | None = "application/json",
        api_key: str | SecretStr | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Construct complete HTTP headers for API requests.

        Args:
            auth_type: Authentication scheme ("bearer", "x-api-key", "basic", "none").
            content_type: Content-Type value (None to omit).
            api_key: API key (str or SecretStr, required unless auth_type="none").
            default_headers: Additional headers to merge.

        Returns:
            Complete header dict ready for HTTP client.

        Raises:
            ValueError: If api_key missing/empty when auth required, or invalid auth_type.
        """
        dict_: dict[str, str] = {}
        if content_type is not None:
            dict_ = HeaderFactory.get_content_type_header(content_type)

        if auth_type == "none":
            pass
        else:
            if isinstance(api_key, SecretStr):
                api_key = api_key.get_secret_value()

            if not api_key or not str(api_key).strip():
                raise ValueError("API key is required for authentication")

            api_key = api_key.strip()

            if auth_type == "bearer":
                dict_.update(HeaderFactory.get_bearer_auth_header(api_key))
            elif auth_type == "x-api-key":
                dict_.update(HeaderFactory.get_x_api_key_header(api_key))
            elif auth_type == "basic":
                dict_.update(HeaderFactory.get_basic_auth_header(api_key))
            else:
                raise ValueError(f"Unsupported auth type: {auth_type}")

        if default_headers:
            dict_.update(default_headers)
        return dict_
