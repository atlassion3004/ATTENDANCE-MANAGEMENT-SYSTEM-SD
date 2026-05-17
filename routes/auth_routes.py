# routes/auth_routes.py
from flask import Blueprint, request, jsonify
from db import get_db_connection
import bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import timedelta
import os

auth_routes = Blueprint('auth_routes', __name__)

# ------------------- Login (checks both tables) -------------------
@auth_routes.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'userid' not in data or 'password' not in data:
        return jsonify({"error": "Missing userid or password"}), 400

    user_id = data['userid']
    password = data['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check student table first
    cursor.execute("SELECT StudentID, password_hash, 'student' AS role FROM student WHERE StudentID = %s", (user_id,))
    user = cursor.fetchone()

    # If not found, check instructor table
    if not user:
        cursor.execute("SELECT InstructorID, password_hash, 'instructor' AS role FROM instructor WHERE InstructorID = %s", (user_id,))
        user = cursor.fetchone()
        
    # If not found in student or instructor, check admin table(NEW ADDITION FOR ADMIN LOGIN)
    if not user:
        cursor.execute("SELECT AdminID, password_hash, 'admin' AS role FROM admin WHERE AdminID = %s", (user_id,))
        user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user or not user['password_hash']:
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create JWT with role in additional claims
    additional_claims = {"role": user['role']}
    access_token = create_access_token(
        identity=user_id,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=2)
    )
    return jsonify({"access_token": access_token, "role": user['role']}), 200


# ------------------- Student Registration -------------------
@auth_routes.route('/register/student', methods=['POST'])
def register_student():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    required = ['studentid', 'surname', 'firstname', 'password']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    student_id = data['studentid']
    surname = data['surname']
    firstname = data['firstname']
    password = data['password']
    middlename = data.get('middlename')
    yearlevel = data.get('yearlevel')
    courseid = data.get('courseid')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check duplicate
    cursor.execute("SELECT StudentID FROM student WHERE StudentID = %s", (student_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Student ID already exists"}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    insert_query = """
        INSERT INTO student (StudentID, Surname, FirstName, MiddleName, YearLevel, CourseID, password_hash, role)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'student')
    """
    try:
        cursor.execute(insert_query, (
            student_id, surname, firstname, middlename, yearlevel, courseid, hashed
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Student registered successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------- Instructor Registration -------------------
@auth_routes.route('/register/instructor', methods=['POST'])
def register_instructor():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    required = ['instructorid', 'surname', 'firstname', 'password']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    instructor_id = data['instructorid']
    surname = data['surname']
    firstname = data['firstname']
    password = data['password']
    middlename = data.get('middlename')
    department = data.get('department')

    # Secret key check
    secret_key = os.getenv("INSTRUCTOR_REGISTRATION_KEY")
    if not secret_key or data.get('registration_key') != secret_key:
        return jsonify({"error": "Invalid or missing instructor registration key"}), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check duplicate
    cursor.execute("SELECT InstructorID FROM instructor WHERE InstructorID = %s", (instructor_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Instructor ID already exists"}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    insert_query = """
        INSERT INTO instructor (InstructorID, InstructorSurname, InstructorFirstName, InstructorMiddleName, InstructorDepartment, password_hash)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(insert_query, (
            instructor_id, surname, firstname, middlename, department, hashed
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Instructor registered successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# routes/auth_routes.py

@auth_routes.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    claims = get_jwt()
    role = claims.get('role')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role == 'student':
        cursor.execute("SELECT Surname, FirstName FROM student WHERE StudentID = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            name = f"{user['Surname']}, {user['FirstName']}"
        else:
            name = "Student"
    elif role == 'instructor':
        cursor.execute("SELECT InstructorSurname, InstructorFirstName FROM instructor WHERE InstructorID = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            name = f"{user['InstructorSurname']}, {user['InstructorFirstName']}"
        else:
            name = "Instructor"
    elif role == 'admin':
        name = "ADMIN"
    else:
        name = "User"

    cursor.close()
    conn.close()
    return jsonify({"name": name, "role": role})