from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)  # admin, lecturer, student
    npm = db.Column(db.String(30), unique=True, nullable=True, index=True)
    employee_id = db.Column(db.String(40), unique=True, nullable=True)
    program_id = db.Column(db.Integer, db.ForeignKey("study_programs.id"), nullable=True)
    cohort = db.Column(db.String(10), nullable=True)
    # Asal identitas: PUSTIK_API, SAMPLE, atau MANUAL. NULL berarti diisi manual.
    identity_source = db.Column(db.String(20), nullable=True)
    # Nomor Induk Dosen Nasional, terpisah dari employee_id yang menyimpan NIK.
    nidn = db.Column(db.String(30), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    program = db.relationship("StudyProgram", back_populates="users")
    face_profile = db.relationship("FaceProfile", back_populates="student", uselist=False,
                                   cascade="all, delete-orphan")
    enrollments = db.relationship("CourseEnrollment", back_populates="student",
                                  foreign_keys="CourseEnrollment.student_id")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @property
    def role_label(self) -> str:
        return {"admin": "Administrator", "lecturer": "Dosen", "student": "Mahasiswa"}.get(self.role, self.role.title())


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class StudyProgram(db.Model):
    __tablename__ = "study_programs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    faculty = db.Column(db.String(140), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    users = db.relationship("User", back_populates="program")
    courses = db.relationship("Course", back_populates="program")


class Semester(db.Model):
    __tablename__ = "semesters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    academic_year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(20), nullable=False)  # Ganjil / Genap
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    enrollment_open = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    offerings = db.relationship("ClassOffering", back_populates="semester")


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=2)
    recommended_semester = db.Column(db.Integer, nullable=True)
    # W = Wajib, P = Pilihan (sesuai kolom W/P pada daftar mata kuliah)
    course_type = db.Column(db.String(1), nullable=False, default="W")
    program_id = db.Column(db.Integer, db.ForeignKey("study_programs.id"), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    program = db.relationship("StudyProgram", back_populates="courses")
    offerings = db.relationship("ClassOffering", back_populates="course")


class ClassOffering(db.Model):
    __tablename__ = "class_offerings"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semesters.id"), nullable=False, index=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    class_code = db.Column(db.String(30), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=40)
    status = db.Column(db.String(20), nullable=False, default="OPEN")  # OPEN / CLOSED
    delivery_mode = db.Column(db.String(20), nullable=False, default="OFFLINE")  # OFFLINE / ONLINE
    online_url = db.Column(db.String(500), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    course = db.relationship("Course", back_populates="offerings")
    semester = db.relationship("Semester", back_populates="offerings")
    lecturer = db.relationship("User", foreign_keys=[lecturer_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    schedules = db.relationship("ClassSchedule", back_populates="offering", cascade="all, delete-orphan",
                                 order_by="ClassSchedule.weekday, ClassSchedule.start_time")
    enrollments = db.relationship("CourseEnrollment", back_populates="offering", cascade="all, delete-orphan")
    sessions = db.relationship("AttendanceSession", back_populates="offering", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("course_id", "semester_id", "class_code", name="uq_offering_course_semester_class"),)

    @property
    def delivery_mode_label(self):
        return "Online" if self.delivery_mode == "ONLINE" else "Tatap Muka"

    @property
    def meetings_per_week(self):
        return len(self.schedules or [])


class ClassSchedule(db.Model):
    __tablename__ = "class_schedules"

    id = db.Column(db.Integer, primary_key=True)
    offering_id = db.Column(db.Integer, db.ForeignKey("class_offerings.id"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)  # Monday=0 ... Sunday=6
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(60), nullable=False)

    offering = db.relationship("ClassOffering", back_populates="schedules")

    @property
    def weekday_name(self):
        return ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][self.weekday]


class CourseEnrollment(db.Model):
    __tablename__ = "course_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    offering_id = db.Column(db.Integer, db.ForeignKey("class_offerings.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)
    requested_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    review_note = db.Column(db.String(255), nullable=True)

    student = db.relationship("User", back_populates="enrollments", foreign_keys=[student_id])
    offering = db.relationship("ClassOffering", back_populates="enrollments")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (db.UniqueConstraint("student_id", "offering_id", name="uq_student_offering"),)


class FaceProfile(db.Model):
    __tablename__ = "face_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    embedding_json = db.Column(db.Text, nullable=False)
    model_name = db.Column(db.String(50), nullable=False, default="ArcFace")
    consent_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    student = db.relationship("User", back_populates="face_profile")


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    offering_id = db.Column(db.Integer, db.ForeignKey("class_offerings.id"), nullable=False, index=True)
    session_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    opened_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    late_after = db.Column(db.DateTime, nullable=False)
    closes_at = db.Column(db.DateTime, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    opened_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Token acak panjang untuk QR URL dan kode pendek yang bisa diketik di desktop.
    access_token = db.Column(db.String(80), nullable=True, unique=True, index=True)
    session_code = db.Column(db.String(12), nullable=True, unique=True, index=True)

    offering = db.relationship("ClassOffering", back_populates="sessions")
    opened_by = db.relationship("User", foreign_keys=[opened_by_id])
    attendances = db.relationship("Attendance", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("offering_id", "session_number", name="uq_offering_session_number"),)


class Attendance(db.Model):
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)  # PRESENT / LATE / ABSENT
    checked_in_at = db.Column(db.DateTime, nullable=True)
    match_score = db.Column(db.Float, nullable=True)
    verification_method = db.Column(db.String(40), nullable=False, default="FACE_RECOGNITION")
    correction_reason = db.Column(db.String(255), nullable=True)
    corrected_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    session = db.relationship("AttendanceSession", back_populates="attendances")
    student = db.relationship("User", foreign_keys=[student_id])
    corrected_by = db.relationship("User", foreign_keys=[corrected_by_id])

    __table_args__ = (db.UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User")


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(700), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    actor = db.relationship("User", foreign_keys=[actor_id])
