# routes/student_dashboard_routes.py
from flask import Blueprint, jsonify, request
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt_identity

student_dashboard_routes = Blueprint('student_dashboard_routes', __name__)

# ---------- Enrolled Subjects & Stats ----------
@student_dashboard_routes.route('/api/student/enrolled-subjects', methods=['GET'])
@jwt_required()
def get_enrolled_subjects():
    student_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch enrolled classes with subject, instructor, schedule, and attendance rate
    cursor.execute("""
        SELECT 
            e.ClassID,
            cs.SubjectCode,
            s.SubjectTitle,
            CONCAT(i.InstructorFirstName, ' ', i.InstructorSurname) AS instructor_name,
            cs.DayOfWeek,
            CAST(cs.StartTime AS CHAR) AS StartTime,
            CAST(cs.EndTime AS CHAR) AS EndTime,
            cs.Room
        FROM enrollment e
        JOIN class_schedule cs ON e.ClassID = cs.ClassID
        JOIN subject s ON cs.SubjectCode = s.SubjectCode
        LEFT JOIN instructor i ON cs.InstructorID = i.InstructorID
        WHERE e.StudentID = %s
        ORDER BY cs.DayOfWeek, cs.StartTime
    """, (student_id,))
    subjects = cursor.fetchall()

    # For each subject, compute attendance rate
    for subj in subjects:
        # Count total sessions for this class
        cursor.execute("""
            SELECT COUNT(DISTINCT a.AttendanceID) AS total_sessions
            FROM attendance a
            WHERE a.ClassID = %s
        """, (subj['ClassID'],))
        total_sessions = cursor.fetchone()['total_sessions'] or 0

        # Count sessions attended by this student (Present or Late)
        cursor.execute("""
            SELECT COUNT(DISTINCT a.AttendanceID) AS attended
            FROM attendance a
            JOIN attendance_details ad ON a.AttendanceID = ad.attendanceid
            WHERE a.ClassID = %s AND ad.studentid = %s AND ad.status IN ('Present', 'Late')
        """, (subj['ClassID'], student_id))
        attended = cursor.fetchone()['attended'] or 0

        rate = (attended / total_sessions * 100) if total_sessions > 0 else 0
        subj['attendance_rate'] = round(rate, 1)
        subj['total_sessions'] = total_sessions
        subj['attended'] = attended

        # Build a compact schedule string
        times = ""
        if subj['StartTime'] and subj['EndTime']:
            times = f" {subj['StartTime']}-{subj['EndTime']}"
        subj['schedule'] = f"{subj['DayOfWeek'] or ''}{times}".strip()

    cursor.close()
    conn.close()
    return jsonify(subjects)

@student_dashboard_routes.route('/api/student/enrollment-stats', methods=['GET'])
@jwt_required()
def get_enrollment_stats():
    student_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all enrolled classes with attendance rates
    cursor.execute("""
        SELECT e.ClassID
        FROM enrollment e
        WHERE e.StudentID = %s
    """, (student_id,))
    classes = cursor.fetchall()

    total_courses = len(classes)
    rates = []
    alerts = 0
    good_standing = 0

    for c in classes:
        class_id = c['ClassID']
        # Total sessions
        cursor.execute("SELECT COUNT(DISTINCT AttendanceID) AS total FROM attendance WHERE ClassID = %s", (class_id,))
        total = cursor.fetchone()['total'] or 0
        # Attended sessions
        cursor.execute("""
            SELECT COUNT(DISTINCT a.AttendanceID) AS attended
            FROM attendance a
            JOIN attendance_details ad ON a.AttendanceID = ad.attendanceid
            WHERE a.ClassID = %s AND ad.studentid = %s AND ad.status IN ('Present', 'Late')
        """, (class_id, student_id))
        attended = cursor.fetchone()['attended'] or 0

        rate = (attended / total * 100) if total > 0 else 0
        rates.append(rate)
        if rate >= 75:
            good_standing += 1
        else:
            alerts += 1

    semester_avg = round(sum(rates) / len(rates), 1) if rates else 0

    cursor.close()
    conn.close()
    return jsonify({
        'total_courses': total_courses,
        'in_good_standing': good_standing,
        'attendance_alerts': alerts,
        'semester_avg': semester_avg
    })

# ---------- Student's Attendance Statistics ----------
# Extend existing attendance endpoint to allow filtering by classid
# (modify the existing get_my_attendance function)
@student_dashboard_routes.route('/api/student/attendance', methods=['GET'])
@jwt_required()
def get_my_attendance():
    student_id = get_jwt_identity()
    status_filter = request.args.get('status')
    search = request.args.get('search', '').strip()
    class_id = request.args.get('classid')   # NEW

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            ad.attendanceid,
            a.ClassID,
            CAST(ad.timein AS CHAR) AS timein,
            CAST(ad.timeout AS CHAR) AS timeout,
            ad.status,
            a.Date AS date,
            cs.SubjectCode,
            s.SubjectTitle
        FROM attendance_details ad
        JOIN attendance a ON ad.attendanceid = a.AttendanceID
        JOIN class_schedule cs ON a.ClassID = cs.ClassID
        JOIN subject s ON cs.SubjectCode = s.SubjectCode
        WHERE ad.studentid = %s
    """
    params = [student_id]

    if class_id:
        query += " AND a.ClassID = %s"
        params.append(class_id)

    if status_filter and status_filter != 'All':
        query += " AND ad.status = %s"
        params.append(status_filter)

    if search:
        query += " AND (s.SubjectTitle LIKE %s OR a.ClassID LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%'])

    query += " ORDER BY a.Date DESC, ad.timein DESC"

    cursor.execute(query, tuple(params))
    records = cursor.fetchall()

    for rec in records:
        if rec.get('date'):
            rec['date'] = str(rec['date'])

    cursor.close()
    conn.close()
    return jsonify(records)