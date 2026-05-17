# routes/attendance_routes.py
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt_identity

attendance_routes = Blueprint('attendance_routes', __name__)

@attendance_routes.route('/attendance', methods=['POST'])
@jwt_required()
def mark_attendance():
    try:
        current_student_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        required = ['attendanceid', 'status']
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        attendance_id = data['attendanceid']
        status = data['status']   # client sends 'Present', but we may override

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ----- NEW: Check lateness -----
        # 1. Get the ClassID for this attendance session
        cursor.execute("SELECT ClassID FROM attendance WHERE AttendanceID = %s", (attendance_id,))
        att_row = cursor.fetchone()
        if not att_row:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid attendance session"}), 404

        class_id = att_row['ClassID']
        # 2. Get the scheduled start time for this class
        cursor.execute("SELECT StartTime FROM class_schedule WHERE ClassID = %s", (class_id,))
        sched = cursor.fetchone()
        if sched and sched['StartTime'] is not None:
            scheduled_start = sched['StartTime']  # this is a timedelta object
            # Convert timedelta to a time-of-day for comparison
            now = datetime.now()
            current_time = now.time()
            # timedelta to time: (datetime.min + scheduled_start).time()
            start_time = (datetime.min + scheduled_start).time()
            # Add 15 minutes to the start time
            late_threshold = (datetime.combine(now.date(), start_time) + timedelta(minutes=15)).time()
            if current_time >= late_threshold:
                status = 'Late'   # override whatever the client sent
        # ----- End lateness check -----
        
        # ---- ADD THE TWO LINES HERE ---- for RECTIFYING SCANNER ERROR
        time_in = datetime.now().strftime('%H:%M:%S')
        time_out = data.get('timeout')

        # The rest of the function (auto-create parent session if needed, upsert)
        # ... same as before, using the (possibly modified) 'status'

        # ---- Auto-create parent session if it doesn't exist ----
        cursor.execute("SELECT AttendanceID FROM attendance WHERE AttendanceID = %s", (attendance_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (AttendanceID) VALUES (%s)", (attendance_id,))
        # ---- Upsert into attendance_details ----
        cursor.execute(
            "SELECT * FROM attendance_details WHERE attendanceid = %s AND studentid = %s",
            (attendance_id, current_student_id)
        )
        existing = cursor.fetchone()

        if existing:
            # Determine what to set for timeout
            new_timeout = data.get('timeout')  # may be None
            # If the client didn't send a timeout AND the existing record has no timeout yet,
            # assume this is a time‑out scan → use current server time.
            if new_timeout is None and existing.get('timeout') is None:
                new_timeout = datetime.now().strftime('%H:%M:%S')

            update_query = """
                UPDATE attendance_details
                SET timeout = %s, status = %s
                WHERE attendanceid = %s AND studentid = %s
            """
            cursor.execute(update_query, (new_timeout, status, attendance_id, current_student_id))
            conn.commit()
            msg = "Attendance updated successfully" if new_timeout is None else "Time‑out recorded successfully"
            status_code = 200
        else:
            insert_query = """
                INSERT INTO attendance_details
                (attendanceid, studentid, timein, timeout, status)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (attendance_id, current_student_id, time_in, time_out, status))
            conn.commit()
            msg = "Attendance recorded successfully"
            status_code = 201

        cursor.close()
        conn.close()
        return jsonify({"message": msg}), status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@attendance_routes.route('/attendance', methods=['GET'])
def get_attendance():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        student_id = request.args.get('studentid')
        date = request.args.get('date')

        # CAST the TIME columns to CHAR so they become strings
        query = """
            SELECT 
                attendanceid,
                studentid,
                CAST(timein AS CHAR) AS timein,
                CAST(timeout AS CHAR) AS timeout,
                status
            FROM attendance_details 
            WHERE 1=1
        """
        params = []

        if student_id:
            query += " AND studentid = %s"
            params.append(student_id)
        if date:
            query += " AND DATE(timein) = %s"
            params.append(date)

        cursor.execute(query, tuple(params))
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500