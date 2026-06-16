# Wiki Module Documentation

## Vision & Roadmap (Google Code Wiki Standard)

We aim to match **Google Code Wiki** standards:
1.  **Living Documentation**: Auto-updated from code.
2.  **Deep Linking**: Symbols in docs link directly to code definitions.
3.  **Visuals**: Auto-generated architecture diagrams.

## Features

- **Page Management**: Create, Read, Update, Delete (Soft) pages.
- **Versioning**: Full history of changes with optimistic locking.
- **Blueprints**: Create pages from predefined templates.
- **Attachments**: Upload and link files to pages.
- **Comments**: Threaded discussions on pages.
- **Search**: Semantic search (Planned Qdrant integration).
- **AI Integration**: "Ask Wiki" feature (Stubbed).

## Architecture

### Data Model

The module uses a relational database (PostgreSQL) with the following entities:

- `wiki_namespaces`: Hierarchical organization.
- `wiki_pages`: Main metadata (slug, title, version).
- `wiki_revisions`: Content history (immutable).
- `wiki_comments`: Threaded comments.
- `wiki_blueprints`: Templates.

> **Note on ORM**: While `src/services/wiki/orm.py` defines SQLAlchemy models for schema management, the runtime service `src/services/wiki/service.py` uses optimized raw SQL via `asyncpg`.

### API Reference

Base URL: `/api/v1/wiki`

#### Pages

- `GET /pages/{slug}`: Get page content.
- `POST /pages`: Create a new page.
- `PUT /pages/{slug}`: Update page content (requires `version` for optimistic locking).
- `POST /preview`: Render Markdown to HTML.

#### Comments

- `GET /pages/{page_id}/comments`: List comments.
- `POST /pages/{page_id}/comments`: Add a comment.

#### Attachments

- `POST /attachments/upload`: Upload a file.

## Usage Examples

### Creating a Page

```json
POST /api/v1/wiki/pages
{
  "slug": "architecture-overview",
  "title": "Architecture Overview",
  "content": "# Architecture\n\nThis is the main doc...",
  "namespace": "engineering",
  "commit_message": "Initial draft"
}
```

### Updating a Page

```json
PUT /api/v1/wiki/pages/architecture-overview
{
  "content": "# Architecture\n\nUpdated content...",
  "version": 1,
  "commit_message": "Fixed typos"
}
```

## Configuration

The module relies on the following services:
- **PostgreSQL**: For storage.
- **Qdrant** (Optional): For semantic search.

## Development Status & Roadmap

- [x] Core Backend API
- [x] Versioning Logic
- [ ] Frontend UI (React Components)
- [ ] Real Qdrant Integration
- [ ] Namespace Management API
- [ ] Export to PDF/Confluence

