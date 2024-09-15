import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
import face_recognition
import cv2
import numpy as np
import asyncio
import logging

# Set up logging
log_file_path = os.path.join('logs', 'attendance_system_backend.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

# Initialize FastAPI app
app = FastAPI()

# MongoDB configuration
MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DB_NAME = "attendance_system"
MONGO_DATA_DIR = os.path.join(os.getcwd(), "data")
MONGO_LOG_DIR = os.path.join(os.getcwd(), "logs")

# MongoDB connection string with updated paths
MONGO_URL = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB_NAME}?directConnection=true"

# MongoDB client with updated configuration
client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]

# Security
SECRET_KEY = "your-secret-key"  # Change this to a secure random key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Models
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class Student(BaseModel):
    id: str
    name: str
    class_name: str
    facial_data: str  # Base64 encoded facial data

class AttendanceRecord(BaseModel):
    date: datetime
    student_id: str
    status: str
    timestamp: datetime
    method: str

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_user(username: str):
    user_dict = await db.users.find_one({"username": username})
    if user_dict:
        return UserInDB(**user_dict)

async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Test MongoDB connection
async def test_connection():
    try:
        await client.server_info()
        logging.info("Successfully connected to MongoDB")
        return True
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        return False

# Routes
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register_student")
async def register_student(student: Student, current_user: User = Depends(get_current_user)):
    # Check if the current user is an administrator
    if current_user.username != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to register students")
    
    # Store the student data in the database
    result = await db.students.insert_one(student.dict())
    if result.inserted_id:
        return {"message": "Student registered successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to register student")

@app.post("/mark_attendance")
async def mark_attendance(image: bytes):
    # Load the image
    nparr = np.frombuffer(image, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Find face locations and encodings
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    if len(face_encodings) == 0:
        raise HTTPException(status_code=400, detail="No face detected in the image")

    # Compare with stored facial data
    students = await db.students.find().to_list(length=None)
    for student in students:
        stored_encoding = np.frombuffer(student['facial_data'], dtype=np.float64)
        matches = face_recognition.compare_faces([stored_encoding], face_encodings[0])
        if matches[0]:
            # Mark attendance
            attendance_record = AttendanceRecord(
                date=datetime.now().date(),
                student_id=student['id'],
                status="present",
                timestamp=datetime.now(),
                method="facial_recognition"
            )
            await db.attendance.insert_one(attendance_record.dict())
            return {"message": f"Attendance marked for student {student['name']}"}

    raise HTTPException(status_code=404, detail="Student not recognized")

@app.post("/manual_attendance")
async def manual_attendance(records: List[AttendanceRecord], current_user: User = Depends(get_current_user)):
    # Check if the current user is a teacher
    if current_user.username not in ["teacher1", "teacher2"]:  # Add logic to check if user is a teacher
        raise HTTPException(status_code=403, detail="Not authorized to mark manual attendance")
    
    # Insert attendance records
    result = await db.attendance.insert_many([record.dict() for record in records])
    if result.inserted_ids:
        return {"message": f"Attendance marked for {len(result.inserted_ids)} students"}
    else:
        raise HTTPException(status_code=500, detail="Failed to mark attendance")

@app.get("/attendance_report")
async def get_attendance_report(start_date: str, end_date: str, class_name: Optional[str] = None, student_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    # Check if the current user is authorized to view reports
    if current_user.username not in ["admin", "teacher1", "teacher2"]:  # Add logic to check if user is authorized
        raise HTTPException(status_code=403, detail="Not authorized to view attendance reports")
    
    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Build query
    query = {"date": {"$gte": start, "$lte": end}}
    if class_name:
        query["class_name"] = class_name
    if student_id:
        query["student_id"] = student_id

    # Fetch attendance records
    records = await db.attendance.find(query).to_list(length=None)

    # Process records and generate report
    report = {
        "total_records": len(records),
        "present": sum(1 for record in records if record["status"] == "present"),
        "absent": sum(1 for record in records if record["status"] == "absent"),
        "late": sum(1 for record in records if record["status"] == "late"),
    }

    return report

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting the attendance system backend...")
    loop = asyncio.get_event_loop()
    if loop.run_until_complete(test_connection()):
        logging.info("MongoDB connection successful. Starting the FastAPI server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        logging.error("Failed to connect to MongoDB. Please check if the MongoDB server is running.")