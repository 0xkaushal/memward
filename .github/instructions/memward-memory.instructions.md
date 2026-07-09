---
applyTo: "**"
---

## Memory — automatic recall and capture (memward MCP)

This workspace has a memward MCP server. These rules apply to **every session** without exception.

### On session start — ALWAYS call search_memory first

Before responding to the user's first message, call `search_memory` to surface relevant context:

```
search_memory(query="<short summary of the user's opening task or question>", limit=5)
```

Use the results to silently inform your response. Do not quote memory entries verbatim unless the user asks; just let them shape what you say.

### During the session — call save_memory when any of these happen

| Trigger | Example |
|---|---|
| User states a preference or habit | "I always use uv", "never add docstrings" |
| Architecture or tooling decision made | chose Supabase over RDS, added CORS |
| Bug root-cause identified and fixed | "the 404 was because the old process was still running" |
| Task completed with a non-obvious approach | specific command, workaround, or pattern discovered |
| User explicitly asks you to remember something | "remember this for next time" |

```
save_memory(content="<one or two sentence fact>", source="copilot")
```

Extract the signal. Do not save raw conversation text — save the distilled fact.

### Rules

- **Do not skip the opening search_memory** even if the task seems simple. The overhead is one tool call.
- **Do not ask the user's permission** to save a memory when a trigger above fires. Just call it.
- If the MCP server is not running, skip silently and continue working.
- Only `status=approved` memories come back from `search_memory`. If results are empty, proceed normally.
