# Code Wiki Gap Analysis & Roadmap

## Vision
Create an intelligent, self-updating documentation system inspired by **Google Code Wiki**. The system should not just be a static text editor but a dynamic interface into the codebase, providing real-time insights, diagrams, and AI assistance.

## Feature Comparison

| Feature | Google Code Wiki | Current 1cAI Wiki | Gap / Action Item |
| :--- | :--- | :--- | :--- |
| **Content Source** | Auto-generated from code + Manual | Manual Markdown only | **Critical**: Implement `WikiCodeSync` service to parse repo and generate/update pages. |
| **diagrams** | Live Architecture/Class/Sequence | Static Images / None | **High**: Integrate `plantuml` generation based on code analysis (already partially in `scripts/`). |
| **Navigation** | Hyperlinked Code Symbols | Manual Links | **High**: Add "Smart Links" `[[code:SymbolName]]` that resolve to file/line. |
| **AI Assistant** | Integrated Gemini Chat | Stubbed "Ask Wiki" | **Medium**: Connect `WikiService.ask_wiki` to `Orchestrator` and RAG. |
| **Freshness** | Updates on every commit | Manual updates | **High**: Add Webhook/Event listener for Git pushes to trigger re-indexing. |
| **UI/UX** | Clean, Search-centric, Split-view | None (Backend only) | **Critical**: Design "Knowledge Portal" UI (React). |

## Implementation Roadmap

### Phase 1: Foundation (Current)
- [x] Basic CRUD API
- [x] Versioning & History
- [x] Markdown Support

### Phase 2: Code Integration (The "Code Wiki" Shift)
- [ ] **Symbol Indexer**: Scan `src/` and index classes/functions into Qdrant/Postgres.
- [ ] **Smart References**: Middleware to render `[[@UserService]]` as a link to the code viewer.
- [ ] **Diagram Pipeline**: Auto-generate Mermaid/PlantUML for modules on save/commit.

### Phase 3: AI & Automation
- [ ] **Auto-Docs**: LLM job to write descriptions for undocumented modules.
- [ ] **RAG Context**: Feed Wiki pages + Code graph into the AI assistant context.
- [ ] **Commit Listener**: Update "Last Modified" and "Changelog" sections in Wiki automatically.

## UX Principles (Google-like)
1.  **Search First**: Homepage is a search bar + "Recent Context".
2.  **Contextual Sidebar**: When reading docs, see relevant code files. When reading code, see relevant docs.
3.  **Zero Stale Data**: Visual warning if doc is older than the code it describes.

