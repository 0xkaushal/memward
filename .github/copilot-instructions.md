# Copilot Instructions

Read [AGENTS.md](../AGENTS.md) before making changes in this repository.

Project-specific requirements live in [AGENTS.md](../AGENTS.md) and should be treated as the authoritative instructions for:
- architecture decisions
- scope boundaries and out-of-scope items
- build order and current project direction
- coding-agent expectations for this repo

Do not duplicate that guidance here. If this file conflicts with [AGENTS.md](../AGENTS.md), follow [AGENTS.md](../AGENTS.md).

## Memory — save and retrieve via MCP tools

This workspace has a memward MCP server configured. Use the tools below proactively:

### When to call `save_memory`
- After the user states a preference, habit, or strong opinion ("I always use uv", "never add docstrings")
- After a significant architecture or tooling decision is made in the conversation
- After a bug root-cause is identified and resolved
- When the user explicitly asks you to remember something
- At the end of a long session if notable facts were established

Call format:
```
save_memory(content="<concise fact>", source="copilot")
```
Keep `content` to one or two sentences — extract the signal, not the full conversation.

### When to call `search_memory`
- At the start of a new task to surface relevant context from past sessions
- Before making a tech-stack recommendation — check if the user has stated preferences before
- When the user references something from a past session you don't have context for

Call format:
```
search_memory(query="<what you're looking for>", limit=5)
```

### Important
- Only `status=approved` memories are returned by `search_memory`. Do not assume the user has reviewed every saved memory.
- Both tools are best-effort. If the MCP server is not running, continue working — do not block on memory operations.