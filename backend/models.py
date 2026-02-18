from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime, date
from bson import ObjectId

# Helper for ObjectId serialization
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

# ========== EMPLOYEE MODELS ==========

class EmployeeBase(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=20)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(..., min_length=2, max_length=50)

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeInDB(EmployeeBase):
    id: Optional[PyObjectId] = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "full_name": "John Doe",
                "email": "john@example.com",
                "department": "Engineering"
            }
        }

class EmployeeResponse(EmployeeBase):
    id: str = Field(alias="_id")
    created_at: str
    
    @validator("created_at", pre=True)
    def format_date(cls, v):
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v

# ========== ATTENDANCE MODELS ==========

class AttendanceBase(BaseModel):
    employee_id: str  # This will store the MongoDB ObjectId as string
    date: date
    status: str = Field(..., pattern="^(Present|Absent)$")

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceInDB(AttendanceBase):
    id: Optional[PyObjectId] = Field(alias="_id")
    marked_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class AttendanceResponse(AttendanceBase):
    id: str = Field(alias="_id")
    employee_name: Optional[str] = None
    employee_details: Optional[dict] = None
    marked_at: str
    
    @validator("marked_at", pre=True)
    def format_marked_at(cls, v):
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v
    
    @validator("date", pre=True)
    def format_date(cls, v):
        if isinstance(v, date):
            return v.strftime("%Y-%m-%d")
        return v