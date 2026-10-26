"""List prices used for every cost figure (standard library only, so offline checks need no Azure packages)."""

# USD per million tokens. Anthropic list prices read 2026-10-26 from
# https://platform.claude.com/docs/en/about-claude/pricing ; Claude in Microsoft
# Foundry bills the same standard rates (Global Standard, no data-zone premium).
# Haiku 5.5 rates are the <=100k-token-prompt tier; every prompt here is far below it.
PRICES = {
    "claude-opus-5-5": {"input": 4.0, "write_5m": 5.0, "write_1h": 8.0, "read": 0.20, "output": 20.0},
    "claude-sonnet-5-5": {"input": 2.0, "write_5m": 2.5, "write_1h": 4.0, "read": 0.10, "output": 10.0},
    "claude-haiku-5-5": {"input": 0.10, "write_5m": 0.125, "write_1h": 0.20, "read": 0.01, "output": 0.50},
}


def cost_usd(model, usage):
    if not usage:
        return None
    price = PRICES[model]
    creation = usage.get("cache_creation") or {}
    write_1h = creation.get("ephemeral_1h_input_tokens", 0) or 0
    write_total = usage.get("cache_creation_input_tokens", 0) or 0
    write_5m = max(write_total - write_1h, 0)
    total = (
        (usage.get("input_tokens", 0) or 0) * price["input"]
        + write_5m * price["write_5m"]
        + write_1h * price["write_1h"]
        + (usage.get("cache_read_input_tokens", 0) or 0) * price["read"]
        + (usage.get("output_tokens", 0) or 0) * price["output"]
    )
    return total / 1_000_000
