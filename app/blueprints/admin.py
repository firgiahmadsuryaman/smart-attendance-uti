from datetime import datetime, date
from io import BytesIO, StringIO
import csv
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, send_file, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from ..extensions import db
from ..models import (User, StudyProgram, Semester, Course, ClassOffering, ClassSchedule,
                      CourseEnrollment, AttendanceSession, Attendance, FaceProfile, ActivityLog, Notification)
from ..utils import role_required, log_action

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
WEEKDAYS = [(0, "Senin"), (1, "Selasa"), (2, "Rabu"), (3, "Kamis"), (4, "Jumat"), (5, "Sabtu"), (6, "Minggu")]


@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html", page_title="Dashboard Admin",
        counts={"students": User.query.filter_by(role="student").count(),
                "lecturers": User.query.filter_by(role="lecturer").count(),
                "programs": StudyProgram.query.count(), "courses": Course.query.count(),
                "offerings": ClassOffering.query.count(), "face": FaceProfile.query.count(),
                "pending": CourseEnrollment.query.filter_by(status="PENDING").count(),
                "sessions": AttendanceSession.query.count()},
        recent_logs=ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all())


@admin_bp.route("/programs", methods=["GET", "POST"])
@login_required
@role_required("admin")
def programs():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        faculty = (request.form.get("faculty") or "").strip()
        if not name or not code:
            flash("Nama dan kode program studi wajib diisi.", "danger")
        else:
            try:
                db.session.add(StudyProgram(name=name, code=code, faculty=faculty or None))
                log_action("PROGRAM_CREATE", f"Membuat program studi {code} - {name}")
                db.session.commit()
                flash("Program studi berhasil ditambahkan.", "success")
                return redirect(url_for("admin.programs"))
            except IntegrityError:
                db.session.rollback()
                flash("Kode atau nama program studi sudah digunakan.", "danger")
    return render_template("admin/programs.html", page_title="Program Studi",
                           programs=StudyProgram.query.order_by(StudyProgram.name).all())


@admin_bp.route("/programs/<int:program_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_program(program_id):
    program = db.get_or_404(StudyProgram, program_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        faculty = (request.form.get("faculty") or "").strip() or None
        if not name or not code:
            flash("Nama dan kode program studi wajib diisi.", "danger")
        else:
            program.name, program.code, program.faculty = name, code, faculty
            try:
                log_action("PROGRAM_UPDATE", f"Memperbarui program studi {code}")
                db.session.commit()
                flash("Program studi berhasil diperbarui.", "success")
                return redirect(url_for("admin.programs"))
            except IntegrityError:
                db.session.rollback()
                flash("Kode atau nama program studi sudah digunakan.", "danger")
    return render_template("admin/program_edit.html", page_title="Edit Program Studi", program=program)


@admin_bp.post("/programs/<int:program_id>/toggle")
@login_required
@role_required("admin")
def toggle_program(program_id):
    program = db.get_or_404(StudyProgram, program_id)
    program.is_active = not program.is_active
    log_action("PROGRAM_TOGGLE", f"Program {program.code}: active={program.is_active}")
    db.session.commit()
    flash("Status program studi diperbarui.", "success")
    return redirect(url_for("admin.programs"))


@admin_bp.route("/semesters", methods=["GET", "POST"])
@login_required
@role_required("admin")
def semesters():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        academic_year = (request.form.get("academic_year") or "").strip()
        term = (request.form.get("term") or "").strip()
        start = request.form.get("start_date") or None
        end = request.form.get("end_date") or None
        if not name or not academic_year or term not in ("Ganjil", "Genap"):
            flash("Nama semester, tahun akademik, dan jenis semester wajib diisi.", "danger")
        else:
            try:
                semester = Semester(name=name, academic_year=academic_year, term=term,
                    start_date=date.fromisoformat(start) if start else None,
                    end_date=date.fromisoformat(end) if end else None,
                    enrollment_open=True, is_active=False)
                db.session.add(semester)
                log_action("SEMESTER_CREATE", f"Membuat semester {name}")
                db.session.commit()
                flash("Semester berhasil dibuat. Aktifkan semester untuk menjadikannya semester berjalan.", "success")
                return redirect(url_for("admin.semesters"))
            except (ValueError, IntegrityError):
                db.session.rollback()
                flash("Tanggal atau nama semester tidak valid/duplikat.", "danger")
    return render_template("admin/semesters.html", page_title="Semester Akademik",
                           semesters=Semester.query.order_by(Semester.id.desc()).all())


@admin_bp.post("/semesters/<int:semester_id>/activate")
@login_required
@role_required("admin")
def activate_semester(semester_id):
    semester = db.get_or_404(Semester, semester_id)
    Semester.query.update({Semester.is_active: False})
    semester.is_active = True
    log_action("SEMESTER_ACTIVATE", f"Semester aktif menjadi {semester.name}")
    db.session.commit()
    flash(f"{semester.name} sekarang menjadi semester aktif.", "success")
    return redirect(url_for("admin.semesters"))


@admin_bp.post("/semesters/<int:semester_id>/toggle-enrollment")
@login_required
@role_required("admin")
def toggle_enrollment(semester_id):
    semester = db.get_or_404(Semester, semester_id)
    semester.enrollment_open = not semester.enrollment_open
    log_action("SEMESTER_ENROLLMENT_TOGGLE", f"{semester.name}: enrollment_open={semester.enrollment_open}")
    db.session.commit()
    flash("Status pemilihan mata kuliah diperbarui.", "success")
    return redirect(url_for("admin.semesters"))


@admin_bp.route("/courses", methods=["GET", "POST"])
@login_required
@role_required("admin")
def courses():
    programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        name = (request.form.get("name") or "").strip()
        credits = request.form.get("credits", type=int) or 2
        recommended_semester = request.form.get("recommended_semester", type=int)
        program_id = request.form.get("program_id", type=int)
        course_type = (request.form.get("course_type") or "W").strip().upper()
        program = db.session.get(StudyProgram, program_id) if program_id else None
        if (not code or not name or not program or credits < 1 or credits > 6
                or recommended_semester not in range(1, 9) or course_type not in ("W", "P")):
            flash("Lengkapi kode, nama, program studi, semester kurikulum (1–8), W/P, dan SKS dengan benar.", "danger")
        else:
            try:
                db.session.add(Course(code=code, name=name, credits=credits,
                    recommended_semester=recommended_semester, course_type=course_type, program_id=program.id,
                    description=(request.form.get("description") or "").strip() or None))
                log_action("COURSE_CREATE", f"Membuat mata kuliah {code} - {name}")
                db.session.commit()
                flash("Mata kuliah berhasil ditambahkan.", "success")
                return redirect(url_for("admin.courses"))
            except IntegrityError:
                db.session.rollback()
                flash("Kode mata kuliah sudah digunakan.", "danger")
    query = Course.query.join(StudyProgram)
    selected_program = request.args.get("program_id", type=int)
    selected_semester = request.args.get("recommended_semester", type=int)
    selected_type = request.args.get("course_type", "")
    search = (request.args.get("q") or "").strip()
    if selected_program:
        query = query.filter(Course.program_id == selected_program)
    if selected_semester:
        query = query.filter(Course.recommended_semester == selected_semester)
    if selected_type in ("W", "P"):
        query = query.filter(Course.course_type == selected_type)
    if search:
        query = query.filter(or_(Course.code.ilike(f"%{search}%"), Course.name.ilike(f"%{search}%")))
    all_courses = query.order_by(StudyProgram.name, Course.recommended_semester, Course.code).all()
    return render_template("admin/courses.html", page_title="Katalog Mata Kuliah", courses=all_courses,
                           programs=programs, selected_program=selected_program,
                           selected_semester=selected_semester, selected_type=selected_type, search=search,
                           semester_options=range(1, 9))


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()
        name = (request.form.get("name") or "").strip()
        credits = request.form.get("credits", type=int) or 2
        recommended_semester = request.form.get("recommended_semester", type=int)
        course_type = (request.form.get("course_type") or "W").strip().upper()
        program = db.session.get(StudyProgram, request.form.get("program_id", type=int))
        if (not code or not name or not program or credits < 1 or credits > 6
                or recommended_semester not in range(1, 9) or course_type not in ("W", "P")):
            flash("Lengkapi kode, nama, program studi, semester kurikulum (1–8), W/P, dan SKS dengan benar.", "danger")
        else:
            course.code, course.name, course.credits = code, name, credits
            course.recommended_semester, course.program_id = recommended_semester, program.id
            course.course_type = course_type
            course.description = (request.form.get("description") or "").strip() or None
            try:
                log_action("COURSE_UPDATE", f"Memperbarui mata kuliah {code}")
                db.session.commit()
                flash("Mata kuliah berhasil diperbarui.", "success")
                return redirect(url_for("admin.courses"))
            except IntegrityError:
                db.session.rollback()
                flash("Kode mata kuliah sudah digunakan.", "danger")
    return render_template("admin/course_edit.html", page_title="Edit Mata Kuliah", course=course, programs=programs)


@admin_bp.post("/courses/<int:course_id>/toggle")
@login_required
@role_required("admin")
def toggle_course(course_id):
    course = db.get_or_404(Course, course_id)
    course.is_active = not course.is_active
    log_action("COURSE_TOGGLE", f"Mata kuliah {course.code}: active={course.is_active}")
    db.session.commit()
    flash("Status mata kuliah diperbarui.", "success")
    return redirect(url_for("admin.courses"))


def _time_or_error(value):
    return datetime.strptime(value, "%H:%M").time()


def _submitted_schedule_slots(delivery_mode="OFFLINE", default_room=""):
    """Parse weekly slots with their own online/offline mode; supports older single-mode forms."""
    weekdays = request.form.getlist("weekday[]") or ([request.form.get("weekday")] if request.form.get("weekday") is not None else [])
    starts = request.form.getlist("start_time[]") or ([request.form.get("start_time")] if request.form.get("start_time") else [])
    ends = request.form.getlist("end_time[]") or ([request.form.get("end_time")] if request.form.get("end_time") else [])
    rooms = request.form.getlist("room[]") or ([request.form.get("room", "")] if weekdays else [])
    modes = request.form.getlist("delivery_mode[]")
    urls = request.form.getlist("online_url[]")
    legacy_mode = (request.form.get("delivery_mode") or delivery_mode or "OFFLINE").upper()
    legacy_url = (request.form.get("online_url") or "").strip() or None
    slots = []
    max_rows = max(len(weekdays), len(starts), len(ends), len(rooms), len(modes), len(urls))
    for index in range(max_rows):
        weekday_value = weekdays[index] if index < len(weekdays) else ""
        start_value = starts[index] if index < len(starts) else ""
        end_value = ends[index] if index < len(ends) else ""
        room_value = rooms[index] if index < len(rooms) else ""
        if not str(weekday_value).strip() and not str(start_value).strip() and not str(end_value).strip():
            continue
        mode = (modes[index] if index < len(modes) else legacy_mode).upper()
        online_url = (urls[index] if index < len(urls) else legacy_url) or ""
        online_url = online_url.strip() or None
        if mode not in ("ONLINE", "OFFLINE"):
            raise ValueError("Pilih moda online atau tatap muka pada setiap slot.")
        if mode == "ONLINE" and online_url and not online_url.lower().startswith(("https://", "http://")):
            raise ValueError("Tautan meeting online harus menggunakan http:// atau https://.")
        try:
            weekday = int(weekday_value)
            start_time = _time_or_error(start_value)
            end_time = _time_or_error(end_value)
        except (ValueError, TypeError):
            raise ValueError("Setiap slot jadwal harus memiliki hari, jam mulai, dan jam selesai yang valid.")
        room = (room_value or default_room or "").strip()
        if mode == "ONLINE":
            room = "Online"
        if weekday not in range(7) or start_time >= end_time:
            raise ValueError("Hari dan rentang jam pada jadwal tidak valid.")
        if mode == "OFFLINE" and not room:
            raise ValueError("Ruang wajib diisi untuk perkuliahan tatap muka.")
        slots.append({"weekday": weekday, "start_time": start_time, "end_time": end_time,
                      "room": room or "Online", "delivery_mode": mode, "online_url": online_url if mode == "ONLINE" else None})
    if not slots:
        raise ValueError("Tambahkan minimal satu slot jadwal mingguan.")
    for index, one in enumerate(slots):
        for other in slots[index + 1:]:
            if one["weekday"] == other["weekday"] and one["start_time"] < other["end_time"] and other["start_time"] < one["end_time"]:
                raise ValueError("Dua slot jadwal pada hari yang sama saling bertabrakan.")
    return slots


def _aggregate_delivery_mode(slots):
    modes = {slot["delivery_mode"] for slot in slots}
    return next(iter(modes)) if len(modes) == 1 else "MIXED"


def _legacy_online_url(slots):
    return next((slot["online_url"] for slot in slots if slot["delivery_mode"] == "ONLINE" and slot.get("online_url")), None)


def _find_schedule_conflict(semester_id, weekday, start_time, end_time, room, lecturer_id, exclude_offering_id=None,
                            delivery_mode="OFFLINE"):
    query = ClassSchedule.query.join(ClassOffering).filter(ClassOffering.semester_id == semester_id)
    if exclude_offering_id is not None:
        query = query.filter(ClassOffering.id != exclude_offering_id)
    for existing in query.all():
        if existing.weekday != weekday:
            continue
        overlaps = start_time < existing.end_time and existing.start_time < end_time
        if not overlaps:
            continue
        existing_mode = getattr(existing, "delivery_mode", None) or existing.offering.delivery_mode or "OFFLINE"
        same_mode = existing_mode == delivery_mode
        if delivery_mode == "OFFLINE" and same_mode and existing.room.strip().casefold() == room.strip().casefold():
            return f"Ruang {room} bentrok dengan {existing.offering.course.code} {existing.offering.class_code} pada waktu yang sama."
        if existing.offering.lecturer_id == lecturer_id:
            return f"Dosen tersebut sudah mengajar {existing.offering.course.code} {existing.offering.class_code} pada waktu yang sama."
    return None


def _validate_slots(semester, lecturer, slots, delivery_mode=None, exclude_offering_id=None):
    for slot in slots:
        conflict = _find_schedule_conflict(semester.id, slot["weekday"], slot["start_time"], slot["end_time"],
                                           slot["room"], lecturer.id, exclude_offering_id, slot["delivery_mode"])
        if conflict:
            raise ValueError(conflict)


@admin_bp.route("/offerings", methods=["GET", "POST"])
@login_required
@role_required("admin")
def offerings():
    courses = Course.query.filter_by(is_active=True).order_by(Course.code).all()
    semesters = Semester.query.order_by(Semester.id.desc()).all()
    lecturers = User.query.filter_by(role="lecturer", active=True).order_by(User.full_name).all()
    programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
    if request.method == "POST":
        course = None
        semester = db.session.get(Semester, request.form.get("semester_id", type=int))
        lecturer = db.session.get(User, request.form.get("lecturer_id", type=int))
        class_code = (request.form.get("class_code") or "").strip().upper()
        capacity = request.form.get("capacity", type=int) or 40
        delivery_mode = (request.form.get("delivery_mode") or "OFFLINE").upper()
        online_url = (request.form.get("online_url") or "").strip() or None
        course_entry_mode = (request.form.get("course_entry_mode") or "catalog").lower()
        try:
            if course_entry_mode == "new":
                course_code = (request.form.get("new_course_code") or "").strip().upper()
                course_name = (request.form.get("new_course_name") or "").strip()
                program = db.session.get(StudyProgram, request.form.get("new_program_id", type=int))
                credits = request.form.get("new_credits", type=int) or 2
                recommended_semester = request.form.get("new_recommended_semester", type=int)
                course_type = (request.form.get("new_course_type") or "W").upper()
                if (not course_code or not course_name or not program or credits not in range(1, 7)
                        or recommended_semester not in range(1, 9) or course_type not in ("W", "P")):
                    raise ValueError("Lengkapi kode, nama, program studi, semester kurikulum 1–8, W/P, dan SKS untuk mata kuliah baru.")
                if Course.query.filter_by(code=course_code).first():
                    raise ValueError("Kode mata kuliah sudah ada. Pilih mata kuliah itu dari katalog agar tidak terjadi duplikasi.")
                course = Course(code=course_code, name=course_name, program_id=program.id, credits=credits,
                                recommended_semester=recommended_semester, course_type=course_type,
                                description=(request.form.get("new_description") or "").strip() or None,
                                is_active=True)
                db.session.add(course)
                db.session.flush()
            else:
                course = db.session.get(Course, request.form.get("course_id", type=int))
                if not course or not course.is_active:
                    raise ValueError("Pilih mata kuliah aktif dari katalog atau lengkapi data mata kuliah baru.")
            if not semester or not lecturer or lecturer.role != "lecturer" or not class_code:
                raise ValueError("Lengkapi semester, dosen, dan kode kelas.")
            if capacity < 1:
                raise ValueError("Kapasitas kelas harus minimal satu.")
            slots = _submitted_schedule_slots(delivery_mode)
            _validate_slots(semester, lecturer, slots)
            delivery_mode = _aggregate_delivery_mode(slots)
            online_url = _legacy_online_url(slots)
            offering = ClassOffering(course=course, semester=semester, lecturer=lecturer,
                class_code=class_code, capacity=capacity, status="OPEN", delivery_mode=delivery_mode,
                online_url=online_url, created_by_id=current_user.id)
            offering.schedules.extend(ClassSchedule(**slot) for slot in slots)
            db.session.add(offering)
            log_action("OFFERING_CREATE", f"Membuka {course.code} kelas {class_code} untuk {semester.name}; {delivery_mode}; {len(slots)} pertemuan/minggu")
            db.session.commit()
            flash("Penawaran kelas dan seluruh slot jadwal berhasil dibuat.", "success")
            return redirect(url_for("admin.offerings"))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Kelas tersebut sudah dibuat untuk mata kuliah dan semester yang sama.", "danger")
    all_offerings = ClassOffering.query.join(Course).join(Semester).order_by(Semester.id.desc(), Course.code, ClassOffering.class_code).all()
    return render_template("admin/offerings.html", page_title="Kelas & Jadwal", courses=courses, semesters=semesters,
                           lecturers=lecturers, weekdays=WEEKDAYS, offerings=all_offerings, programs=programs,
                           semester_options=range(1, 9))


@admin_bp.route("/offerings/<int:offering_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_offering(offering_id):
    offering = db.get_or_404(ClassOffering, offering_id)
    if request.method == "POST":
        lecturer = db.session.get(User, request.form.get("lecturer_id", type=int))
        try:
            class_code = (request.form.get("class_code") or "").strip().upper()
            capacity = request.form.get("capacity", type=int) or 40
            status = request.form.get("status", "OPEN")
            delivery_mode = (request.form.get("delivery_mode") or "OFFLINE").upper()
            online_url = (request.form.get("online_url") or "").strip() or None
            if not lecturer or lecturer.role != "lecturer" or not class_code or capacity < 1 or status not in ("OPEN", "CLOSED"):
                raise ValueError("Periksa kembali data kelas.")
            slots = _submitted_schedule_slots(delivery_mode)
            _validate_slots(offering.semester, lecturer, slots, exclude_offering_id=offering.id)
            delivery_mode = _aggregate_delivery_mode(slots)
            online_url = _legacy_online_url(slots)
            offering.lecturer_id = lecturer.id
            offering.class_code = class_code
            offering.capacity = capacity
            offering.status = status
            offering.delivery_mode = delivery_mode
            offering.online_url = online_url
            offering.schedules.clear()
            for slot in slots:
                offering.schedules.append(ClassSchedule(**slot))
            log_action("OFFERING_UPDATE", f"Memperbarui kelas {offering.course.code} {class_code}; {delivery_mode}; {len(slots)} slot/minggu")
            db.session.commit()
            flash("Kelas dan jadwal berhasil diperbarui.", "success")
            return redirect(url_for("admin.offerings"))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Kode kelas sudah digunakan pada mata kuliah dan semester ini.", "danger")
    lecturers = User.query.filter_by(role="lecturer", active=True).order_by(User.full_name).all()
    return render_template("admin/offering_edit.html", page_title="Edit Kelas & Jadwal", offering=offering,
                           lecturers=lecturers, weekdays=WEEKDAYS)


@admin_bp.post("/offerings/<int:offering_id>/toggle")
@login_required
@role_required("admin")
def toggle_offering(offering_id):
    offering = db.get_or_404(ClassOffering, offering_id)
    offering.status = "CLOSED" if offering.status == "OPEN" else "OPEN"
    log_action("OFFERING_TOGGLE", f"Kelas {offering.class_code} menjadi {offering.status}")
    db.session.commit()
    flash("Status penawaran kelas diperbarui.", "success")
    return redirect(url_for("admin.offerings"))


@admin_bp.route("/lecturers", methods=["GET", "POST"])
@login_required
@role_required("admin")
def lecturers():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        employee_id = (request.form.get("employee_id") or "").strip() or None
        password = request.form.get("password") or ""
        if not full_name or not email or len(password) < 8:
            flash("Nama, email, dan password minimal 8 karakter wajib diisi.", "danger")
        elif User.query.filter_by(email=email).first() or (employee_id and User.query.filter_by(employee_id=employee_id).first()):
            flash("Email atau ID dosen sudah terdaftar.", "danger")
        else:
            user = User(full_name=full_name, email=email, employee_id=employee_id, role="lecturer", active=True)
            user.set_password(password)
            db.session.add(user)
            log_action("LECTURER_CREATE", f"Membuat akun dosen {email}")
            db.session.commit()
            flash("Akun dosen berhasil dibuat.", "success")
            return redirect(url_for("admin.lecturers"))
    lecturers_list = User.query.filter_by(role="lecturer").order_by(User.full_name).all()
    return render_template("admin/lecturers.html", page_title="Data Dosen", lecturers=lecturers_list)


@admin_bp.route("/students")
@login_required
@role_required("admin")
def students():
    search = (request.args.get("q") or "").strip()
    query = User.query.filter_by(role="student")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(like), User.npm.ilike(like), User.email.ilike(like)))
    return render_template("admin/students.html", page_title="Data Mahasiswa", students=query.order_by(User.full_name).all(), search=search)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Edit akun Admin tidak tersedia melalui menu ini.", "warning")
        return redirect(url_for("admin.dashboard"))
    programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        new_password = request.form.get("new_password") or ""
        if not full_name or not email:
            flash("Nama dan email wajib diisi.", "danger")
        elif User.query.filter(User.email == email, User.id != user.id).first():
            flash("Email sudah digunakan akun lain.", "danger")
        else:
            user.full_name, user.email = full_name, email
            if user.role == "student":
                npm = (request.form.get("npm") or "").strip()
                program = db.session.get(StudyProgram, request.form.get("program_id", type=int))
                if not npm or not program:
                    flash("NPM dan program studi wajib diisi.", "danger")
                    return render_template("admin/user_edit.html", page_title="Edit Pengguna", user=user, programs=programs)
                if User.query.filter(User.npm == npm, User.id != user.id).first():
                    flash("NPM sudah digunakan mahasiswa lain.", "danger")
                    return render_template("admin/user_edit.html", page_title="Edit Pengguna", user=user, programs=programs)
                user.npm, user.program_id = npm, program.id
                user.cohort = (request.form.get("cohort") or "").strip() or None
            else:
                employee_id = (request.form.get("employee_id") or "").strip() or None
                if employee_id and User.query.filter(User.employee_id == employee_id, User.id != user.id).first():
                    flash("ID dosen sudah digunakan.", "danger")
                    return render_template("admin/user_edit.html", page_title="Edit Pengguna", user=user, programs=programs)
                user.employee_id = employee_id
            if new_password:
                if len(new_password) < 8:
                    flash("Password baru minimal 8 karakter.", "danger")
                    return render_template("admin/user_edit.html", page_title="Edit Pengguna", user=user, programs=programs)
                user.set_password(new_password)
            try:
                log_action("USER_UPDATE", f"Memperbarui data {user.role}: {user.email}")
                db.session.commit()
                flash("Data pengguna berhasil diperbarui.", "success")
                return redirect(url_for("admin.students" if user.role == "student" else "admin.lecturers"))
            except IntegrityError:
                db.session.rollback()
                flash("Data tidak bisa disimpan karena ada nilai unik yang duplikat.", "danger")
    return render_template("admin/user_edit.html", page_title="Edit Pengguna", user=user, programs=programs)


@admin_bp.post("/users/<int:user_id>/toggle")
@login_required
@role_required("admin")
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Status akun Admin tidak dapat diubah dari menu ini.", "warning")
    else:
        user.active = not user.active
        log_action("USER_TOGGLE", f"User {user.email} active={user.active}")
        db.session.commit()
        flash("Status akun diperbarui.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/enrollments")
@login_required
@role_required("admin")
def enrollments():
    status = request.args.get("status", "PENDING").upper()
    if status not in ("PENDING", "APPROVED", "REJECTED", "ALL"):
        status = "PENDING"
    # Gunakan ON clause eksplisit untuk kedua join.
    # ClassOffering memiliki beberapa FK ke users (lecturer_id dan created_by_id),
    # sedangkan CourseEnrollment juga memiliki student_id dan reviewed_by_id ke users.
    # Join eksplisit menghindari AmbiguousForeignKeysError pada SQLAlchemy.
    query = (
        db.session.query(CourseEnrollment)
        .select_from(CourseEnrollment)
        .join(User, User.id == CourseEnrollment.student_id)
        .join(ClassOffering, ClassOffering.id == CourseEnrollment.offering_id)
    )
    if status != "ALL":
        query = query.filter(CourseEnrollment.status == status)
    rows = query.order_by(CourseEnrollment.requested_at.desc()).all()
    return render_template("admin/enrollments.html", page_title="Pengambilan Mata Kuliah", enrollments=rows, active_status=status)


@admin_bp.post("/enrollments/<int:enrollment_id>/review")
@login_required
@role_required("admin")
def review_enrollment(enrollment_id):
    enrollment = db.get_or_404(CourseEnrollment, enrollment_id)
    decision = (request.form.get("decision") or "").upper()
    if decision not in ("APPROVED", "REJECTED"):
        flash("Keputusan tidak valid.", "danger")
    elif enrollment.status != "PENDING":
        flash("Pengajuan ini sudah diproses.", "warning")
    else:
        if decision == "APPROVED":
            approved_count = CourseEnrollment.query.filter_by(offering_id=enrollment.offering_id, status="APPROVED").count()
            if approved_count >= enrollment.offering.capacity:
                flash("Kapasitas kelas sudah penuh.", "danger")
                return redirect(url_for("admin.enrollments"))
            conflicts = CourseEnrollment.query.filter_by(student_id=enrollment.student_id, status="APPROVED").all()
            target_schedules = list(enrollment.offering.schedules)
            for existing in conflicts:
                if existing.offering.semester_id != enrollment.offering.semester_id:
                    continue
                if existing.offering.course_id == enrollment.offering.course_id:
                    flash(f"Mahasiswa sudah mengambil {existing.offering.course.name} pada kelas {existing.offering.class_code}.", "danger")
                    return redirect(url_for("admin.enrollments"))
                for target_schedule in target_schedules:
                    for old_schedule in existing.offering.schedules:
                        overlap = (target_schedule.weekday == old_schedule.weekday and
                                   target_schedule.start_time < old_schedule.end_time and
                                   old_schedule.start_time < target_schedule.end_time)
                        if overlap:
                            flash(f"Jadwal bentrok pada hari {target_schedule.weekday_name} dengan {existing.offering.course.name} ({existing.offering.class_code}).", "danger")
                            return redirect(url_for("admin.enrollments"))
        enrollment.status = decision
        enrollment.reviewed_at = datetime.now()
        enrollment.reviewed_by_id = current_user.id
        enrollment.review_note = (request.form.get("review_note") or "").strip() or None
        log_action("ENROLLMENT_REVIEW", f"Enrolmen #{enrollment.id} {decision}")
        db.session.add(Notification(
            user_id=enrollment.student_id,
            title="Pengajuan mata kuliah diperbarui",
            message=f"Pengajuan {enrollment.offering.course.name} kelas {enrollment.offering.class_code}: {decision}.",
        ))
        db.session.commit()
        flash(f"Pengajuan berhasil {decision.lower()}.", "success")
    return redirect(url_for("admin.enrollments"))


@admin_bp.route("/face-profiles")
@login_required
@role_required("admin")
def face_profiles():
    students = User.query.filter_by(role="student").order_by(User.full_name).all()
    return render_template("admin/face_profiles.html", page_title="Monitoring Face Profile", students=students)


@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    rows = Attendance.query.join(AttendanceSession).join(ClassOffering).join(Course).join(User, Attendance.student_id == User.id).order_by(Attendance.created_at.desc()).limit(500).all()
    return render_template("admin/reports.html", page_title="Rekap Presensi", attendances=rows)


@admin_bp.route("/reports/export.csv")
@login_required
@role_required("admin")
def export_reports_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NPM", "Nama", "Mata Kuliah", "Kelas", "Pertemuan", "Status", "Waktu Presensi"])
    rows = Attendance.query.join(AttendanceSession).join(ClassOffering).join(Course).join(User, Attendance.student_id == User.id).order_by(Attendance.created_at.desc()).all()
    for att in rows:
        writer.writerow([att.student.npm or "", att.student.full_name, att.session.offering.course.name,
                         att.session.offering.class_code, att.session.session_number, att.status,
                         att.checked_in_at.strftime("%Y-%m-%d %H:%M:%S") if att.checked_in_at else ""])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    response.headers["Content-Disposition"] = "attachment; filename=rekap-presensi.csv"
    return response


@admin_bp.route("/logs")
@login_required
@role_required("admin")
def logs():
    entries = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(300).all()
    return render_template("admin/logs.html", page_title="Log Aktivitas", entries=entries)
