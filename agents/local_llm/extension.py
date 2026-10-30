"""Bounded MCP helper for the operator-approved localhost advisory operation."""

import json
import sys
from local_llm import Client, LocalError

NAME = "aceis_local_llm_generate"


def definition():
    return {
        "name": NAME,
        "description": "Ask the existing localhost AceIS coding model for an UNVERIFIED advisory response. "
                       "No files, commands, model loading or generated code are executed.",
        "inputSchema": {"type": "object", "properties": {
            "task": {"type": "string", "enum": ["draft", "review"]},
            "prompt": {"type": "string", "minLength": 1,
                       "description": "Explicit source/specification, at most 16384 UTF-8 bytes"},
            "max_tokens": {"type": "integer", "minimum": 1, "maximum": 1024, "default": 256}},
            "required": ["task", "prompt"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False,
                        "idempotentHint": False, "openWorldHint": False},
    }


def dispatch(name, arguments, client=None):
    try:
        if (name != NAME or not isinstance(arguments, dict)
                or set(arguments) - {"task", "prompt", "max_tokens"}
                or not {"task", "prompt"} <= set(arguments)):
            raise LocalError("INVALID_INPUT", "Unsupported tool or arguments")
        data = (client or Client()).generate(arguments["task"], arguments["prompt"],
                                            arguments.get("max_tokens", 256))
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                "structuredContent": data, "isError": False}
    except LocalError as exc:
        data = {"error": exc.code, "message": str(exc), "automatic_retry": False,
                "verification_status": "NOT_EXECUTED"}
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                "structuredContent": data, "isError": True}


if __name__ == "__main__":
    if sys.argv[1:] == ["--call"]:
        try:
            raw = sys.stdin.buffer.read(32769)
            if len(raw) > 32768:
                raise ValueError("Input frame exceeds bound")
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {"name", "arguments"}:
                raise ValueError("Expected one explicit tool call")
            result = dispatch(value["name"], value["arguments"])
        except (ValueError, UnicodeError, TypeError, OSError):
            result = {"isError": True, "structuredContent": {"error": "INVALID_INPUT",
                      "automatic_retry": False, "verification_status": "NOT_EXECUTED"}}
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(1 if result["isError"] else 0)
    elif not sys.argv[1:]:
        print(json.dumps(definition(), ensure_ascii=False, indent=2))
    else:
        raise SystemExit("Use no arguments for the schema, or --call with one JSON input frame")
