# Code Approval API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/code_approval`

## Endpoints

### Submit for Review
```http
POST /api/v1/code_approval/submit
{
  "code": "...",
  "description": "Feature: User authentication",
  "reviewers": ["reviewer1", "reviewer2"]
}
```

### Approve
```http
POST /api/v1/code_approval/{id}/approve
{"comment": "LGTM!"}
```

### Reject
```http
POST /api/v1/code_approval/{id}/reject
{"comment": "Needs refactoring"}
```

### Get Status
```http
GET /api/v1/code_approval/{id}
```

**See:** [Code Approval Guide](../06-features/CODE_APPROVAL_GUIDE.md)
