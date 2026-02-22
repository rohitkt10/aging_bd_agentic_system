"""
Test utilities for LLM module.

Provides fake/mock LLM provider for testing without actual API calls.
"""

from __future__ import annotations

from typing import Any


class FakeLLMProvider:
    """
    Fake LLM provider for testing.

    Returns predictable responses without making actual API calls.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        structured_responses: list[dict[str, Any]] | None = None,
    ):
        """
        Initialize fake provider with predetermined responses.

        Args:
            responses: List of responses to cycle through (optional).
                      If None, returns a simple echo response.
            structured_responses: List of structured responses for invoke_structured (optional).
        """
        self.responses = responses or []
        self.structured_responses = structured_responses or []
        self.call_count = 0
        self.structured_call_count = 0

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """
        Return a fake response.

        Args:
            prompt: The input prompt (ignored)
            **kwargs: Additional parameters (ignored)

        Returns:
            A fake response string
        """
        self.call_count += 1

        if self.responses:
            # Cycle through predetermined responses
            return self.responses[(self.call_count - 1) % len(self.responses)]

        # Default: echo back a summary of the prompt
        preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        return f"Fake LLM response to: {preview}"

    def invoke_structured(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """
        Return a fake structured response.

        Args:
            prompt: The input prompt (ignored)
            schema: Expected output schema (used to shape response)
            **kwargs: Additional parameters (ignored)

        Returns:
            A fake structured response matching the schema
        """
        self.structured_call_count += 1

        # If structured_responses provided, cycle through them
        if self.structured_responses:
            return self.structured_responses[
                (self.structured_call_count - 1) % len(self.structured_responses)
            ]

        # Try to create a minimal valid response based on schema
        if "type" in schema:
            schema_type = schema["type"]

            if schema_type == "array":
                # Return an array with one item based on item schema
                item_schema = schema.get("items", {})
                return [self._make_fake_structured(item_schema)]

            elif schema_type == "object":
                return self._make_fake_structured(schema)

        # Fallback: return minimal dict
        return {"result": "fake response"}

    def _make_fake_structured(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Create a fake structured response based on schema."""
        result: dict[str, Any] = {}

        for prop_name, prop_schema in schema.get("properties", {}).items():
            prop_type = prop_schema.get("type", "string")

            if prop_name == "grade":
                result[prop_name] = "pass"
            elif prop_name == "comment":
                result[prop_name] = "Fake comment for testing"
            elif prop_name == "score":
                result[prop_name] = 7
            elif prop_type == "array":
                result[prop_name] = []
            elif prop_type == "string":
                result[prop_name] = f"fake_{prop_name}"
            elif prop_type == "integer":
                result[prop_name] = 1

        return result
