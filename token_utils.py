"""
token_utils.py
Day 26 — Token counting for cost/usage tracking.
"""

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return an approximate token count for `text`.

    Uses tiktoken's cl100k_base encoding as a reasonable general-purpose
    estimate. Note: this project's actual LLM (qwen3:8b via Ollama) uses a
    different tokenizer internally, so this is an approximation -- the
    same caveat already noted back in Day 20's token-budget work.
    """
    if not text:
        return 0
    return len(_ENCODING.encode(text))


if __name__ == "__main__":
    samples = [
        "What's my copay on the Gold PPO plan?",
        "",
        "Your copay for the Gold PPO plan is 10%. This is not medical advice.",
    ]
    for s in samples:
        print(f"{count_tokens(s)} tokens: {s!r}")
