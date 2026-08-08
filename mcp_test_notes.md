# MCP Test Notes — Day 23

## Setup note: SDK and registration process both differ from the mission's instructions

Two things had changed since the mission's instructions were written, discovered during setup:

1. **`mcp` package (2.0.0) API**: the older `mcp.server.fastmcp.FastMCP` class no longer exists. The current package uses `mcp.server.mcpserver.MCPServer`, with the same `.tool()` decorator pattern and `.run(transport='stdio')` — same concept, renamed class.

2. **Claude Desktop's registration process**: manual editing of `claude_desktop_config.json` is no longer the primary path. The app now uses a **Desktop Extensions (.mcpb)** system — packaged ZIP bundles containing a `manifest.json` and the server code, installed via Settings → Extensions → Advanced settings → Extension Developer → Install Extension. Confirmed via the current official Claude Help Center article (support.claude.com), since this wasn't discoverable just from the app's Developer settings alone.

## Building the .mcpb bundle

Used Anthropic's official CLI (`npm install -g @anthropic-ai/mcpb`, then `mcpb init` / `mcpb validate` / `mcpb pack`) rather than hand-authoring `manifest.json`, to stay conformant with the spec.

### Bug found and fixed during setup: wrong Python interpreter

The first packaged version failed to load with:
```
ModuleNotFoundError: No module named 'mcp'
```
The extension's logs showed Claude Desktop had resolved `"command": "python"` (the default `mcpb init` generated) to an unrelated system Python install (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`), not the project's venv where `mcp`, `chromadb`, `sentence-transformers`, etc. are actually installed.

**Fix:** changed `manifest.json`'s `mcp_config.command` to the absolute path of the project's venv Python:
```json
"command": "/Users/utkarshmavi/Desktop/ABTalks - AI Cohort/Daily Task/.venv/bin/python3"
```
Repackaged and reinstalled — resolved the error immediately, confirmed via "Server started and connected successfully" in the extension logs with no further errors.

### Architecture note

Rather than duplicating `mcp_server.py` and its dependencies (`retrieval_engine.py`, `coverage.db`, `chroma_data/`, etc.) inside the bundle, `server/main.py` is a thin wrapper that adds the real project root to `sys.path` and runs the actual `mcp_server.py` by absolute path via `runpy.run_path()`. This keeps the bundle small and avoids maintaining two copies of the server logic, at the cost of the bundle only working on this specific machine (not portable to another user's install) — an acceptable tradeoff for a personal local tool, not a publicly distributed extension.

## Step 5: Registration confirmed

After fixing the interpreter path, Claude Desktop's Settings → Extensions → Local MCP servers showed:
- Status: **Enabled** (no longer "failed")
- Two tools listed under "Tool permissions": **Check coverage**, **Get claim status**
- Permission level: "Needs approval" (each tool call requires explicit user approval before running)

## Step 5: Test 1 — check_coverage

**Question asked in Claude Desktop:** "Is cosmetic surgery covered under my Gold PPO plan?"

**Result:** Tool call approved and executed successfully. Claude's response correctly stated cosmetic surgery is excluded, listed the other excluded services (adult dental care, long-term care, private-duty nursing, adult routine eye care, weight loss programs), and included the plan's exact pricing data returned by the tool ($500/month premium, $2,000 deductible, 10% copay) — confirming the tool's combined output (policy excerpts + plan pricing from Day 4's data) was correctly used to ground the answer. Claude also added a helpful, appropriately-hedged note distinguishing cosmetic vs. reconstructive surgery, without fabricating anything not in the tool's actual response.

## Step 6: Test 2 — get_claim_status

**Question asked in Claude Desktop:** "What's the status of claim C1001?"

**Result:** Tool call approved and executed successfully. Response: "Claim C1001 is currently Pending. Procedure: X-ray. Amount: $250. Filed: April 1, 2023." — matches the `claims` table in `coverage.db` exactly.

## Summary

Both tools confirmed working end-to-end through Claude Desktop's live MCP integration: correct registration, correct tool-call approval flow, and correct, accurately-grounded answers for both `check_coverage` and `get_claim_status`. The main real-world friction was the Python interpreter path defaulting incorrectly during bundle creation — worth remembering for any future MCP bundle: always explicitly set `mcp_config.command` to the exact interpreter with your dependencies installed, never trust the CLI's `"python"` default.
