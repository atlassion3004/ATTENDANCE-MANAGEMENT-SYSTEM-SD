from functools import wraps
from flask import Blueprint, request, jsonify
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt, verify_jwt_in_request
import bcrypt

admin_routes = Blueprint('admin_routes', __name__)

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') != 'admin':
                return jsonify({"error": "Admin access required"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# ----- Instructor Management -----
@admin_routes.route('/api/admin/instructors', methods=['GET'])
@jwt_required()
@admin_required()
def get_instructors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT InstructorID, InstructorSurname, InstructorFirstName, InstructorMiddleName, InstructorDepartment FROM instructor ORDER BY InstructorSurname, InstructorFirstName")
    instructors = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(instructors)

@admin_routes.route('/api/admin/instructors', methods=['POST'])
@jwt_required()
@admin_required()
def create_instructor():
    data = request.get_json()
    required = ['instructorid', 'surname', 'firstname', 'password']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing {field}"}), 400

    instructor_id = data['instructorid']
    surname = data['surname']
    firstname = data['firstname']
    password = data['password']
    middlename = data.get('middlename')
    department = data.get('department')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT InstructorID FROM instructor WHERE InstructorID = %s", (instructor_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Instructor ID already exists"}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        cursor.execute("""
            INSERT INTO instructor (InstructorID, InstructorSurname, InstructorFirstName, InstructorMiddleName, InstructorDepartment, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (instructor_id, surname, firstname, middlename, department, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Instructor created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_routes.route('/api/admin/instructors/<instructor_id>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_instructor(instructor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT InstructorID FROM instructor WHERE InstructorID = %s", (instructor_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Instructor not found"}), 404

    # Note: related schedules and attendance may have FK constraints; consider cascading or warnings
    cursor.execute("DELETE FROM instructor WHERE InstructorID = %s", (instructor_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Instructor deleted"}), 200

# ---------- Subject Management ----------
@admin_routes.route('/api/admin/subjects', methods=['GET'])
@jwt_required()
@admin_required()
def get_subjects():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT SubjectCode, SubjectTitle FROM subject ORDER BY SubjectCode")
    subjects = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(subjects)

@admin_routes.route('/api/admin/subjects', methods=['POST'])
@jwt_required()
@admin_required()
def create_subject():
    data = request.get_json()
    if not data or 'subjectcode' not in data or 'subjecttitle' not in data:
        return jsonify({"error": "subjectcode and subjecttitle required"}), 400

    subject_code = data['subjectcode'].strip()
    subject_title = data['subjecttitle'].strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SubjectCode FROM subject WHERE SubjectCode = %s", (subject_code,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Subject code already exists"}), 409

    try:
        cursor.execute("INSERT INTO subject (SubjectCode, SubjectTitle) VALUES (%s, %s)",
                       (subject_code, subject_title))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Subject created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_routes.route('/api/admin/subjects/<subject_code>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_subject(subject_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Could check FK references first, but for now just delete
    cursor.execute("DELETE FROM subject WHERE SubjectCode = %s", (subject_code,))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    if affected:
        return jsonify({"message": "Subject deleted"}), 200
    else:
        return jsonify({"error": "Subject not found"}), 404

# ---------- Course Management ----------
@admin_routes.route('/api/admin/courses', methods=['GET'])
@jwt_required()
@admin_required()
def get_courses():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT CourseID, CourseDescription FROM course ORDER BY CourseID")
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(courses)

@admin_routes.route('/api/admin/courses', methods=['POST'])
@jwt_required()
@admin_required()
def create_course():
    data = request.get_json()
    if not data or 'courseid' not in data or 'coursedescription' not in data:
        return jsonify({"error": "courseid and coursedescription required"}), 400

    course_id = data['courseid'].strip()
    course_desc = data['coursedescription'].strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CourseID FROM course WHERE CourseID = %s", (course_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Course ID already exists"}), 409

    try:
        cursor.execute("INSERT INTO course (CourseID, CourseDescription) VALUES (%s, %s)",
                       (course_id, course_desc))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Course created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_routes.route('/api/admin/courses/<course_id>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM course WHERE CourseID = %s", (course_id,))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    if affected:
        return jsonify({"message": "Course deleted"}), 200
    else:
        return jsonify({"error": "Course not found"}), 404