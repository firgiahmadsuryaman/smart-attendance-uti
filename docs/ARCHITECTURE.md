# Arsitektur Sistem

```mermaid
flowchart TD
    A[Browser: Bootstrap + JavaScript] --> B[Flask Routes / Blueprints]
    B --> C[Auth + RBAC]
    B --> D[Akademik: Semester, Course, Offering, Schedule, Enrolment]
    B --> E[Sesi Presensi + Aturan Waktu]
    E --> F[Face Engine: DeepFace ArcFace + OpenCV/MediaPipe Challenge]
    D --> G[(SQLite atau MySQL)]
    E --> G
    F --> E
    B --> H[PDF/Excel Export]
```

## Relasi konseptual

```mermaid
erDiagram
    STUDY_PROGRAM ||--o{ USERS : has
    STUDY_PROGRAM ||--o{ COURSES : provides
    SEMESTER ||--o{ CLASS_OFFERINGS : opens
    COURSES ||--o{ CLASS_OFFERINGS : offered_as
    USERS ||--o{ CLASS_OFFERINGS : teaches
    CLASS_OFFERINGS ||--o{ CLASS_SCHEDULES : scheduled_at
    USERS ||--o{ COURSE_ENROLLMENTS : requests
    CLASS_OFFERINGS ||--o{ COURSE_ENROLLMENTS : includes
    USERS ||--o| FACE_PROFILES : enrolls
    CLASS_OFFERINGS ||--o{ ATTENDANCE_SESSIONS : has
    ATTENDANCE_SESSIONS ||--o{ ATTENDANCES : records
    USERS ||--o{ ATTENDANCES : attends
    USERS ||--o{ ACTIVITY_LOGS : acts
```

## Endpoint penting
- `POST /student/api/face/enroll` — pendaftaran Face Profile setelah login, dengan challenge sampel depan/kedip/kiri/kanan.
- `POST /student/api/attendance/<session_id>/verify` — pemeriksaan blink, face embedding, token, enrolmen APPROVED, sesi, jendela waktu, dan duplikasi.
- Route sesi dosen membuat kode pendek serta token acak panjang untuk QR.

## Prinsip keamanan
1. Backend memvalidasi semua hak presensi, bukan hanya frontend.
2. Enrolmen `APPROVED` diperlukan untuk jadwal dan hak presensi.
3. Face engine memverifikasi identitas; backend menentukan apakah presensi diperbolehkan.
4. Unique constraint pada `(session_id, student_id)` mencegah presensi ganda.
5. Sesi yang kedaluwarsa ditutup pada permintaan terautentikasi berikutnya dan peserta yang belum tercatat difinalisasi `ABSENT`.
6. Challenge kedip/gerak kepala berbasis sampel adalah mitigasi dasar; tidak menjamin penolakan semua serangan foto/video.
7. Data biometrik diperlakukan sebagai data sensitif dan harus dilindungi dengan dasar pemrosesan, persetujuan dan retensi yang sesuai.
