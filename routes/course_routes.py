from flask import Blueprint, jsonify
from db import get_db_connection

course_routes = Blueprint('course_routes', __name__)

@course_routes.route('/courses', methods=['GET'])
def get_courses():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM course")
    courses = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(courses)