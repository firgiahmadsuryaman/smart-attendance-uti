# Integrasi Data Akademik — Sumber PUSTIK

Dokumen ini mencatat hasil investigasi atas halaman register
`https://agent.teknokrat.ac.id/auth/register` (Sistem Administrasi Surat / "Agent Sang Juara",
Universitas Teknokrat Indonesia), tanggal 17 Oktober 2026.

Tujuannya: menentukan dari mana aplikasi tersebut mengambil data mahasiswa dan dosen, agar
aplikasi Smart Attendance dapat memakai sumber data yang sama sehingga menjadi satu ekosistem.

**Status dokumen:** catatan temuan investigasi. Belum ada kode integrasi di proyek ini.
Tidak ada kode baru, tidak ada perubahan model, dan tidak ada permintaan akses yang diajukan.

---

## 1. Kesimpulan

Sumber data mahasiswa dan dosen pada aplikasi tersebut adalah **PUSTIK** — Pusat Sistem
Teknologi Informasi dan Komunikasi Universitas Teknokrat Indonesia.

Bukan PDDIKTI, bukan SIAKAD publik. PUSTIK dipanggil dari sisi server (server-to-server),
sehingga URL dan kredensialnya tidak pernah sampai ke browser.

## 2. Bukti

### 2.1 Pesan galat yang menyebut sumbernya

Halaman register memiliki toggle **Mahasiswa** (input NPM) dan **Dosen** (input NIK). Tombol
"Periksa"/"Cek" memanggil endpoint berikut:

```http
POST /backend/auth/resolve/student
Content-Type: application/json

{"npm":"<npm>"}
```

```json
{"ok":false,"error":{"code":"BAD_REQUEST","message":"NPM tidak ditemukan di PUSTIK.","correlationId":"..."}}
```

```http
POST /backend/auth/resolve/lecturer
Content-Type: application/json

{"nik":"<nik>"}
```

```json
{"ok":false,"error":{},"message":"Identitas dosen tidak ditemukan di PUSTIK."}
```

Pesan inilah bukti langsungnya: identitas dicocokkan ke PUSTIK, bukan ke basis data lokal.

Catatan lain dari jalur yang sama:

- `GET /backend/auth/csrf` — endpoint menyediakan token CSRF; endpoint `resolve/*` menolak
  permintaan tanpa token ini (`CSRF_REJECTED`).
- `GET /backend/system/status` → `{"ok":true,"data":{"maintenance":null,"upcoming":[],...}}`.
- Prefix `/backend` dipetakan ke `/api` di balik reverse proxy. Buktinya, permintaan ke
  `/backend/docs` dijawab `Cannot GET /api/docs`.

### 2.2 Daftar resmi sumber identitas di aplikasi

Bundle JavaScript aplikasi memuat enumerasi berikut:

| Kode | Label tampilan |
| --- | --- |
| `PUSTIK_API` | "Pangkalan Data Resmi" |
| `PUSTIK_MOCK` | "Pangkalan Data Resmi (contoh)" |
| `MANUAL` | "Dibuat Manual oleh Admin" |

Artinya setiap akun mencatat asal identitasnya. Keberadaan `PUSTIK_MOCK` menandakan aplikasi
punya mode data contoh — perlu diwaspadai saat menyusun integrasi agar tidak salah arah.

### 2.3 Route internal yang mengindikasikan pengaturan integrasi

Pemetaan route hasil ekstraksi bundle memuat `/admin/integrations`, `/admin/system`, dan
`/admin/system/monitoring`. Route ini berada di balik login admin dan tidak diperiksa lebih
lanjut. Keberadaannya konsisten dengan adanya konfigurasi koneksi PUSTIK yang diatur admin.

## 3. Bentuk data identitas dari PUSTIK

Dari kode halaman register, objek `identity` hasil `resolve` memuat field berikut:

| Field | Isi |
| --- | --- |
| `npm` | Nomor Pokok Mahasiswa |
| `nik` | Nomor Induk Kepegawaian (dosen) |
| `nidn` | Nomor Induk Dosen Nasional (dosen) |
| `name` | Nama lengkap |
| `programStudy` | Program studi (objek ber-`name`, dapat pula berupa string) |
| `faculty` | Fakultas (objek ber-`name`) |
| `semester` | Semester berjalan, contoh tampil "Semester 5" |
| `cohort` | Angkatan, contoh tampil "angkatan 2023" |
| `academicStatus` | Status akademik/kepegawaian |
| `positions` | Jabatan struktural (dosen); kosong berarti "Tidak ada jabatan struktural" |

Nilai `academicStatus` yang punya label di antarmuka:

| Kode | Label |
| --- | --- |
| `ACTIVE` | Aktif |
| `LEAVE` | Sedang cuti |
| `GRADUATED` | Lulus |
| `INACTIVE` | Tidak aktif |
| `TRANSFERRED` | Pindah |
| `DROPPED_OUT` | Mengundurkan diri / berhenti |
| `RESIGNED` | Mengundurkan diri (dosen) |
| `UNVERIFIED` | Belum terverifikasi |
| `UNKNOWN` | Status belum tersedia |

Data ini lebih kaya daripada data PDDIKTI nasional — PDDIKTI tidak menyediakan semester
berjalan maupun jabatan struktural. Artinya PUSTIK membaca sistem akademik internal kampus
yang hidup, bukan snapshot PDDIKTI.

## 4. Alur register aplikasi tersebut (untuk gambaran batas akses)

```text
1. Periksa identitas   POST /backend/auth/resolve/student   {npm}
                       POST /backend/auth/resolve/lecturer  {nik}       ← PUSTIK dipanggil di sini
2. Kirim OTP WhatsApp  POST /auth/register/student/send-otp
3. Verifikasi OTP      POST /auth/register/student/verify-otp
4. Buat akun           POST /auth/register/student   (jenis kelamin, tempat/tanggal lahir,
                                                       email, nomor WhatsApp, kata sandi)
```

Data identitas hasil `resolve` disalin ke basis data aplikasi tersebut setelah OTP terverifikasi.
Jadi setelah registrasi, mereka menyimpan salinan sendiri — bukan membaca PUSTIK setiap saat.

## 5. Konsekuensi untuk proyek ini

### 5.1 Titik sambung identitas di proyek ini

| Peran | Kolom saat ini | Lokasi |
| --- | --- | --- |
| Mahasiswa | `users.npm` | `app/models.py:15` |
| Dosen | `users.employee_id` (slot NIDN) | `app/models.py:16` |
| Program studi | `study_programs.code` / `name` | `app/models.py:51-62` |

Kondisi saat ini: seluruh data master diisi manual. `seed-demo` hanya menyiapkan 15 program
studi dan satu semester aktif (`app/__init__.py:121-161`). Registrasi mahasiswa menerima NPM
apa pun tanpa verifikasi (`app/blueprints/auth.py:42-72`). Login memakai email dan password
lokal, NPM bukan kredensial (`app/blueprints/auth.py:21-39`). Proyek ini belum memiliki klien
HTTP sama sekali dan `requirements.txt` belum memuat `requests`/`httpx`.

Kesimpulannya: kolom identitasnya sudah ada, tetapi belum pernah disambungkan ke sumber mana pun.

### 5.2 Pilihan jalur integrasi

| Jalur | Cara | Catatan |
| --- | --- | --- |
| 1. Akses resmi ke PUSTIK | Ajukan permintaan API ke PUSTIK | Paling benar. PUSTIK pemilik datanya. Kemungkinan besar endpoint setara `resolve` sudah tersedia. |
| 2. PDDIKTI publik | Pakai data nasional publik | Isi lebih sedikit (tanpa semester berjalan/jabatan). Server memakai proteksi fingerprint TLS; `requests` biasa dari server dapat ditolak 403 dan butuh impersonasi TLS seperti `curl_cffi`. |
| 3. Menumpang aplikasi tersebut | Panggil `POST /backend/auth/resolve/*` miliknya | Tidak disarankan. Bergantung pada aplikasi pihak lain, tanpa jaminan layanan, dan sewaktu-waktu dapat berubah (misalnya CSRF diperketat). |

Jalur 1 perlu ditempuh lebih dahulu. Tanpa dasar pemrosesan yang sah, pengambilan data pribadi
mahasiswa berisiko secara hukum (UU Perlindungan Data Pribadi), terlepas dari mudah atau
tidaknya secara teknis.

## 6. Yang belum diketahui

- URL, format, dan skema autentikasi API PUSTIK yang sebenarnya. Tidak terlihat dari browser
  karena pemanggilan terjadi di sisi server aplikasi tersebut.
- Apakah PUSTIK menyediakan endpoint pencarian massal, sinkronisasi terjadwal, atau webhook
  perubahan data. Perlu ditanyakan langsung ke PUSTIK.
- Apakah data PUSTIK bersumber dari SIAKAD internal, PDDIKTI, atau keduanya.
- Cakupan dan retensi data pada mode `PUSTIK_MOCK`.

## 7. Langkah berikutnya bila integrasi dilanjutkan

1. Ajukan permintaan akses resmi ke PUSTIK: jelaskan kebutuhan (verifikasi identitas mahasiswa
   dan dosen pada sistem presensi), data yang diminta, dan dasar pemrosesan datanya.
2. Setelah akses tersedia, buat modul klien terpisah (misalnya `app/integrations/pustik.py`)
   dengan base URL dan kredensial di `.env`, tidak di kode.
3. Tambahkan kolom pencatat asal identitas pada `users`, mengikuti pola enumerasi aplikasi
   tersebut (`PUSTIK_API`, `MANUAL`, dan seterusnya) agar data hasil integrasi dapat dibedakan
   dari data yang diisi manual.
4. Verifikasi NPM saat registrasi mahasiswa, bukan sekadar menerima input.
5. Sediakan jalur jatuh (fallback) ke input manual bila PUSTIK tidak tersedia, supaya presensi
   tidak ikut berhenti.
6. Uji dengan salinan basis data, bukan pada data berisi.

## 8. Catatan etika

Investigasi ini hanya membaca endpoint publik pada halaman register (fitur "periksa identitas"
yang memang tersedia untuk umum), tanpa mencoba masuk ke akun siapa pun, tanpa menembus
autentikasi, dan tanpa pengambilan data massal. Data identitas mahasiswa dan dosen adalah data
pribadi; pemakaiannya di proyek ini memerlukan izin dan dasar pemrosesan dari universitas.

## Lanjutan

Rencana teknis dan status implementasi integrasi ini ada di
`docs/SPEC_REGISTER_PUSTIK.md`.
