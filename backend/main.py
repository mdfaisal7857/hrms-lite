from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, date
from bson import ObjectId
import traceback

from database import connect_to_mongo, close_mongo_connection, get_database
from models import (
    EmployeeCreate, EmployeeInDB, EmployeeResponse,
    AttendanceCreate, AttendanceInDB, AttendanceResponse
)

# Initialize FastAPI
app = FastAPI(
    title="HRMS Lite API",
    description="Simple Employee & Attendance Management System",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "http://localhost:3000",
        "http://localhost:5000",
        "https://vercel.com/faisals-projects-c69451ab/hrms-lite",  # Your Vercel URL (after deployment)
        "https://hrms-lite-frontend.vercel.app"  # Alternative
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== DATABASE EVENTS ==========

@app.on_event("startup")
async def startup_event():
    """Connect to database on startup"""
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await close_mongo_connection()

# ========== HELPER FUNCTIONS ==========

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

# ========== EMPLOYEE APIs ==========

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "HRMS Lite API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/api/employees", response_model=dict)
async def get_all_employees():
    """Get all employees"""
    try:
        db = get_database()
        cursor = db.employees.find().sort("created_at", -1)
        employees = await cursor.to_list(length=None)
        
        # Convert ObjectId to string for JSON response
        for emp in employees:
            emp["_id"] = str(emp["_id"])
            if "created_at" in emp:
                emp["created_at"] = emp["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "status": "success",
            "data": employees,
            "count": len(employees)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/employees", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_employee(employee: EmployeeCreate):
    """Add a new employee"""
    try:
        db = get_database()
        
        # Check if employee_id already exists
        existing_emp = await db.employees.find_one({"employee_id": employee.employee_id})
        if existing_emp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Employee ID '{employee.employee_id}' already exists"
            )
        
        # Check if email already exists
        existing_email = await db.employees.find_one({"email": employee.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{employee.email}' is already registered"
            )
        
        # Create new employee
        new_employee = {
            "employee_id": employee.employee_id,
            "full_name": employee.full_name,
            "email": employee.email,
            "department": employee.department,
            "created_at": datetime.utcnow()
        }
        
        result = await db.employees.insert_one(new_employee)
        created_employee = await db.employees.find_one({"_id": result.inserted_id})
        
        # Format for response
        created_employee["_id"] = str(created_employee["_id"])
        created_employee["created_at"] = created_employee["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "status": "success",
            "message": "Employee added successfully",
            "data": created_employee
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/employees/{employee_id}", response_model=dict)
async def get_employee(employee_id: str):
    """Get a single employee by ID"""
    try:
        db = get_database()
        
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )
        
        employee = await db.employees.find_one({"_id": ObjectId(employee_id)})
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Format for response
        employee["_id"] = str(employee["_id"])
        employee["created_at"] = employee["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "status": "success",
            "data": employee
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.delete("/api/employees/{employee_id}", response_model=dict)
async def delete_employee(employee_id: str):
    """Delete an employee by ID"""
    try:
        db = get_database()
        
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )
        
        # Find the employee
        employee = await db.employees.find_one({"_id": ObjectId(employee_id)})
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Delete employee
        await db.employees.delete_one({"_id": ObjectId(employee_id)})
        
        # Delete all attendance records for this employee
        await db.attendances.delete_many({"employee_id": employee_id})
        
        return {
            "status": "success",
            "message": f"Employee {employee['full_name']} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ========== ATTENDANCE APIs ==========

@app.post("/api/attendance", response_model=dict, status_code=status.HTTP_201_CREATED)
async def mark_attendance(attendance: AttendanceCreate):
    """Mark attendance for an employee"""
    try:
        db = get_database()
        
        # Check if employee exists
        if not ObjectId.is_valid(attendance.employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )
        
        employee = await db.employees.find_one({"_id": ObjectId(attendance.employee_id)})
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {attendance.employee_id} not found"
            )
        
        # Validate status
        if attendance.status not in ["Present", "Absent"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Status must be either "Present" or "Absent"'
            )
        
        # Check if attendance already marked for this date
        date_str = attendance.date.strftime("%Y-%m-%d")
        existing = await db.attendances.find_one({
            "employee_id": attendance.employee_id,
            "date": date_str
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attendance already marked for {employee['full_name']} on {date_str}"
            )
        
        # Create attendance record
        new_attendance = {
            "employee_id": attendance.employee_id,
            "date": date_str,
            "status": attendance.status,
            "marked_at": datetime.utcnow()
        }
        
        result = await db.attendances.insert_one(new_attendance)
        created = await db.attendances.find_one({"_id": result.inserted_id})
        
        # Format for response
        created["_id"] = str(created["_id"])
        created["marked_at"] = created["marked_at"].strftime("%Y-%m-%d %H:%M:%S")
        created["employee_name"] = employee["full_name"]
        
        return {
            "status": "success",
            "message": f"Attendance marked for {employee['full_name']}",
            "data": created
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/attendance", response_model=dict)
async def get_attendance(date: Optional[str] = None):
    """Get attendance records (optionally filtered by date)"""
    try:
        db = get_database()
        
        # Build query
        query = {}
        if date:
            query["date"] = date
        
        # Get attendance records
        cursor = db.attendances.find(query).sort("date", -1)
        records = await cursor.to_list(length=None)
        
        # Get all employees for reference
        employees = {}
        emp_cursor = db.employees.find()
        async for emp in emp_cursor:
            employees[str(emp["_id"])] = emp
        
        # Format records
        formatted_records = []
        for record in records:
            record["_id"] = str(record["_id"])
            emp = employees.get(record["employee_id"], {})
            formatted_records.append({
                "_id": record["_id"],
                "employee_id": record["employee_id"],
                "employee_name": emp.get("full_name", "Unknown"),
                "employee_details": {
                    "employee_id": emp.get("employee_id", "N/A"),
                    "department": emp.get("department", "N/A")
                },
                "date": record["date"],
                "status": record["status"],
                "marked_at": record["marked_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(record["marked_at"], datetime) else record["marked_at"]
            })
        
        return {
            "status": "success",
            "data": formatted_records,
            "count": len(formatted_records)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/attendance/employee/{employee_id}", response_model=dict)
async def get_employee_attendance(employee_id: str):
    """Get attendance records for a specific employee"""
    try:
        db = get_database()
        
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )
        
        # Check if employee exists
        employee = await db.employees.find_one({"_id": ObjectId(employee_id)})
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {employee_id} not found"
            )
        
        # Get attendance records
        cursor = db.attendances.find({"employee_id": employee_id}).sort("date", -1)
        records = await cursor.to_list(length=None)
        
        # Format records
        formatted_records = []
        for record in records:
            record["_id"] = str(record["_id"])
            formatted_records.append({
                "_id": record["_id"],
                "date": record["date"],
                "status": record["status"],
                "marked_at": record["marked_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(record["marked_at"], datetime) else record["marked_at"]
            })
        
        return {
            "status": "success",
            "employee": {
                "_id": str(employee["_id"]),
                "employee_id": employee["employee_id"],
                "full_name": employee["full_name"],
                "email": employee["email"],
                "department": employee["department"]
            },
            "data": formatted_records,
            "count": len(formatted_records)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)