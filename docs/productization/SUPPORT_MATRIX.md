# 1cAI Enterprise Support Matrix

## Runtime

| Area | Supported baseline | Notes |
| --- | --- | --- |
| OS | Windows Server 2019+, Windows 10/11 for workstation use | Primary 1C/EDT runner profile is Windows. |
| Python | 3.11 | Current validated local path: `C:\Python311\python.exe`. |
| Node | 20+ | Portal build uses Vite, React and TanStack Router. |
| Browser | Current Chrome, Edge, Firefox | Portal is a standard SPA. |

## 1C Tooling

| Tool | Support level | Notes |
| --- | --- | --- |
| EDT unpacked XML | Supported | Canonical metadata import and drift. |
| YAxUnit | Adapter-ready | Dry-run and result import supported; live execution needs local profile. |
| Vanessa | Adapter-ready | Generic runner plan and evidence import supported. |
| 1C:Tester | Import/adapter-ready | Customer runner profile required. |
| EDT-MCP | Bridge-ready | Risk classification and approval path exist. |

## Storage

| Store | Support level |
| --- | --- |
| Local JSON/NDJSON | Baseline on-prem mode |
| SQLite Rentgen store | Existing Rentgen analysis mode |
| PostgreSQL | Existing app modules; product governance migration planned |

## AI Providers

The deterministic governance core works without AI. LLM providers are optional accelerators and must cite artifact, policy and evidence sources.
