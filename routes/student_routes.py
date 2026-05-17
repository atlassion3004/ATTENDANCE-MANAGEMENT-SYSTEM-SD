from flask import Blueprint, jsonify
from db import get_db_connection

student_routes = Blueprint('student_routes', __name__)

@student_routes.route('/students', methods=['GET'])
def get_students():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student")
    students = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify(students)