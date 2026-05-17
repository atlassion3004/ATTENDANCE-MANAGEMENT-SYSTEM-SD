import os
import bcrypt
import mysql.connector

def create_tables_and_admin():
    # Read credentials from environment
    db_config = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'ssl_disabled': False,
        'connection_timeout': 10       # seconds
    }

    # Quick connection test
    try:
        test_conn = mysql.connector.connect(**db_config)
        test_conn.close()
        print("Connection test successful.")
    except mysql.connector.Error as e:
        print(f"Connection failed: {e}")
        raise

    # Now create tables
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS course (
        CourseID VARCHAR(20) PRIMARY KEY,
        CourseDescription TEXT
    );

    CREATE TABLE IF NOT EXISTS subject (
        SubjectCode VARCHAR(20) PRIMARY KEY,
        SubjectTitle VARCHAR(100)
    );

    CREATE TABLE IF NOT EXISTS student (
        StudentID VARCHAR(20) PRIMARY KEY,
        Surname VARCHAR(50) NOT NULL,
        FirstName VARCHAR(50) NOT NULL,
        MiddleName VARCHAR(50),
        YearLevel VARCHAR(20),
        CourseID VARCHAR(20),
        password_hash VARCHAR(255),
        role ENUM('student','instructor') DEFAULT 'student',
        FOREIGN KEY (CourseID) REFERENCES course(CourseID)
    );

    CREATE TABLE IF NOT EXISTS instructor (
        InstructorID VARCHAR(20) PRIMARY KEY,
        InstructorSurname VARCHAR(50) NOT NULL,
        InstructorFirstName VARCHAR(50) NOT NULL,
        InstructorMiddleName VARCHAR(50),
        InstructorDepartment VARCHAR(100),
        password_hash VARCHAR(255)
    );

    CREATE TABLE IF NOT EXISTS admin (
        AdminID VARCHAR(20) PRIMARY KEY,
        AdminName VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS class_schedule (
        ClassID VARCHAR(20) PRIMARY KEY,
        SubjectCode VARCHAR(20),
        InstructorID VARCHAR(20),
        Room VARCHAR(50),
        DayOfWeek VARCHAR(10),
        StartTime TIME,
        EndTime TIME,
        FOREIGN KEY (SubjectCode) REFERENCES subject(SubjectCode),
        FOREIGN KEY (InstructorID) REFERENCES instructor(InstructorID)
    );

    CREATE TABLE IF NOT EXISTS attendance (
        AttendanceID VARCHAR(30) PRIMARY KEY,
        ClassID VARCHAR(20),
        Date DATE,
        FOREIGN KEY (ClassID) REFERENCES class_schedule(ClassID)
    );

    CREATE TABLE IF NOT EXISTS attendance_details (
        attendanceid VARCHAR(30) NOT NULL,
        studentid VARCHAR(20) NOT NULL,
        timein TIME,
        timeout TIME,
        status VARCHAR(20),
        PRIMARY KEY (attendanceid, studentid),
        FOREIGN KEY (attendanceid) REFERENCES attendance(AttendanceID),
        FOREIGN KEY (studentid) REFERENCES student(StudentID)
    );

    CREATE TABLE IF NOT EXISTS enrollment (
        StudentID VARCHAR(20) NOT NULL,
        ClassID VARCHAR(20) NOT NULL,
        PRIMARY KEY (StudentID, ClassID),
        FOREIGN KEY (StudentID) REFERENCES student(StudentID) ON DELETE CASCADE,
        FOREIGN KEY (ClassID) REFERENCES class_schedule(ClassID) ON DELETE CASCADE
    );
    """

    for statement in CREATE_TABLES.split(';'):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

    # Insert default admin
    cursor.execute("SELECT COUNT(*) FROM admin WHERE AdminID = 'ADMIN-001'")
    if cursor.fetchone()[0] == 0:
        password = 'admin123'
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO admin (AdminID, AdminName, password_hash) VALUES (%s, %s, %s)",
            ('ADMIN-001', 'System Admin', hashed)
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("Database setup complete.")

if __name__ == '__main__':
    create_tables_and_admin()