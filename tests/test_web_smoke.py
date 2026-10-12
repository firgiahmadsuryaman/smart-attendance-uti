import pytest
from app import create_app
from app.extensions import db
from app.models import User, StudyProgram, Semester, Course, ClassOffering, CourseEnrollment


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        program = StudyProgram(name="Informatika", code="IF", faculty="FTIK")
        semester = Semester(name="Ganjil Test", academic_year="2026/2027", term="Ganjil", is_active=True, enrollment_open=True)
        db.session.add_all([program, semester])
        db.session.flush()
        admin = User(full_name="Admin Uji", email="admin@test.local", role="admin", active=True)
        admin.set_password("password-uji-123")
        student = User(full_name="Mahasiswa Uji", email="student@test.local", npm="TEST001", role="student", program_id=program.id, active=True)
        student.set_password("password-uji-123")
        lecturer = User(full_name="Dosen Uji", email="lecturer@test.local", role="lecturer", active=True)
        lecturer.set_password("password-uji-123")
        db.session.add_all([admin, student, lecturer])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email):
    return client.post("/login", data={"email": email, "password": "password-uji-123"}, follow_redirects=True)


def test_auth_pages_load(client):
    assert client.get("/login").status_code == 200
    response = client.get("/register")
    assert response.status_code == 200
    assert b'name="npm"' in response.data
    assert b'name="phone"' not in response.data
    assert b'name="class_code"' not in response.data


def test_admin_can_open_dashboard(client):
    login(client, "admin@test.local")
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Dashboard Admin" in response.data


def test_student_cannot_open_admin(client):
    login(client, "student@test.local")
    response = client.get("/admin/")
    assert response.status_code == 403


def test_student_schedule_pdf_download(client):
    login(client, "student@test.local")
    response = client.get("/student/schedule/download.pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_student_dashboard_loads(client):
    login(client, "student@test.local")
    response = client.get("/student/")
    assert response.status_code == 200
    assert b"Dashboard Mahasiswa" in response.data


def test_student_face_enrollment_page_loads(client):
    login(client, "student@test.local")
    response = client.get("/student/face-enrollment")
    assert response.status_code == 200
    assert b"Pendaftaran Wajah" in response.data


def test_lecturer_dashboard_loads(client):
    login(client, "lecturer@test.local")
    response = client.get("/lecturer/")
    assert response.status_code == 200
    assert b"Dashboard Dosen" in response.data


def test_admin_navigation_pages_load(client):
    login(client, "admin@test.local")
    paths = [
        "/admin/programs", "/admin/semesters", "/admin/courses",
        "/admin/offerings", "/admin/lecturers", "/admin/students",
        "/admin/enrollments", "/admin/face-profiles", "/admin/reports", "/admin/logs",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"Gagal membuka {path}: {response.status_code}"


def test_lecturer_navigation_pages_load(client):
    login(client, "lecturer@test.local")
    for path in ["/lecturer/classes", "/lecturer/teaching/add", "/lecturer/schedule", "/lecturer/statistics"]:
        response = client.get(path)
        assert response.status_code == 200, f"Gagal membuka {path}: {response.status_code}"


def test_admin_enrollments_with_data_loads(app, client):
    """Regression test for explicit joins in the admin enrollment list."""
    with app.app_context():
        program = StudyProgram.query.filter_by(code="IF").one()
        semester = Semester.query.filter_by(name="Ganjil Test").one()
        student = User.query.filter_by(email="student@test.local").one()
        lecturer = User.query.filter_by(email="lecturer@test.local").one()
        course = Course(code="IFTEST101", name="Mata Kuliah Uji", credits=2,
                        program_id=program.id, course_type="W", is_active=True)
        db.session.add(course)
        db.session.flush()
        offering = ClassOffering(course_id=course.id, semester_id=semester.id,
                                 lecturer_id=lecturer.id, class_code="IFTEST-A",
                                 capacity=40, status="OPEN", delivery_mode="OFFLINE")
        db.session.add(offering)
        db.session.flush()
        db.session.add(CourseEnrollment(student_id=student.id, offering_id=offering.id,
                                        status="PENDING"))
        db.session.commit()

    login(client, "admin@test.local")
    response = client.get("/admin/enrollments?status=ALL")
    assert response.status_code == 200
    assert b"Mahasiswa Uji" in response.data
    assert b"Mata Kuliah Uji" in response.data
