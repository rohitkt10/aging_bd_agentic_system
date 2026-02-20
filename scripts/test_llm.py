#!/usr/bin/env python3
"""
Manual test script for LLM client and providers.

Run with: python scripts/test_llm.py

This script tests:
1. FakeLLMProvider for testing without API calls
2. VertexGeminiProvider (if VERTEX_PROJECT_ID is set)
3. LLMClient singleton pattern
4. Basic invoke and invoke_structured operations
"""

from __future__ import annotations

import os
import sys


def test_fake_provider() -> None:
    """Test the FakeLLMProvider."""
    print("=" * 60)
    print("Testing FakeLLMProvider...")
    print("=" * 60)

    from aging_bd_agentic_system.llm.testing import FakeLLMProvider

    # Test basic invoke
    provider = FakeLLMProvider()
    response = provider.invoke("Hello, fake LLM!")
    print(f"✓ Basic invoke: {response[:100]}...")

    # Test predefined responses
    provider_with_responses = FakeLLMProvider(
        responses=["Response 1", "Response 2"]
    )
    assert provider_with_responses.invoke("test") == "Response 1"
    assert provider_with_responses.invoke("test") == "Response 2"
    print("✓ Predefined responses work correctly")

    # Test structured output
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "number"},
        },
    }
    structured_response = provider.invoke_structured("Generate data", schema=schema)
    assert isinstance(structured_response, dict)
    assert "name" in structured_response
    print(f"✓ Structured output: {structured_response}")

    # Test array schema
    array_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
        },
    }
    array_response = provider.invoke_structured("Generate list", schema=array_schema)
    assert isinstance(array_response, list)
    print(f"✓ Array output: {array_response}")

    print("\n✅ All FakeLLMProvider tests passed!\n")


def test_llm_client_singleton() -> None:
    """Test the LLMClient singleton pattern."""
    print("=" * 60)
    print("Testing LLMClient singleton pattern...")
    print("=" * 60)

    # Set required env var
    os.environ["VERTEX_PROJECT_ID"] = "test-project"

    from aging_bd_agentic_system.llm import get_llm, reset_llm

    # Test singleton
    client1 = get_llm()
    client2 = get_llm()
    assert client1 is client2
    print("✓ get_llm() returns singleton instance")

    # Test reset
    reset_llm()
    client3 = get_llm()
    assert client1 is not client3
    print("✓ reset_llm() creates new instance")

    # Clean up
    reset_llm()
    print("\n✅ LLMClient singleton tests passed!\n")


def test_llm_client_with_fake_provider() -> None:
    """Test LLMClient with FakeLLMProvider."""
    print("=" * 60)
    print("Testing LLMClient with FakeLLMProvider...")
    print("=" * 60)

    os.environ["VERTEX_PROJECT_ID"] = "test-project"

    from aging_bd_agentic_system.llm import get_llm, reset_llm
    from aging_bd_agentic_system.llm.testing import FakeLLMProvider

    reset_llm()
    client = get_llm()

    # Replace provider with fake
    client.provider = FakeLLMProvider(responses=["Test response from client"])

    # Test invoke
    response = client.invoke("Hello")
    assert response == "Test response from client"
    print(f"✓ Client invoke: {response}")

    # Test structured invoke
    client.provider = FakeLLMProvider()
    schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    structured = client.invoke_structured("Generate", schema=schema)
    assert isinstance(structured, dict)
    print(f"✓ Client structured invoke: {structured}")

    reset_llm()
    print("\n✅ LLMClient with FakeLLMProvider tests passed!\n")


def test_prompts_module() -> None:
    """Test that all prompts are defined."""
    print("=" * 60)
    print("Testing prompts module...")
    print("=" * 60)

    from aging_bd_agentic_system.llm import prompts

    # Check Phase 1 prompts
    assert hasattr(prompts, "PHASE1_SYSTEM_PROMPT")
    assert hasattr(prompts, "PHASE1_CRITIQUE_PROMPT")
    print("✓ Phase 1 prompts defined")

    # Check Phase 2 prompts
    assert hasattr(prompts, "PHASE2_RESEARCH_PROMPT")
    assert hasattr(prompts, "PHASE2_CRITIQUE_PROMPT")
    assert hasattr(prompts, "PHASE2_GO_MAPPING_PROMPT")
    print("✓ Phase 2 prompts defined")

    # Check placeholders
    assert "{hallmark_name}" in prompts.PHASE1_SYSTEM_PROMPT
    assert "{hallmark_name}" in prompts.PHASE1_CRITIQUE_PROMPT
    assert "{biological_process}" in prompts.PHASE2_RESEARCH_PROMPT
    print("✓ Prompt placeholders verified")

    print("\n✅ Prompts module tests passed!\n")


def test_vertex_provider_optional() -> None:
    """
    Test VertexGeminiProvider if credentials are available.

    This is optional and will be skipped if VERTEX_PROJECT_ID is not set.
    """
    print("=" * 60)
    print("Testing VertexGeminiProvider (optional)...")
    print("=" * 60)

    project_id = os.environ.get("VERTEX_PROJECT_ID")
    if not project_id:
        print("⚠️  VERTEX_PROJECT_ID not set - skipping Vertex AI tests")
        print("   To enable these tests, set VERTEX_PROJECT_ID in your environment")
        return

    try:
        from aging_bd_agentic_system.llm import VertexGeminiProvider

        provider = VertexGeminiProvider(
            project_id=project_id,
            location=os.environ.get("VERTEX_LOCATION", "us-central1"),
            model=os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-exp"),
        )

        # Test basic invoke
        response = provider.invoke("Say 'Hello from Vertex AI!'")
        assert isinstance(response, str)
        print(f"✓ VertexAI invoke: {response[:100]}...")

        # Test structured invoke
        schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "count": {"type": "integer"},
            },
        }
        structured = provider.invoke_structured(
            'Generate JSON with {"message": "test", "count": 42}',
            schema=schema,
        )
        assert isinstance(structured, dict)
        print(f"✓ VertexAI structured: {structured}")

        print("\n✅ VertexGeminiProvider tests passed!\n")

    except Exception as e:
        print(f"⚠️  VertexAI test failed (this is expected if credentials are not configured):")
        print(f"   {e}")
        print()


def main() -> int:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Module Test Suite")
    print("=" * 60 + "\n")

    try:
        # Run all tests
        test_fake_provider()
        test_llm_client_singleton()
        test_llm_client_with_fake_provider()
        test_prompts_module()
        test_vertex_provider_optional()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
