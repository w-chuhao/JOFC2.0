"""Opt-in, one-request DeepSeek connection smoke test.

Run with: python -m scripts.test_deepseek_connection
"""

from pathlib import Path
import logging
import sys

from starter.conversation_llm import DeepSeekConversationLLM


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    client = DeepSeekConversationLLM.from_environment(project_root)
    if client is None:
        print("DeepSeek is not configured. Add DEEPSEEK_KEY to .env first.")
        return 2

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    client.max_attempts = 1
    client.max_consecutive_failures = 1
    ok, usage = client.healthcheck()
    if not ok:
        print("DeepSeek connection check failed. Check the key, model, and network.")
        return 1

    print(
        "DeepSeek connection check passed "
        f"(prompt tokens: {usage.prompt_tokens}, completion tokens: {usage.completion_tokens})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
