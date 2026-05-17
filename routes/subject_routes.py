from flask import Blueprint, jsonify
from db import get_db_connection

subject_routes = Blueprint('subject_routes', __name__)

@subject_routes.route('/subjects', methods=['GET'])
def get_subjects():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM subject")
    subjects = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(subjects)