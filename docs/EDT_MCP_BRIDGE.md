# 1cAI EDT-MCP Bridge

This note captures the first integration layer inspired by DitriXNew/EDT-MCP.

## Why It Matters

EDT-MCP is valuable because it runs inside 1C:EDT and can answer questions that
static file analysis cannot:

- semantic query validation in project context;
- content assist, symbol info, definitions and references;
- WYSIWYG form layout snapshots and screenshots;
- safe module writes with `contentHash` / `expectedSource`;
- cascading metadata create/rename/delete through EDT;
- real YAXUnit runs and debug sessions;
- progressive tool disclosure to keep MCP context small.

1cAI should use this as the EDT-native execution bridge while Rentgen remains
the whole-configuration analysis, risk, governance and release-control layer.

## Implemented Now

- API: `GET /api/v1/edt-mcp/toolsets`
- API: `POST /api/v1/edt-mcp/plan`
- API: `GET /api/v1/edt-mcp/connection-config`
- API: `GET /api/v1/edt-mcp/status`
- API: `GET /api/v1/edt-mcp/live-tools`
- API: `POST /api/v1/edt-mcp/call`
- MCP tool: `edt_mcp_toolsets`
- MCP tool: `edt_mcp_plan`
- MCP tool: `edt_mcp_connection_config`
- MCP tool: `edt_mcp_status`
- MCP tool: `edt_mcp_live_tools`
- MCP tool: `edt_mcp_call`
- UI: `/edt-mcp`

The planner maps user tasks to:

- EDT-MCP toolsets to reveal;
- EDT-MCP tools to call;
- 1cAI companion tools to run around them;
- safety notes and confirmation requirements.

The live bridge:

- probes `/health` and `/mcp`;
- initializes the MCP session using protocol `2025-11-25`;
- reads `tools/list` and enriches each live tool with a 1cAI risk classification;
- calls `tools/call` through a local safety gate;
- allows read-only tools by default;
- blocks write, execute, mixed-risk and unknown tools unless `confirm=true`,
  `actor` and `approval_reason` are present;
- writes blocked/confirmed risky calls to the shared security audit logger without
  storing raw tool arguments or EDT-MCP tokens;
- supports internal approval records in `data/approval_records.json`; approved
  records are matched by tool, actor, risk and optional argument constraints
  such as `modulePath`, then consumed after successful live calls;
- can require approval records for all risky calls with
  `EDT_MCP_REQUIRE_APPROVAL_RECORD=1`;
- rejects non-loopback `base_url` values by default to avoid turning 1cAI into a network proxy;
- accepts the EDT-MCP shared token through `X-EDT-MCP-Token`.

Remote EDT-MCP endpoints are intentionally disabled by default. Set
`EDT_MCP_ALLOW_REMOTE=1` only in a trusted isolated deployment where routing,
auth and audit are owned by the customer environment.

## Product Rule

Use EDT-MCP for live EDT semantics. Use 1cAI/Rentgen for blast radius, quality,
requirements, release gates, ownership, incident response and management views.

## Reuse Note

The public EDT-MCP repository is AGPL-3.0. The user says the authors are known
and direct code reuse is allowed; before vendoring Java code into 1cAI, keep a
written permission or dual-license note in the project record.

## Next Hardening

1. Add customer-specific policy-as-code around metadata deletes, launch/debug and `update_database`.
2. Let release/change gates pre-create approvals automatically from their reviewed plans.
3. Package EDT-MCP installation checks into offline readiness.
4. Vendor or dual-license only the Java plugin pieces that are explicitly cleared for 1cAI distribution.
