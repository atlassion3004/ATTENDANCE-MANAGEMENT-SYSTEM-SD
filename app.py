from flask import Flask
from flask_jwt_extended import JWTManager
from routes.student_routes import student_routes
from routes.attendance_routes import attendance_routes
from routes.course_routes import course_routes
from routes.subject_routes import subject_routes
from routes.instructor_routes import instructor_routes
from routes.class_routes import class_routes
from routes.auth_routes import auth_routes
from routes.schedule_routes import schedule_routes
from flask import redirect, url_for
from routes.admin_routes import admin_routes
from routes.student_dashboard_routes import student_dashboard_routes

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "CHANGE-IN-PRODUCTION"
jwt = JWTManager(app)

app.register_blueprint(student_routes)
app.register_blueprint(attendance_routes)
app.register_blueprint(course_routes)
app.register_blueprint(subject_routes)
app.register_blueprint(instructor_routes)
app.register_blueprint(class_routes)
app.register_blueprint(auth_routes)
app.register_blueprint(schedule_routes)
app.register_blueprint(admin_routes)
app.register_blueprint(student_dashboard_routes)
    
@app.route('/scanner')
def scanner():
    return app.send_static_file('scanner.html')

@app.route('/')
def index():
    # Serve the unified login page
    return app.send_static_file('login.html')

@app.route('/instructor-dashboard')
def instructor_dashboard():
    # The HTML itself will check the token, but we can still serve it.
    return app.send_static_file('instructor.html')

@app.route('/student-dashboard')
def student_dashboard():
    # Placeholder – or redirect to scanner
    return app.send_static_file('student_dashboard.html')