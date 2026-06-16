# Archi API Module

**Status:** ✅ Registered in main.py

## Endpoints

### Export

```
POST /api/v1/archi/export
```

Export Unified Change Graph to ArchiMate XML format.

**Request:**

```json
{
  "output_filename": "architecture.archimate",
  "filters": {
    "node_types": ["Module", "Document"]
  }
}
```

**Response:**

```json
{
  "status": "success",
  "file_path": "exports/archi/architecture.archimate",
  "elements_count": 150,
  "relationships_count": 320
}
```

### Import

```
POST /api/v1/archi/import
```

Import ArchiMate model into Unified Change Graph.

**Request:**

```json
{
  "file_path": "imports/architecture.archimate"
}
```

**Response:**

```json
{
  "status": "success",
  "nodes_created": 150,
  "relationships_created": 320
}
```

### Health Check

```
GET /api/v1/archi/health
```

Check Archi integration health.

**Response:**

```json
{
  "status": "healthy",
  "exporter": "ready",
  "importer": "ready"
}
```

### Supported Types

```
GET /api/v1/archi/supported-types
```

Get supported ArchiMate element and relationship types.

**Response:**

```json
{
  "element_types": [
    "Module",
    "Function",
    "Class",
    "Document",
    "Catalog",
    "Register",
    "Configuration",
    "Form",
    "Report"
  ],
  "relationship_types": [
    "DEPENDS_ON",
    "CALLS",
    "CONTAINS",
    "USES",
    "IMPLEMENTS"
  ],
  "archimate_version": "3.1"
}
```

## Usage Examples

### Python

```python
import httpx

# Export
response = httpx.post(
    "http://localhost:8000/api/v1/archi/export",
    json={"output_filename": "my_arch.archimate"}
)
print(response.json())

# Import
response = httpx.post(
    "http://localhost:8000/api/v1/archi/import",
    json={"file_path": "imports/arch.archimate"}
)
print(response.json())
```

### cURL

```bash
# Export
curl -X POST http://localhost:8000/api/v1/archi/export \
  -H "Content-Type: application/json" \
  -d '{"output_filename": "test.archimate"}'

# Import
curl -X POST http://localhost:8000/api/v1/archi/import \
  -H "Content-Type: application/json" \
  -d '{"file_path": "imports/test.archimate"}'

# Health
curl http://localhost:8000/api/v1/archi/health
```

## Integration with Archi Tool

1. **Export from 1C AI Stack:**

   ```bash
   POST /api/v1/archi/export
   ```

2. **Open in Archi:**

   - Launch Archi tool
   - File → Import → ArchiMate Model Exchange File
   - Select exported `.archimate` file
   - View architecture diagrams

3. **Import back to 1C AI Stack:**
   - Design in Archi
   - File → Export → ArchiMate Model Exchange File
   - Import via API:
     ```bash
     POST /api/v1/archi/import
     ```

## Files

- `src/api/archi_api.py` — API endpoints
- `src/exporters/archi_exporter.py` — Export logic
- `src/exporters/archi_importer.py` — Import logic
