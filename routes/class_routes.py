from flask import Blueprint, jsonify
from db import get_db_connection

class_routes = Blueprint('class_routes', __name__)

@class_routes.route('/classes', methods=['GET'])
def get_classes():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM class_schedule")
    classes = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(classes)