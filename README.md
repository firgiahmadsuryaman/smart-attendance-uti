# Smart Attendance — Universitas Teknokrat Indonesia

Aplikasi prototipe sistem informasi presensi mahasiswa berbasis web dengan tiga role (Admin, Dosen, Mahasiswa), jadwal akademik terintegrasi, pendaftaran wajah, verifikasi presensi, QR/token sesi, statistik kehadiran, dan ekspor jadwal/laporan.

## Face Recognition dan pendaftaran otomatis

Pendaftaran wajah menggunakan satu sesi kamera yang merekam sampel secara otomatis. Setelah mahasiswa klik **Mulai Perekaman Otomatis**, browser mendeteksi wajah dan memandu tahap wajah depan, kedipan, tengok kiri, dan tengok kanan. Mahasiswa tidak perlu menekan tombol untuk mengambil setiap sampel. Sesudah semua challenge ditangkap, sampel dikirim ke backend untuk validasi landmark dan pembuatan Face Profile.

Saat presensi, mahasiswa masuk menggunakan QR/token lalu klik **Mulai Verifikasi Otomatis**. Kamera mengambil sampel mata terbuka dan mendeteksi kedipan. Backend tetap memvalidasi kedipan, kecocokan embedding ArcFace, status enrolmen, token/sesi, batas waktu, dan duplikasi sebelum mencatat kehadiran.

**Catatan runtime browser:** modul MediaPipe Face Mesh JavaScript dimuat dari jsDelivr, sehingga browser perlu akses internet ketika membuka halaman pendaftaran wajah/presensi. Akses kamera harus diizinkan; gunakan `localhost` atau HTTPS. OpenCV dan MediaPipe Python tetap diperlukan untuk verifikasi ulang di server. Versi di `requirements-face.txt` mengunci OpenCV 4.x agar cocok dengan jalur MediaPipe Face Mesh yang dipakai.

Kedipan dan gerakan kepala merupakan challenge liveness dasar, bukan jaminan anti-spoofing sempurna. Uji dengan kondisi kamera, pencahayaan, dan perangkat yang digunakan.

## Fitur utama

- Login dengan Flask-Login, password hashing, dan pembatasan akses berbasis role.
- Admin mengelola program studi, semester, katalog mata kuliah, kelas/penawaran, dosen, jadwal mingguan, enrolmen/KRS, Face Profile, rekap, serta log aktivitas.
- Form kelas mendukung satu sampai empat slot jadwal mingguan, sehingga kelas dapat bertemu sekali atau beberapa kali per minggu.
- Informasi kelas mencakup kode, nama mata kuliah, program studi, semester kurikulum, W/P, SKS, kelas, dosen, semester akademik, moda online/offline, ruang, dan tautan online.
- Dosen dapat memilih mata kuliah dari katalog atau menambahkan mata kuliah baru sekaligus membuat penawaran kelas dan jadwal mengajar.
- Mahasiswa memilih kelas dari penawaran yang tersedia. Setelah pengajuan disetujui, jadwal otomatis muncul di dashboard dan dapat diunduh sebagai PDF atau Excel.
- Sesi presensi menampilkan QR untuk ponsel dan kode token untuk laptop/komputer.
- Dosen mengatur durasi presensi normal dan toleransi keterlambatan. Batas waktu dihitung sejak tombol Buka Sesi ditekan.
- Presensi memvalidasi status akun, Face Profile, enrolmen APPROVED, token, sesi, waktu, dan presensi ganda.
- Statistik kehadiran dosen dapat difilter berdasarkan hari, bulan, semester, dan kelas; laporan dapat diekspor sebagai PDF/Excel dengan identitas visual universitas.
- Pendaftaran wajah meminta sampel depan, kedipan, dan gerakan kepala kiri/kanan. Presensi meminta sampel mata terbuka dan kedipan.
- Aset logo Universitas Teknokrat Indonesia dan foto kampus tersedia pada `app/static/images/`.

## Keterbatasan penting

Challenge kedipan/gerak kepala pada versi ini menggunakan sampel frame statis dan pemeriksaan landmark, sehingga merupakan **liveness dasar** dan bukan sistem anti-spoofing kelas produksi. Video replay atau serangan yang lebih canggih masih mungkin melewati challenge sederhana. Kalibrasi threshold model dan pengujian pada perangkat/pencahayaan sebenarnya masih dibutuhkan. Jangan memakai data wajah mahasiswa sungguhan tanpa persetujuan, dasar pemrosesan, dan kebijakan perlindungan data yang sesuai.

QR hanya membuka alamat aplikasi. Untuk membuka kamera dari ponsel, browser umumnya memerlukan konteks aman HTTPS (kecuali localhost pada perangkat yang sama). Akses HTTP melalui IP LAN bisa membuka halaman, tetapi akses kamera dapat diblokir. Gunakan HTTPS yang sesuai untuk demo lintas perangkat.

Aplikasi belum terhubung ke sistem akademik resmi Universitas Teknokrat Indonesia. Data mata kuliah, dosen, jadwal, dan peserta dimasukkan lewat sistem ini.

## Kebutuhan

- Windows 10/11 atau Linux
- Python 3.10 disarankan
- Browser modern
- SQLite untuk uji awal atau MySQL/XAMPP untuk lingkungan tim
- Webcam/kamera browser untuk pengujian face enrollment dan presensi

## Instalasi Windows (SQLite, jalur termudah)

1. Ekstrak ZIP ke folder sederhana, misalnya `C:\Projects\smart_attendance`.
2. Buka CMD di folder tersebut.
3. Jalankan:

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

4. Edit `.env` dan ubah `SECRET_KEY` menjadi nilai acak yang kuat. `APP_BASE_URL` dapat dibiarkan kosong untuk mengikuti host pada request; atur bila perlu alamat QR tertentu.
5. Siapkan database dan data akademik demo:

```bat
python -m flask --app run.py init-db
python -m flask --app run.py seed-demo
python -m flask --app run.py create-admin
```

`create-admin` akan meminta nama, email, dan password admin melalui terminal.

6. Jalankan:

```bat
python run.py
```

7. Buka `http://127.0.0.1:5000` dan masuk menggunakan akun Admin yang dibuat.

## Instalasi Linux (venv lokal)

Gunakan Python 3.10 hingga 3.12. Rentang ini penting bila nanti memakai Face Recognition:
`mediapipe==0.10.35` pada `requirements-face.txt` belum menyediakan wheel untuk Python 3.13
ke atas. Bila distribusi Anda hanya menyediakan Python yang lebih baru, `uv` dapat mengambil
interpreter 3.12 terpisah tanpa mengubah Python sistem.

1. Siapkan virtual environment. Pilih salah satu:

```bash
# Bila python3.12 sudah tersedia di sistem
python3.12 -m venv .venv

# Bila belum tersedia, unduh interpreter terpisah memakai uv
uv venv --python 3.12 .venv
```

2. Aktifkan dan pasang dependensi:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements-dev.txt` memuat `requirements.txt` ditambah `pytest`. Bila uv tersedia,
`uv pip install -r requirements-dev.txt` jauh lebih cepat.

3. Siapkan konfigurasi dan basis data:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # salin hasilnya ke SECRET_KEY
python -m flask --app run.py init-db
python -m flask --app run.py seed-demo
python -m flask --app run.py create-admin
```

`create-admin` meminta nama, email, dan password melalui terminal. Untuk pengisian otomatis
pada lingkungan pengujian, alirkan jawabannya ke stdin:

```bash
printf 'Nama Admin\nadmin@teknokrat.ac.id\npassword-anda\npassword-anda\n' \
  | python -m flask --app run.py create-admin
```

4. Jalankan dan buka `http://127.0.0.1:5000`:

```bash
python run.py
```

Atur `FLASK_DEBUG=1` di `.env` agar server memuat ulang otomatis saat berkas berubah. Mode ini
hanya untuk pengembangan lokal; jangan diaktifkan di server yang dapat diakses publik.

5. Jalankan pengujian:

```bash
python -m pytest tests/ -q
```

Memeriksa kesesuaian skema basis data dengan model setelah kode berubah:

```bash
python -m flask --app run.py check-schema
python -m flask --app run.py routes      # daftar seluruh route dan endpoint
```

## Menggunakan MySQL / XAMPP

1. Jalankan MySQL melalui XAMPP.
2. Buat database `smart_attendance` di phpMyAdmin.
3. Edit `.env` dan set `DATABASE_URL`. Jika XAMPP menggunakan port `3307`:

```env
DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3307/smart_attendance?charset=utf8mb4
```

Jika MySQL berjalan pada port `3306`, gunakan `3306` pada URL. Pastikan nama database, user, password, dan port sesuai. Jangan menganggap MySQL pasti menggunakan port default.

Jalankan perintah `init-db`, `seed-demo`, dan `create-admin` seperti di atas setelah koneksi database benar.

**Penting:** `init-db` menggunakan `db.create_all()` untuk database baru dan tidak memigrasikan kolom tabel yang sudah ada. Sebelum mengubah database existing, buat backup. Jika memakai instalasi lama, gunakan Flask-Migrate/Alembic untuk membuat dan menjalankan migrasi setelah meninjau perubahan yang dihasilkan.

## QR dan akses ponsel

- QR mengarah ke URL yang tersimpan dalam konfigurasi `APP_BASE_URL`, atau host aplikasi pada request jika nilainya kosong.
- Jangan isi `127.0.0.1` jika QR akan dipindai ponsel: alamat itu menunjuk ke ponsel sendiri, bukan laptop/server.
- Untuk akses di jaringan lokal, jalankan dengan `FLASK_HOST=0.0.0.0`, cari IP LAN laptop, dan gunakan alamat itu sebagai `APP_BASE_URL`. Pastikan firewall mengizinkan port aplikasi.
- Browser ponsel dapat mensyaratkan HTTPS untuk kamera. Untuk pengujian ponsel, gunakan lingkungan HTTPS yang aman. Di localhost pada komputer yang sama, izin kamera umumnya dapat digunakan.

Contoh `.env` untuk jaringan lokal (ganti IP sesuai IP laptop dan gunakan HTTPS untuk kamera ponsel jika diminta browser):

```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
APP_BASE_URL=http://192.168.1.10:5000
```

## Instalasi Face Recognition dan challenge

Setelah versi web biasa dan database berjalan, aktifkan virtual environment yang sama dengan yang dipakai `python run.py`.

Jika sebelumnya OpenCV 5.x terpasang, bersihkan paket OpenCV yang saling berbagi modul `cv2` lebih dahulu:

```bat
.venv\Scripts\activate
python -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
python -m pip install -r requirements-face.txt
```

Versi OpenCV dipatok pada 4.11.0.86 dan MediaPipe pada 0.10.35 untuk menjaga kompatibilitas jalur Face Mesh yang digunakan prototipe ini. DeepFace memakai ArcFace untuk membuat embedding; OpenCV/MediaPipe digunakan untuk memeriksa landmark liveness. Instalasi pertama dapat mengunduh bobot model; pastikan koneksi internet dan ruang disk cukup.

Sebelum membuka kamera di browser, uji runtime Face Mesh dari root proyek:

```bat
python scripts/check_face_runtime.py
```

Tes ini memakai gambar kosong untuk memastikan graph Face Mesh berhasil dimuat; hasil wajah terdeteksi harus nol. Tes ini tidak menguji kamera atau membuktikan liveness pada wajah pengguna. Jika gagal, simpan output lengkap untuk diagnosis.

Pengaturan di `.env`:

```env
FACE_MODEL=ArcFace
FACE_DETECTOR_BACKEND=opencv
FACE_MATCH_THRESHOLD=0.35
```

Threshold `0.35` hanyalah nilai awal prototipe, bukan standar universal. Lakukan evaluasi false accept/false reject dan kalibrasi pada perangkat, cahaya, dan sampel yang diizinkan.

### Challenge pendaftaran wajah

1. Sampel wajah depan dengan mata terbuka.
2. Sampel saat berkedip.
3. Sampel menoleh ke kiri.
4. Sampel menoleh ke kanan.

Backend memeriksa landmark dan perbedaan yang diharapkan sebelum menyimpan embedding. Challenge ini membantu mencegah penggunaan foto statis sederhana, tetapi bukan jaminan anti-spoofing mutlak.

### Challenge saat presensi

Mahasiswa membuka sesi melalui QR/token, mengambil sampel mata terbuka dan saat berkedip, lalu backend memeriksa challenge, mencocokkan embedding ArcFace, memvalidasi enrolmen APPROVED, jendela waktu, sesi, dan duplikasi.

## Alur data akademik

1. Admin menyiapkan semester dan daftar program studi.
2. Admin atau dosen membuat/memilih mata kuliah dan membuka penawaran kelas.
3. Penawaran memuat semester, kelas, dosen, moda perkuliahan, dan satu atau beberapa slot jadwal mingguan.
4. Mahasiswa mendaftar menggunakan NPM, nama, email, program studi, password, dan angkatan opsional. Form tidak meminta kelas, nomor HP, atau wajah.
5. Setelah login, mahasiswa mendaftarkan wajah dari dashboard.
6. Mahasiswa memilih kelas yang dibuka untuk program studi dan semester aktifnya.
7. Admin menyetujui/menolak pengajuan jika alur persetujuan diaktifkan. Hanya enrolmen `APPROVED` yang membentuk jadwal resmi dan memberikan hak presensi.
8. Mahasiswa melihat jadwal mingguan dan mengunduh PDF/Excel.
9. Dosen membuka sesi; QR/token tersedia selama sesi. Durasi hadir normal dan toleransi dihitung relatif terhadap waktu ketika tombol dibuka.
10. Sesi ditutup oleh dosen, atau ditandai tutup saat ada permintaan terautentikasi setelah `closes_at` terlewati. Peserta approved yang belum memiliki catatan dibuatkan `ABSENT`.

## Verifikasi identitas mahasiswa dan dosen

Pendaftaran akun memverifikasi NPM (mahasiswa) atau NIK (dosen) ke sumber identitas sebelum
akun dibuat. Nama, program studi, dan angkatan diambil dari sumber itu — tidak diketik oleh
pendaftar, dan nilai yang dikirim lewat form tidak dipercaya.

Sumber identitas diatur lewat `.env`:

```env
IDENTITY_PROVIDER=sample        # sample (data contoh) atau pustik (data resmi kampus)
PUSTIK_BASE_URL=
PUSTIK_API_KEY=
PUSTIK_TIMEOUT=8
IDENTITY_CHECK_RATE_LIMIT=10
```

Dengan `IDENTITY_PROVIDER=sample`, halaman register menampilkan lencana **"Mode data contoh"**
dan server menulis peringatan di log. Data contoh hanya untuk pengembangan; jangan dipakai
untuk data mahasiswa sungguhan.

Akun data contoh yang dapat dipakai menguji:

| Identifier | Jenis | Keadaan |
| --- | --- | --- |
| `23312001` | NPM | Informatika, semester 5, angkatan 2023, aktif |
| `23312002` | NPM | Informatika, status Lulus — pendaftaran ditolak |
| `23312003` | NPM | Program studi tidak terdaftar — pendaftaran ditolak |
| `0012345678` | NIK | Dosen Informatika, aktif |
| `99999999` | keduanya | Menyimulasikan gangguan pada sumber identitas |

Provider `pustik` belum boleh diarahkan ke server PUSTIK sungguhan sampai kontrak resminya
dikonfirmasi. Pemetaan responsnya masih berdasarkan dugaan; lihat
`docs/SPEC_REGISTER_PUSTIK.md` bagian 4.5.

### Perubahan skema setelah migrasi diaktifkan

Database tidak lagi disiapkan dengan `init-db` untuk perubahan lanjutan. Repositori saat ini
memiliki dua revisi migrasi: revisi dasar skema awal (`b3af04b5297f`) dan penambahan kolom
identitas (`8f09cae67180`), sehingga instalasi baru dapat langsung memakai `flask db upgrade`.
Perintah di bawah mengasumsikan virtual environment sudah aktif. Setelah mengubah model:

```bash
python -m flask --app run.py db migrate -m "keterangan perubahan"
python -m flask --app run.py db upgrade
python -m flask --app run.py check-schema
```

Untuk database baru, `flask db upgrade` adalah jalur yang digunakan; `init-db` tetap tersedia untuk database kosong, tetapi tidak mencatat revisi migrasi.

## Menu menurut role

### Admin
- Dashboard
- Program Studi
- Semester Akademik
- Katalog Mata Kuliah
- Kelas & Jadwal
- Data Dosen dan Mahasiswa
- Persetujuan Pengambilan Mata Kuliah
- Rekap Presensi
- Monitoring Face Profile
- Pengaturan
- Log Aktivitas

### Dosen
- Dashboard
- Input Mata Kuliah/Kelas yang Diajar
- Kelas yang Diampu
- Jadwal Mengajar dan ekspor PDF/Excel
- Buka Sesi Presensi (QR dan token)
- Monitoring Presensi
- Statistik harian, bulanan, semester dan ekspor PDF/Excel
- Koreksi presensi dengan alasan dan jejak audit

### Mahasiswa
- Registrasi/Login
- Dashboard
- Daftarkan Wajah
- Mata Kuliah Saya / ajukan kelas
- Jadwal semester otomatis
- Unduh PDF/Excel
- Presensi melalui QR/token dan verifikasi wajah
- Riwayat dan rekap kehadiran
- Notifikasi dan Profil

## Pemeriksaan sebelum demo

1. Buat Admin, jalankan aplikasi, dan login.
2. Pastikan 15 program studi tersedia setelah `seed-demo`.
3. Buat akun dosen, lalu dosen membuat penawaran kelas dengan dua slot jadwal pada minggu yang sama.
4. Buat akun mahasiswa dengan program studi sama; mahasiswa mengajukan kelas.
5. Admin menyetujui pengajuan dan periksa bahwa jadwal muncul di dashboard mahasiswa.
6. Unduh PDF/Excel mahasiswa dan PDF/Excel jadwal dosen.
7. Dosen membuka sesi dan cek QR serta kode token.
8. Tes akses token salah, kelas yang tidak diikuti, sesi kedaluwarsa, presensi ganda, dan enrolmen belum approved.
9. Instal requirements-face dan uji pendaftaran wajah dengan sampel yang disetujui.
10. Tes proses akhir sesi dan statistik harian/bulanan/semester.

## Struktur proyek

```text
smart_attendance/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── utils.py
│   ├── face_engine.py
│   ├── blueprints/
│   ├── templates/
│   └── static/
├── docs/
├── tests/
├── requirements.txt
├── requirements-face.txt
├── .env.example
├── run.py
└── README.md
```

## Troubleshooting: Internal Server Error (HTTP 500)

Jika halaman dashboard, Admin, Dosen, atau Mahasiswa menampilkan HTTP 500 setelah source code diperbarui:

1. Periksa jendela CMD tempat `python run.py` berjalan. Traceback pada terminal menunjukkan penyebab sebenarnya; halaman browser sengaja tidak menampilkan detail sensitif.
2. Jalankan pemeriksaan struktur database:

```bat
python -m flask --app run.py check-schema
```

3. Jika perintah melaporkan tabel atau kolom yang hilang, jangan menghapus database secara langsung. Buat backup terlebih dahulu. Perintah `init-db` hanya membuat tabel yang belum ada dan tidak menambahkan kolom yang hilang ke tabel lama.
4. Untuk database SQLite pengembangan tanpa data yang perlu dipertahankan, cara paling bersih adalah menghentikan server dan mengganti nama `instance/smart_attendance.db` menjadi file backup, kemudian menjalankan `init-db`, `seed-demo`, dan `create-admin`. Jangan lakukan ini pada database berisi data penting.
5. Untuk MySQL/XAMPP atau database yang berisi data, lakukan migrasi terkontrol setelah meninjau perbedaan skema. Pastikan `.env` menunjuk ke database dan port yang benar.
6. Jika `check-schema` menyatakan skema sesuai tetapi halaman masih error, salin traceback lengkap yang muncul di CMD setelah membuka halaman yang gagal. Jangan kirim password atau nilai secret dari `.env`.

Perbaikan pada versi ini juga menambahkan route halaman `/student/face-enrollment`, yang diperlukan oleh tautan pada sidebar dan dashboard mahasiswa.
