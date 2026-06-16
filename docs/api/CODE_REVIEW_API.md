# Code Review API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/code_review`

## Endpoints

### Submit Code for Review
```http
POST /api/v1/code_review/submit
{
  "code": "Функция ПолучитьДанные()...",
  "language": "bsl"
}

Response:
{
  "review_id": "rev_123",
  "quality_score": 85,
  "issues": [...]
}
```

### Auto-fix Issues
```http
POST /api/v1/code_review/{id}/autofix

Response:
{
  "fixed_code": "...",
  "fixes_applied": 3
}
```

**See:** [Code Review Guide](../06-features/CODE_REVIEW_GUIDE.md)
