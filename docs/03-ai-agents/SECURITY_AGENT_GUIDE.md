# Security Agent — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
Security Agent автоматизирует security audit, vulnerability scanning, compliance checking.

## Features
- 🔒 Security Audit
- 🐛 Vulnerability Scanning
- ✅ Compliance Checking (152-ФЗ)
- 🔐 Secret Detection
- 📊 Security Reports

## Quick Start
```python
from security_agent import SecurityAgent

agent = SecurityAgent()

# Security audit
audit = await agent.security_audit("/path/to/1c")

# Scan vulnerabilities
vulns = await agent.scan_vulnerabilities(code="...")

# Check compliance
compliance = await agent.check_compliance(standard="152-fz")
```

## API
```http
POST /api/v1/security/audit
POST /api/v1/security/scan
GET /api/v1/security/compliance
```

**See:** [Security Module README](../../src/modules/security/README.md)
