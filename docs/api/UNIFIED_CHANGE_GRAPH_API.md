# Unified Change Graph API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/graph`

## Endpoints

### Build Graph
```http
POST /api/v1/graph/build
{
  "source_path": "/path/to/1c/project",
  "language": "bsl"
}
```

### Impact Analysis
```http
POST /api/v1/graph/impact
{
  "graph_id": "graph_123",
  "changed_files": ["Module1.bsl"]
}
```

### Export Graph
```http
GET /api/v1/graph/{id}/export?format=dot
GET /api/v1/graph/{id}/export?format=json
```

**See:** [Unified Change Graph Guide](../06-features/UNIFIED_CHANGE_GRAPH_GUIDE.md)
