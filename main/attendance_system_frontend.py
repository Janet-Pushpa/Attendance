import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import cv2
from PIL import Image
import io
import json

# Set the backend URL
BACKEND_URL = "http://localhost:8000"

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None

def login():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = requests.post(f"{BACKEND_URL}/token", data={"username": username, "password": password})
        if response.status_code == 200:
            st.session_state.token = response.json()["access_token"]
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

def register_student():
    st.title("Register New Student")
    student_id = st.text_input("Student ID")
    name = st.text_input("Name")
    class_name = st.text_input("Class")
    
    uploaded_file = st.file_uploader("Upload student photo", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        
        if st.button("Register Student"):
            # Convert image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Prepare student data
            student_data = {
                "id": student_id,
                "name": name,
                "class_name": class_name,
                "facial_data": img_byte_arr
            }
            
            # Send request to backend
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = requests.post(f"{BACKEND_URL}/register_student", json=student_data, headers=headers)
            
            if response.status_code == 200:
                st.success("Student registered successfully!")
            else:
                st.error(f"Failed to register student: {response.text}")

def mark_attendance():
    st.title("Mark Attendance")
    st.write("Click the button below to capture an image and mark attendance.")
    if st.button("Capture Image"):
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Convert frame to jpg
                is_success, im_buf_arr = cv2.imencode(".jpg", frame)
                byte_im = im_buf_arr.tobytes()
                
                # Display captured image
                image = Image.open(io.BytesIO(byte_im))
                st.image(image, caption="Captured Image", use_column_width=True)
                
                # Send image to backend for attendance marking
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(f"{BACKEND_URL}/mark_attendance", data=byte_im, headers=headers)
                
                if response.status_code == 200:
                    st.success(response.json()["message"])
                else:
                    st.error(f"Failed to mark attendance: {response.text}")
            else:
                st.error("Failed to capture image")
            cap.release()
        else:
            st.error("Unable to open camera")

def manual_attendance():
    st.title("Manual Attendance")
    date = st.date_input("Date")
    time = st.time_input("Time")
    student_id = st.text_input("Student ID")
    status = st.selectbox("Status", ["present", "absent", "late"])
    
    if st.button("Mark Attendance"):
        attendance_data = {
            "date": datetime.combine(date, time).isoformat(),
            "student_id": student_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "method": "manual"
        }
        
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.post(f"{BACKEND_URL}/manual_attendance", json=[attendance_data], headers=headers)
        
        if response.status_code == 200:
            st.success("Attendance marked successfully!")
        else:
            st.error(f"Failed to mark attendance: {response.text}")

def attendance_report():
    st.title("Attendance Report")
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    class_name = st.text_input("Class Name (optional)")
    student_id = st.text_input("Student ID (optional)")
    
    if st.button("Generate Report"):
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "class_name": class_name if class_name else None,
            "student_id": student_id if student_id else None
        }
        
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{BACKEND_URL}/attendance_report", params=params, headers=headers)
        
        if response.status_code == 200:
            report_data = response.json()
            st.write("Attendance Report:")
            st.json(report_data)
            
            # Create a pie chart
            fig, ax = plt.subplots()
            sizes = [report_data['present'], report_data['absent'], report_data['late']]
            labels = 'Present', 'Absent', 'Late'
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            st.pyplot(fig)
        else:
            st.error(f"Failed to generate report: {response.text}")

def main():
    st.sidebar.title("Navigation")
    if st.session_state.token is None:
        login()
    else:
        page = st.sidebar.radio("Go to", ["Register Student", "Mark Attendance", "Manual Attendance", "Attendance Report"])
        
        if page == "Register Student":
            register_student()
        elif page == "Mark Attendance":
            mark_attendance()
        elif page == "Manual Attendance":
            manual_attendance()
        elif page == "Attendance Report":
            attendance_report()

if __name__ == "__main__":
    main()