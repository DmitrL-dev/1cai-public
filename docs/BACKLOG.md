# Backlog

## Wiki Module (Google Code Wiki Style)

- [ ] **Testing & Verification**
    - [ ] **Environment Setup**: Deploy PostgreSQL and run full integration test of Wiki Module (Backend + Frontend).
    - [ ] **Code Sync Validation**: Verify `scripts/run_wiki_sync.py` correctly parses `src/` and populates the DB.
    - [ ] **Frontend E2E**: Check navigation, Markdown rendering, and "Create Page" flow in the React app.
    - [ ] **Optimistic Locking**: Verify editing conflict resolution (Backend logic).

- [ ] **Frontend Improvements**
    - [ ] **Search UI**: Connect search bar in Header to `WikiApi.search`.
    - [ ] **Sidebar Navigation**: Make the sidebar tree dynamic based on Namespaces (currently static).
    - [ ] **Code Linking**: Implement "Smart Links" (click on `[[Class]]` -> jump to code definition).

- [ ] **Backend Enhancements**
    - [ ] **Qdrant Integration**: Implement real vector indexing in `WikiService.upsert_page`.
    - [ ] **RAG Pipeline**: Connect `/ask` endpoint to LLM Orchestrator.
    - [ ] **Diagram Generation**: Add Mermaid.js support to `CodeSyncService` for auto-diagrams.

