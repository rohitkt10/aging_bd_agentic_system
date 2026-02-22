#!/usr/bin/env python3
"""
Test OpenAI integration.

Verifies that OpenAI models can be invoked through the LLM client.

Usage:
    python scripts/test_openai_integration.py

Requires OPENAI_API_KEY in .env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def main() -> int:
    print("\n" + "=" * 50)
    print("OpenAI Integration Test")
    print("=" * 50)

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n❌ OPENAI_API_KEY not found in environment")
        print("   Add it to your .env file:")
        print("   OPENAI_API_KEY=sk-your-key-here")
        return 1

    # Force OpenAI provider
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["OPENAI_MODEL"] = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Import after setting env vars
    from aging_bd_agentic_system.llm import get_llm, reset_llm

    reset_llm()  # Clear any cached client

    print(f"\nModel: {os.environ['OPENAI_MODEL']}")

    # Test 1: Simple invoke
    print("\n--- Test 1: Simple invoke ---")
    llm = get_llm()
    response = llm.invoke("Say 'OpenAI integration works' and nothing else.")
    print(f"Response: {response}")

    if "OpenAI integration works" not in response:
        print("❌ Response doesn't contain expected text")
        return 1

    # Test 2: Structured output
    print("\n--- Test 2: Structured output ---")
    schema = {
        "title": "test_response",
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "success": {"type": "boolean"},
        },
        "required": ["message", "success"],
    }

    result = llm.invoke_structured(
        "Return a JSON object with message='test passed' and success=true",
        schema=schema,
    )
    print(f"Structured result: {result}")

    if not result.get("success"):
        print("❌ Structured output returned success=false")
        return 1

    print("\n" + "=" * 50)
    print("✅ OpenAI integration tests passed")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
