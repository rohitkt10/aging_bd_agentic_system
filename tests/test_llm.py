"""
Tests for LLM client and providers.

These tests use the FakeLLMProvider to avoid actual API calls.
"""

from __future__ import annotations

import os

import pytest

from aging_bd_agentic_system.llm.client import LLMClient, get_llm, reset_llm
from aging_bd_agentic_system.llm.providers import LLMProvider
from aging_bd_agentic_system.llm.testing import FakeLLMProvider


class TestFakeLLMProvider:
    """Tests for the fake LLM provider used in testing."""

    def test_invoke_returns_response(self) -> None:
        """Test that invoke returns a response."""
        provider = FakeLLMProvider()
        response = provider.invoke("Hello")
        assert "Fake LLM response" in response
        assert "Hello" in response

    def test_invoke_uses_predefined_responses(self) -> None:
        """Test that invoke cycles through predefined responses."""
        provider = FakeLLMProvider(responses=["Response 1", "Response 2"])
        assert provider.invoke("test") == "Response 1"
        assert provider.invoke("test") == "Response 2"
        assert provider.invoke("test") == "Response 1"  # cycles back

    def test_invoke_structured_returns_dict(self) -> None:
        """Test that invoke_structured returns a dict."""
        provider = FakeLLMProvider()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        response = provider.invoke_structured("test", schema=schema)
        assert isinstance(response, dict)
        assert "name" in response

    def test_invoke_structured_handles_array_schema(self) -> None:
        """Test that invoke_structured handles array schemas."""
        provider = FakeLLMProvider()
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            },
        }
        response = provider.invoke_structured("test", schema=schema)
        assert isinstance(response, list)


class TestLLMClientIntegration:
    """Tests for LLMClient with FakeLLMProvider."""

    def setup_method(self) -> None:
        """Reset the global LLM client before each test."""
        reset_llm()

    def test_client_requires_vertex_project_id(self) -> None:
        """Test that client raises error when VERTEX_PROJECT_ID is not set."""
        # Ensure the env var is not set
        os.environ.pop("VERTEX_PROJECT_ID", None)

        with pytest.raises(ValueError, match="VERTEX_PROJECT_ID"):
            LLMClient()

    def test_client_uses_config(self) -> None:
        """Test that client reads configuration from LLMConfig."""
        from aging_bd_agentic_system.config import LLMConfig

        os.environ["VERTEX_PROJECT_ID"] = "test-project"

        config = LLMConfig(
            model="test-model",
            temperature=0.5,
            vertex_location="test-location",
        )
        client = LLMClient(config)
        assert client.provider.llm.project == "test-project"
        assert client.provider.llm.location == "test-location"
        assert client.provider.llm.model_name == "test-model"
        assert client.provider.llm.temperature == 0.5

    def test_client_invoke_delegates_to_provider(self) -> None:
        """Test that client invoke delegates to provider."""
        # This would require mocking the VertexAI provider
        # For now, we test with a fake provider
        os.environ["VERTEX_PROJECT_ID"] = "test-project"

        client = LLMClient()
        # Replace provider with fake
        client.provider = FakeLLMProvider(responses=["Test response"])

        response = client.invoke("Hello")
        assert response == "Test response"

    def test_get_llm_returns_singleton(self) -> None:
        """Test that get_llm returns the same instance."""
        os.environ["VERTEX_PROJECT_ID"] = "test-project"

        client1 = get_llm()
        client2 = get_llm()

        assert client1 is client2

    def test_reset_llm_creates_new_instance(self) -> None:
        """Test that reset_llm allows creating a new instance."""
        os.environ["VERTEX_PROJECT_ID"] = "test-project"

        client1 = get_llm()
        reset_llm()
        client2 = get_llm()

        assert client1 is not client2


class TestLLMProviderInterface:
    """Tests to verify the LLM provider interface."""

    def test_provider_has_required_methods(self) -> None:
        """Test that LLMProvider defines required abstract methods."""
        # Verify that the abstract class has the required methods
        assert hasattr(LLMProvider, "invoke")
        assert hasattr(LLMProvider, "invoke_structured")

    def test_vertex_gemini_is_provider(self) -> None:
        """Test that VertexGeminiProvider is an LLMProvider."""
        from aging_bd_agentic_system.llm.providers import VertexGeminiProvider

        # Check that it's a subclass (we can't instantiate without credentials)
        assert issubclass(VertexGeminiProvider, LLMProvider)


class TestPromptsModule:
    """Tests for the prompts module."""

    def test_phase1_prompts_exist(self) -> None:
        """Test that Phase 1 prompts are defined."""
        from aging_bd_agentic_system.llm import prompts

        assert hasattr(prompts, "PHASE1_SYSTEM_PROMPT")
        assert hasattr(prompts, "PHASE1_CRITIQUE_PROMPT")

        # Verify prompts have placeholders
        assert "{hallmark_name}" in prompts.PHASE1_SYSTEM_PROMPT
        assert "{hallmark_name}" in prompts.PHASE1_CRITIQUE_PROMPT
        assert "{processes_json}" in prompts.PHASE1_CRITIQUE_PROMPT

    def test_phase2_prompts_exist(self) -> None:
        """Test that Phase 2 prompts are defined."""
        from aging_bd_agentic_system.llm import prompts

        assert hasattr(prompts, "PHASE2_RESEARCH_SYSTEM_PROMPT")
        assert hasattr(prompts, "PHASE2_CRITIQUE_SYSTEM_PROMPT")
        assert hasattr(prompts, "PHASE2_GO_MAPPING_SYSTEM_PROMPT")
        assert hasattr(prompts, "PHASE2_DECISION_USER_PROMPT")

        # Verify prompts have expected placeholders
        assert "{biological_process}" in prompts.PHASE2_RESEARCH_SYSTEM_PROMPT
        assert "{hallmark_name}" in prompts.PHASE2_RESEARCH_SYSTEM_PROMPT
        assert "{biological_process}" in prompts.PHASE2_CRITIQUE_SYSTEM_PROMPT
        assert "{biological_process}" in prompts.PHASE2_GO_MAPPING_SYSTEM_PROMPT
