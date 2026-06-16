from pydantic import BaseModel, EmailStr


class TenantRegistrationRequest(BaseModel):
    company_name: str
    admin_email: EmailStr
    admin_name: str
    plan: str = "starter"  # starter, professional, enterprise
