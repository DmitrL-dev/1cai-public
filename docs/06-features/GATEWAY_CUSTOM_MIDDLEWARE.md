# Gateway Custom Middleware Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
Руководство по созданию custom middleware для API Gateway.

---

## 🎯 Middleware Types

### 1. Authentication Middleware
```python
from fastapi import Request, HTTPException

async def auth_middleware(request: Request, call_next):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Missing token")
    
    # Verify token
    user = await verify_token(token)
    request.state.user = user
    
    response = await call_next(request)
    return response
```

### 2. Rate Limiting Middleware
```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("100/minute")
async def rate_limit_middleware(request: Request, call_next):
    response = await call_next(request)
    return response
```

### 3. Logging Middleware
```python
import structlog
from fastapi import Request

log = structlog.get_logger()

async def logging_middleware(request: Request, call_next):
    log.info("request_started", 
             method=request.method,
             path=request.url.path)
    
    response = await call_next(request)
    
    log.info("request_completed",
             status=response.status_code)
    
    return response
```

### 4. CORS Middleware
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.1cai.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🔧 Creating Custom Middleware

### Step 1: Define Middleware Function
```python
async def custom_middleware(request: Request, call_next):
    # Before request
    print(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # After request
    print(f"Response: {response.status_code}")
    
    return response
```

### Step 2: Register Middleware
```python
from fastapi import FastAPI

app = FastAPI()
app.middleware("http")(custom_middleware)
```

### Step 3: Test Middleware
```python
import pytest
from fastapi.testclient import TestClient

def test_custom_middleware():
    client = TestClient(app)
    response = client.get("/api/test")
    assert response.status_code == 200
```

---

## 📊 Middleware Order

**Execution Order (Request):**
```
1. CORS
2. Authentication
3. Rate Limiting
4. Logging
5. Custom Middleware
6. Route Handler
```

**Execution Order (Response):**
```
6. Route Handler
5. Custom Middleware
4. Logging
3. Rate Limiting
2. Authentication
1. CORS
```

---

## 🔐 Security Middleware

### Request Validation
```python
async def validate_request(request: Request, call_next):
    # Validate content type
    if request.method in ["POST", "PUT"]:
        if "application/json" not in request.headers.get("content-type", ""):
            raise HTTPException(400, "Invalid content type")
    
    response = await call_next(request)
    return response
```

### Security Headers
```python
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

---

**See Also:**
- [Gateway Guide](./GATEWAY_GUIDE.md)
- [Auth Guide](./AUTH_GUIDE.md)
- [Security Standards](../standards/quick-reference/SECURITY.md)
