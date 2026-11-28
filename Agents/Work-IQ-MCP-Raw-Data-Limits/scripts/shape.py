"""Describe a JSON value by its structure and sizes, without its text.

Used for everything that leaves the private evidence folder: a real mailbox answer is reduced to
key names, counts, lengths and numbers. Error codes and messages are kept, they describe the service.
"""
SHOW_TEXT = {"code", "message", "error", "type", "contentType", "odata.type", "@odata.type", "name_of_tool", "strategy"}


def shape(value, key="", depth=0):
    if isinstance(value, dict):
        if depth > 6:
            return f"object({len(value)} keys)"
        return {k: shape(v, k, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        return {"count": len(value), "first": shape(value[0], key, depth + 1)}
    if isinstance(value, str):
        if key in SHOW_TEXT:
            return value[:400]
        return f"text({len(value)} chars)"
    return value


def tool_result(response):
    """Split an MCP tools/call answer into (is_error, text parts, structuredContent)."""
    if not isinstance(response, dict):
        return None, [], None
    if "error" in response:
        return True, [str(response["error"])], None
    result = response.get("result", {})
    texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    return bool(result.get("isError")), texts, result.get("structuredContent")
