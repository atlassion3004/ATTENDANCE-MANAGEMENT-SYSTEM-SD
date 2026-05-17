# routes/instructor_routes.py
import bcrypt
from functools import wraps
from flask import Blueprint, request, jsonify
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from datetime import datetime, timedelta

instructor_routes = Blueprint('instructor_routes', __name__)

# ---------- Decorator ----------
def instructor_or_admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') not in ['instructor', 'admin']:
                return jsonify({"error": "Instructor or admin access required"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# ---------- Get Instructor's Classes ----------
@instructor_routes.route('/api/instructor/classes', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_instructor_classes():
    claims = get_jwt()
    role = claims.get('role')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role == 'admin':
        cursor.execute("""
            SELECT cs.ClassID, cs.SubjectCode, s.SubjectTitle
            FROM class_schedule cs
            JOIN subject s ON cs.SubjectCode = s.SubjectCode
            ORDER BY cs.ClassID
        """)
    else:
        instructor_id = get_jwt_identity()
        cursor.execute("""
            SELECT cs.ClassID, cs.SubjectCode, s.SubjectTitle
            FROM class_schedule cs
            JOIN subject s ON cs.SubjectCode = s.SubjectCode
            WHERE cs.InstructorID = %s
            ORDER BY cs.DayOfWeek, cs.StartTime
        """, (instructor_id,))

    classes = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(classes)

# ---------- Get Attendance Records for a Class (with optional date) ----------
@instructor_routes.route('/api/attendance-records', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_attendance_records():
    class_id = request.args.get('classid')
    date = request.args.get('date')  # expected YYYY-MM-DD

    if not class_id:
        return jsonify({"error": "classid is required"}), 400

    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ----- ADMIN BYPASS HERE -----
    role = get_jwt().get('role')
    if role != 'admin':
        cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
        row = cursor.fetchone()
        if not row or row['InstructorID'] != instructor_id:
            cursor.close()
            conn.close()
            return jsonify({"error": "Unauthorized class access"}), 403
    # ----- END OF INSERT -----

    cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
    row = cursor.fetchone()
    if not row or row['InstructorID'] != instructor_id:
        cursor.close()
        conn.close()
        return jsonify({"error": "Unauthorized class access"}), 403

    query = """
        SELECT ad.attendanceid, ad.studentid, ad.timein, ad.timeout, ad.status,
               s.Surname, s.FirstName, s.MiddleName,
               a.Date
        FROM attendance_details ad
        JOIN student s ON ad.studentid = s.StudentID
        JOIN attendance a ON ad.attendanceid = a.AttendanceID
        WHERE a.ClassID = %s
    """
    params = [class_id]

    if date:
        query += " AND a.Date = %s"
        params.append(date)

    query += " ORDER BY ad.timein ASC"

    cursor.execute(query, tuple(params))
    records = cursor.fetchall()

    from datetime import timedelta   # ensure import at top

    for rec in records:
        # Convert time columns
        if isinstance(rec.get('timein'), timedelta):
            rec['timein'] = str(rec['timein'])
        if isinstance(rec.get('timeout'), timedelta):
            rec['timeout'] = str(rec['timeout'])
        # Convert date column to string
        if rec.get('Date'):
            rec['Date'] = str(rec['Date'])   # e.g., "2026-05-14"
        # Build full name
        name_parts = [rec.get('Surname', ''), rec.get('FirstName', '')]
        if rec.get('MiddleName'):
            name_parts.append(rec['MiddleName'])
        rec['student_name'] = ', '.join([p for p in name_parts if p])
        # Remove raw name fields (optional)
        rec.pop('Surname', None)
        rec.pop('FirstName', None)
        rec.pop('MiddleName', None)

    cursor.close()
    conn.close()
    return jsonify(records)

# ---------- Update an Attendance Record ----------
@instructor_routes.route('/api/attendance-records', methods=['PUT'])
@jwt_required()
@instructor_or_admin_required()
def update_attendance_record():
    data = request.get_json()
    required = ['attendanceid', 'studentid']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing {field}"}), 400

    attendance_id = data['attendanceid']
    student_id = data['studentid']

    # Verify instructor owns the class of this attendance record
    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.ClassID FROM attendance a
        JOIN class_schedule cs ON a.ClassID = cs.ClassID
        WHERE a.AttendanceID = %s AND cs.InstructorID = %s
    """, (attendance_id, instructor_id))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Record not found or access denied"}), 404

    # Allowed fields to update: status, timein, timeout
    updates = []
    values = []
    for field in ['status', 'timein', 'timeout']:
        if field in data:
            updates.append(f"{field} = %s")
            values.append(data[field])

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    values.extend([attendance_id, student_id])
    query = "UPDATE attendance_details SET " + ", ".join(updates) + " WHERE attendanceid = %s AND studentid = %s"
    cursor.execute(query, tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Record updated"}), 200

# ---------- Delete an Attendance Record ----------
@instructor_routes.route('/api/attendance-records', methods=['DELETE'])
@jwt_required()
@instructor_or_admin_required()
def delete_attendance_record():
    data = request.get_json()
    if not data or 'attendanceid' not in data or 'studentid' not in data:
        return jsonify({"error": "attendanceid and studentid required"}), 400

    attendance_id = data['attendanceid']
    student_id = data['studentid']

    # Verify instructor owns the class
    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.ClassID FROM attendance a
        JOIN class_schedule cs ON a.ClassID = cs.ClassID
        WHERE a.AttendanceID = %s AND cs.InstructorID = %s
    """, (attendance_id, instructor_id))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Record not found or access denied"}), 404

    cursor.execute("DELETE FROM attendance_details WHERE attendanceid = %s AND studentid = %s",
                   (attendance_id, student_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Record deleted"}), 200

# ---------- Student Management (Instructor) ----------

# Get all students (with optional search)
@instructor_routes.route('/api/students', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_all_students():
    search = request.args.get('search', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search:
        cursor.execute("""
            SELECT StudentID, Surname, FirstName, MiddleName, YearLevel, CourseID
            FROM student
            WHERE StudentID LIKE %s OR CONCAT(FirstName, ' ', Surname) LIKE %s
            ORDER BY Surname, FirstName
        """, (f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("""
            SELECT StudentID, Surname, FirstName, MiddleName, YearLevel, CourseID
            FROM student
            ORDER BY Surname, FirstName
        """)
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(students)

# Create a new student (instructor-only)
@instructor_routes.route('/api/students', methods=['POST'])
@jwt_required()
@instructor_or_admin_required()
def create_student():
    data = request.get_json()
    required = ['studentid', 'surname', 'firstname', 'password']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing {field}"}), 400

    student_id = data['studentid']
    surname = data['surname']
    firstname = data['firstname']
    password = data['password']
    middlename = data.get('middlename')
    yearlevel = data.get('yearlevel')
    courseid = data.get('courseid')
    
    #convert empty strings to None for optional fields
    if courseid == '':
        courseid = None
    if yearlevel == '':
        yearlevel = None
    if middlename == '':
        middlename = None

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check duplicate
    cursor.execute("SELECT StudentID FROM student WHERE StudentID = %s", (student_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Student ID already exists"}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        cursor.execute("""
            INSERT INTO student (StudentID, Surname, FirstName, MiddleName, YearLevel, CourseID, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'student')
        """, (student_id, surname, firstname, middlename, yearlevel, courseid, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Student created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get enrollment for a specific class (instructor's own class)
@instructor_routes.route('/api/enrollments', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_enrollments():
    class_id = request.args.get('classid')
    if not class_id:
        return jsonify({"error": "classid required"}), 400

    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify the class belongs to the instructor (or allow admin)
    role = get_jwt().get('role')
    if role != 'admin':
        cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
        row = cursor.fetchone()
        if not row or row['InstructorID'] != instructor_id:
            cursor.close()
            conn.close()
            return jsonify({"error": "Unauthorized class access"}), 403


    cursor.execute("""
        SELECT e.StudentID, s.Surname, s.FirstName, s.MiddleName
        FROM enrollment e
        JOIN student s ON e.StudentID = s.StudentID
        WHERE e.ClassID = %s
        ORDER BY s.Surname, s.FirstName
    """, (class_id,))
    enrollments = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(enrollments)

# Enroll a student into a class
@instructor_routes.route('/api/enrollments', methods=['POST'])
@jwt_required()
@instructor_or_admin_required()
def enroll_student():
    data = request.get_json()
    if not data or 'studentid' not in data or 'classid' not in data:
        return jsonify({"error": "studentid and classid required"}), 400

    student_id = data['studentid']
    class_id = data['classid']
    instructor_id = get_jwt_identity()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify class ownership(UPDATED TO ALLOW ADMIN BYPASS)
    role = get_jwt().get('role')
    if role != 'admin':
        # existing ownership check
        cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
        row = cursor.fetchone()
        if not row or row[0] != instructor_id:
            cursor.close()
            conn.close()
            return jsonify({"error": "Unauthorized class access"}), 403

    # Check student exists
    cursor.execute("SELECT StudentID FROM student WHERE StudentID = %s", (student_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Student does not exist"}), 404

    # Insert (ignore if already enrolled)
    try:
        cursor.execute("INSERT INTO enrollment (StudentID, ClassID) VALUES (%s, %s)", (student_id, class_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Student enrolled successfully"}), 201
    except Exception as e:
        # Duplicate entry will raise IntegrityError
        return jsonify({"error": str(e)}), 409

# Unenroll (delete enrollment)
@instructor_routes.route('/api/enrollments', methods=['DELETE'])
@jwt_required()
@instructor_or_admin_required()
def unenroll_student():
    data = request.get_json()
    if not data or 'studentid' not in data or 'classid' not in data:
        return jsonify({"error": "studentid and classid required"}), 400

    student_id = data['studentid']
    class_id = data['classid']
    instructor_id = get_jwt_identity()

    conn = get_db_connection()
    cursor = conn.cursor()
    
    #ADMIN BYPASS
    role = get_jwt().get('role')
    if role != 'admin':
        cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
        row = cursor.fetchone()
        if not row or row[0] != instructor_id:
            cursor.close()
            conn.close()
            return jsonify({"error": "Unauthorized class access"}), 403
    #END BYPASS    
    
    cursor.execute("DELETE FROM enrollment WHERE StudentID = %s AND ClassID = %s", (student_id, class_id))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    if affected:
        return jsonify({"message": "Student unenrolled"}), 200
    else:
        return jsonify({"error": "Enrollment not found"}), 404
    
# Delete a student (instructor only)
@instructor_routes.route('/api/students/<student_id>', methods=['DELETE'])
@jwt_required()
@instructor_or_admin_required()
def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if student exists
    cursor.execute("SELECT StudentID FROM student WHERE StudentID = %s", (student_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    # Delete – enrollment records will cascade automatically if FK set
    cursor.execute("DELETE FROM student WHERE StudentID = %s", (student_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Student deleted successfully"}), 200

# ---------- Absence Report ----------
@instructor_routes.route('/api/absence-report', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def absence_report():
    class_id = request.args.get('classid')
    date = request.args.get('date')  # YYYY-MM-DD

    if not class_id or not date:
        return jsonify({"error": "classid and date are required"}), 400

    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verify the class belongs to the instructor
    cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
    row = cursor.fetchone()
    if not row or row['InstructorID'] != instructor_id:
        cursor.close()
        conn.close()
        return jsonify({"error": "Unauthorized class access"}), 403

    # 1. Get all enrolled students
    cursor.execute("""
        SELECT e.StudentID, s.Surname, s.FirstName, s.MiddleName
        FROM enrollment e
        JOIN student s ON e.StudentID = s.StudentID
        WHERE e.ClassID = %s
    """, (class_id,))
    enrolled = cursor.fetchall()

    # 2. Get students who have attendance on that date for this class
    cursor.execute("""
        SELECT ad.studentid
        FROM attendance_details ad
        JOIN attendance a ON ad.attendanceid = a.AttendanceID
        WHERE a.ClassID = %s AND a.Date = %s
    """, (class_id, date))
    present_records = cursor.fetchall()
    present_ids = {rec['studentid'] for rec in present_records}

    # 3. Separate absent and present
    absent = []
    present_list = []
    for stu in enrolled:
        full_name = ', '.join([p for p in [stu['Surname'], stu['FirstName'], stu.get('MiddleName')] if p])
        entry = {
            'studentid': stu['StudentID'],
            'student_name': full_name
        }
        if stu['StudentID'] in present_ids:
            present_list.append(entry)
        else:
            absent.append(entry)

    cursor.close()
    conn.close()

    return jsonify({
        'date': date,
        'classid': class_id,
        'absent': absent,
        'present': present_list
    })
    
    # ---------- Class Metrics (for dashboard) ----------
@instructor_routes.route('/api/instructor/class-metrics', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_class_metrics():
    class_id = request.args.get('classid')
    if not class_id:
        return jsonify({"error": "classid required"}), 400

    # Admin can see any class; instructor only own
    claims = get_jwt()
    role = claims.get('role')
    instructor_id = get_jwt_identity()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role != 'admin':
        cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
        row = cursor.fetchone()
        if not row or row['InstructorID'] != instructor_id:
            cursor.close()
            conn.close()
            return jsonify({"error": "Unauthorized class access"}), 403

    # Total students enrolled in the class
    cursor.execute("SELECT COUNT(*) AS total FROM enrollment WHERE ClassID = %s", (class_id,))
    total_students = cursor.fetchone()['total']

    # Attendance stats from attendance_details + attendance
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT a.AttendanceID) AS total_sessions,
            SUM(CASE WHEN ad.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN ad.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            SUM(CASE WHEN ad.status = 'Late' THEN 1 ELSE 0 END) AS late_count
        FROM attendance_details ad
        JOIN attendance a ON ad.attendanceid = a.AttendanceID
        WHERE a.ClassID = %s
    """, (class_id,))
    stats = cursor.fetchone()

    total_sessions = stats['total_sessions'] or 0
    present = stats['present_count'] or 0
    absent = stats['absent_count'] or 0
    late = stats['late_count'] or 0

    # Attendance rate: (present + late) / total sessions * total_students? Usually rate per session.
    # We'll compute overall rate: (present + late) / (total_sessions * total_students) if >0 else 0
    rate = 0.0
    if total_sessions > 0 and total_students > 0:
        total_expected = total_sessions * total_students
        total_recorded = present + late
        rate = (total_recorded / total_expected) * 100

    cursor.close()
    conn.close()

    return jsonify({
        'total_students': total_students,
        'attendance_rate': round(rate, 1),
        'absences': absent,
        'lates': late
    })