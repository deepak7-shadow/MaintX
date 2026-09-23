from pydantic import BaseModel
from typing import Optional
from enum import Enum
from uuid import UUID

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MAINTENANCE_ENGINEER = "MAINTENANCE_ENGINEER"
    SUPERVISOR = "SUPERVISOR"
    SECURITY_ANALYST = "SECURITY_ANALYST"
    AUDITOR = "AUDITOR"

class UserProfileResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    role: UserRole
    department: Optional[str] = None
    engineer_code: Optional[str] = None

class ActionResponse(BaseModel):
    success: bool
    action: str
    performed_by: str
    role: str
    message: str
