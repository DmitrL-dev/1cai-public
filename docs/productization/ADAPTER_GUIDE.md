# 1cAI Adapter Guide

## Adapter Principles

- Keep adapters optional.
- Dry-run first.
- Record evidence for every run/import.
- Route risky actions through policy, approval and audit.
- Never make a third-party product the source of truth for internal ALM records.

## Test Runner Adapters

Supported adapter ids:

- `yaxunit`
- `vanessa`
- `1c_tester`
- `bsl_manifest`

Each customer profile should define command, working directory, environment variables, timeout and expected result files.

## ALM/BA Adapters

External Jira, Confluence, Azure DevOps, DOORS, Polarion, TestRail and ServiceNow integrations are customer-paid extensions. The internal 1cAI artifact graph remains the source of truth.

## EDT-MCP Adapters

Write/execute tools must require confirmation, actor, approval reason and audit event. Unknown tools are treated as risky until classified.
