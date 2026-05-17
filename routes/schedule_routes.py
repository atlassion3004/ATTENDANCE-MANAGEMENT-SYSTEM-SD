from flask import Blueprint, request, jsonify
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from datetime import datetime, timedelta
from functools import wraps
import zoneinfo

schedule_routes = Blueprint('schedule_routes', __name__)

def manila_date_str():
    return datetime.now(zoneinfo.ZoneInfo("Asia/Manila")).strftime('%Y-%m-%d')

# Helper to verify instructor role (UPDATED WITH ADMIN BYPASS)
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

# GET all schedules for the logged-in instructor
@schedule_routes.route('/my-schedules', methods=['GET'])
@jwt_required()
@instructor_or_admin_required()
def get_my_schedules():
    claims = get_jwt()
    role = claims.get('role')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if role == 'admin':
        cursor.execute("""
            SELECT cs.ClassID, cs.SubjectCode, cs.Room, cs.DayOfWeek,
                   CAST(cs.StartTime AS CHAR) AS StartTime,
                   CAST(cs.EndTime AS CHAR) AS EndTime,
                   s.SubjectTitle
            FROM class_schedule cs
            JOIN subject s ON cs.SubjectCode = s.SubjectCode
            ORDER BY cs.ClassID
        """)
    else:
        instructor_id = get_jwt_identity()
        cursor.execute("""
            SELECT cs.ClassID, cs.SubjectCode, cs.Room, cs.DayOfWeek,
                   CAST(cs.StartTime AS CHAR) AS StartTime,
                   CAST(cs.EndTime AS CHAR) AS EndTime,
                   s.SubjectTitle
            FROM class_schedule cs
            JOIN subject s ON cs.SubjectCode = s.SubjectCode
            WHERE cs.InstructorID = %s
        """, (instructor_id,))

    schedules = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(schedules)

# Create a new class schedule (instructor only, for themselves)
@schedule_routes.route('/schedules', methods=['POST'])
@jwt_required()
@instructor_or_admin_required()
def create_schedule():
    data = request.get_json()
    required = ['classid', 'subjectcode', 'room', 'dayofweek', 'starttime', 'endtime']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    class_id = data['classid']
    subject_code = data['subjectcode']
    room = data['room']
    day_of_week = data['dayofweek']
    start_time = data['starttime']
    end_time = data['endtime']

    # Determine instructor ID
    role = get_jwt().get('role')
    if role == 'admin':
        # Admin may provide an instructorid, otherwise set NULL
        instructor_id = data.get('instructorid', None)
        if instructor_id == '':
            instructor_id = None
    else:
        # Instructors always use their own ID
        instructor_id = get_jwt_identity()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO class_schedule (ClassID, SubjectCode, InstructorID, Room, DayOfWeek, StartTime, EndTime)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (class_id, subject_code, instructor_id, room, day_of_week, start_time, end_time))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Schedule created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Update an existing schedule (only if it belongs to the instructor)
@schedule_routes.route('/schedules/<class_id>', methods=['PUT'])
@jwt_required()
@instructor_or_admin_required()
def update_schedule(class_id):
    data = request.get_json()
    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verify ownership
    cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
    row = cursor.fetchone()
    if not row or row[0] != instructor_id:
        cursor.close()
        conn.close()
        return jsonify({"error": "Schedule not found or access denied"}), 404

    # Build update dynamically
    updates = []
    values = []
    for field in ['subjectcode', 'room', 'dayofweek', 'starttime', 'endtime']:
        if field in data:
            updates.append(f"{field} = %s")
            values.append(data[field])
    if not updates:
        return jsonify({"error": "No fields to update"}), 400
    values.append(class_id)
    query = "UPDATE class_schedule SET " + ", ".join(updates) + " WHERE ClassID = %s"
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Schedule updated"}), 200

# Delete a schedule
@schedule_routes.route('/schedules/<class_id>', methods=['DELETE'])
@jwt_required()
@instructor_or_admin_required()
def delete_schedule(class_id):
    instructor_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT InstructorID FROM class_schedule WHERE ClassID = %s", (class_id,))
    row = cursor.fetchone()
    if not row or row[0] != instructor_id:
        cursor.close()
        conn.close()
        return jsonify({"error": "Schedule not found or access denied"}), 404
    cursor.execute("DELETE FROM class_schedule WHERE ClassID = %s", (class_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Schedule deleted"}), 200

# routes/schedule_routes.py  (add this new route)
@schedule_routes.route('/generate-session', methods=['POST'])
@jwt_required()
@instructor_or_admin_required()
def generate_session():
    data = request.get_json()
    if not data or 'classid' not in data:
        return jsonify({"error": "Missing classid"}), 400

    class_id = data['classid']
    instructor_id = get_jwt_identity()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Ownership check for non-admin
    role = get_jwt().get('role')
    if role != 'admin':
        cursor.execute(
            "SELECT * FROM class_schedule WHERE ClassID = %s AND InstructorID = %s",
            (class_id, instructor_id)
        )
        schedule = cursor.fetchone()
        if not schedule:
            cursor.close()
            conn.close()
            return jsonify({"error": "Schedule not found or access denied"}), 404

    # Check if an attendance session already exists for this class today
    cursor.execute(
        "SELECT AttendanceID FROM attendance WHERE ClassID = %s AND Date = CURDATE()",
        (class_id,)
    )
    existing = cursor.fetchone()

    if existing:
        attendance_id = existing['AttendanceID']
        cursor.close()
        conn.close()
        return jsonify({
            "attendanceid": attendance_id,
            "classid": class_id,
            "message": "Existing session loaded"
        }), 200
    else:
        # Create new session
        import uuid
        attendance_id = "ATT-" + uuid.uuid4().hex[:8].upper()
        cursor.execute(
            "INSERT INTO attendance (AttendanceID, ClassID, Date) VALUES (%s, %s, %s)",
            (attendance_id, class_id, manila_date_str())
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({
            "attendanceid": attendance_id,
            "classid": class_id,
            "message": "New session created"
        }), 201