import sys
import traceback

try:
    import face_recognition
    
    print("Face recognition module imported successfully!")
    print("Available face detection models:", face_recognition.api.face_detector_model_location())
    print("Available face recognition models:", face_recognition.api.face_recognition_model_location())
    print("Python version:", sys.version)
    print("Face recognition version:", face_recognition.__version__)
    
    print("Test complete.")

except Exception as e:
    error_message = f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
    print(error_message)