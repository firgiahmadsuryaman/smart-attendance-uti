# Spec: Integrasi Identitas PUSTIK & Halaman Register Baru

Tanggal: 17 Oktober 2026
Status: menunggu peninjauan sebelum disusun rencana implementasi

Dokumen ini merinci rencana teknis untuk dua hal yang diminta sekaligus:

1. Modul integrasi identitas ke PUSTIK (Universitas Teknokrat Indonesia).
2. Halaman register baru bergaya `https://agent.teknokrat.ac.id/auth/register`, disesuaikan
   dengan tampilan Smart Attendance.

Latar belakang temuan tentang sumber data PUSTIK ada di `docs/INTEGRASI_PUSTIK.md`. Dokumen ini
tidak mengulang pembuktiannya.

---

## 1. Tujuan

Mahasiswa dan dosen mendaftar dengan NPM atau NIK yang diverifikasi ke data akademik resmi,
sehingga identitas di sistem presensi tidak lagi diisi bebas dan dapat dipertanggungjawabkan.
Nama, program studi, dan angkatan berasal dari sumber resmi, bukan dari ketikan pendaftar.

Ukuran keberhasilan:

- Pendaftaran dengan NPM/NIK yang tidak ada di PUSTIK ditolak, dengan pesan yang membedakan
  "tidak ditemukan" dan "sistem sedang gangguan".
- Identitas yang tersimpan berasal dari provider, bukan dari isian form.
- Seluruh alur dapat dijalankan dan diuji sekarang, tanpa menunggu kredensial PUSTIK turun.
- Menukar provider contoh menjadi provider HTTP PUSTIK hanya mengubah konfigurasi `.env`,
  tanpa mengubah kode halaman register.

## 2. Keputusan yang sudah disepakati

| Topik | Keputusan |
| --- | --- |
| Kontrak PUSTIK | Belum tersedia. Dibangun dengan provider yang bisa ditukar plus provider data contoh |
| OTP WhatsApp | Dilewati pada iterasi ini |
| Pendaftaran dosen | Dosen boleh mendaftar sendiri lewat NIK; verifikasi NIK wajib, tidak boleh dilewati |
| Identitas tidak ditemukan | Pendaftaran diblokir, dengan pesan dibedakan dari gangguan sistem |
| Perubahan skema | Flask-Migrate diaktifkan dan revisi pertama dibuat |
| Pembatas laju | Dipasang pada endpoint pemeriksaan identitas |
| Tombol Cek | Berbasis AJAX, dengan respons berupa potongan HTML dari satu partial Jinja |

## 3. Ruang lingkup

**Termasuk:**

- Paket `app/integrations/` berisi kontrak provider, provider data contoh, dan provider HTTP.
- Penambahan kolom `identity_source` dan `nidn` pada tabel `users`, beserta migrasinya.
- Halaman register dua tab dengan pemeriksaan identitas, kartu konfirmasi, dan form akun.
- Pembatas laju untuk endpoint pemeriksaan identitas.

**Tidak termasuk:**

- Sinkronisasi mata kuliah, jadwal, kelas, dan KRS. Kebutuhan itu terpisah dan belum punya
  endpoint di PUSTIK.
- OTP WhatsApp atau verifikasi email.
- Pengumpulan jenis kelamin, tempat lahir, dan tanggal lahir. Model data proyek ini tidak
  menyimpannya, sehingga menambah kolom hanya akan menghasilkan kolom mati.
- Pembuatan akun mahasiswa manual oleh admin.
- Penghapusan atau penonaktifan akun yang sudah ada.

## 4. Arsitektur modul integrasi

```
app/integrations/
├── __init__.py    # pabrik provider, membaca konfigurasi aplikasi
├── base.py        # IdentityProvider (ABC), Identity (dataclass), kelas galat
├── sample.py      # SampleIdentityProvider — data contoh lokal
└── pustik.py      # PustikIdentityProvider — klien HTTP
```

Aturan ketergantungan: `base.py` tidak mengimpor Flask maupun model database. Paket ini tidak
boleh menyentuh `db.session`. Pemetaan identitas ke baris `User` dilakukan di blueprint
`auth.py`, bukan di paket integrasi. Dengan pemisahan ini, provider dapat diuji tanpa
menjalankan aplikasi dan tanpa database.

### 4.1 Kontrak provider

```python
@dataclass(frozen=True)
class Identity:
    kind: str                      # "student" | "lecturer"
    identifier: str                # NPM untuk mahasiswa, NIK untuk dosen
    name: str
    program_name: str | None
    program_code: str | None
    faculty: str | None
    semester: int | None
    cohort: str | None
    academic_status: str           # ACTIVE, LEAVE, GRADUATED, ...
    nidn: str | None = None
    positions: tuple[str, ...] = ()


class IdentityProvider(ABC):
    source_code: str               # "PUSTIK_API" | "SAMPLE"

    def resolve_student(self, npm: str) -> Identity: ...
    def resolve_lecturer(self, nik: str) -> Identity: ...
```

Bentuk ini netral terhadap cara PUSTIK mengemas datanya. Pemetaan dari respons PUSTIK ke
`Identity` hanya ada di `pustik.py`.

`program_code` dipakai lebih dulu saat mencocokkan program studi ke tabel lokal, karena kode
lebih stabil daripada nama.

### 4.2 Taksonomi galat

```python
class IdentityError(Exception):
    user_message: str   # pesan siap tampil, tanpa detail internal

class IdentityNotFound(IdentityError): ...      # identifier tidak ada di sumber
class ProviderUnavailable(IdentityError): ...   # jaringan, timeout, atau status 5xx
class ProviderMisconfigured(IdentityError): ... # konfigurasi kosong atau tidak valid
class ProgramNotRegistered(IdentityError): ...  # identitas ada, program studi tidak ada di lokal
class IdentityNotActive(IdentityError): ...     # status akademik bukan ACTIVE
```

`ProgramNotRegistered` dan `IdentityNotActive` bukan kegagalan provider — identitasnya berhasil
diambil, tetapi tidak memenuhi syarat. Keduanya tetap turunan `IdentityError` supaya pemanggil
punya satu jalur penanganan.

### 4.3 Pabrik provider

```python
def get_identity_provider() -> IdentityProvider
```

Membaca `current_app.config["IDENTITY_PROVIDER"]` dan menyimpan instance di
`current_app.extensions["identity_provider"]` supaya sesi HTTP tidak dibuat ulang setiap
permintaan. Nilai yang tidak dikenal dianggap galat konfigurasi, bukan diam-diam jatuh ke
provider contoh.

### 4.4 Provider data contoh

`SampleIdentityProvider` memakai data tetap di dalam modul (`SAMPLE_STUDENTS`,
`SAMPLE_LECTURERS`), mengikuti kebiasaan `seed-demo` yang juga menaruh data tetap di dalam
kode. Isi minimalnya:

| NPM / NIK | Keadaan | Gunanya |
| --- | --- | --- |
| `23312001` | mahasiswa Informatika, semester 5, angkatan 2023, ACTIVE | jalur berhasil |
| `23312002` | mahasiswa Informatika, status GRADUATED | menguji penolakan status |
| `23312003` | mahasiswa prodi "Teknik Robotika" yang tidak ada di tabel lokal | menguji ProgramNotRegistered |
| `0012345678` | dosen Informatika, ACTIVE, punya NIDN dan jabatan struktural | jalur berhasil dosen |
| `99999999` | memicu `ProviderUnavailable` | menguji pesan gangguan sistem secara manual |

Nama program studi pada data contoh wajib sama dengan daftar di `seed-demo`
(`app/__init__.py:128-144`) supaya pendaftaran berhasil tanpa penyiapan tambahan. Hal ini
diuji secara otomatis, bukan sekadar didokumentasikan.

Satu pengecualian: entri `23312003` sengaja memakai program studi yang tidak ada di tabel lokal
supaya jalur `ProgramNotRegistered` bisa diuji. Entri ini ditandai eksplisit di dalam kode
(misalnya lewat penanda `expects_unregistered_program=True`), sehingga aturan "program studi
data contoh harus ada di seed" tetap dapat diuji untuk seluruh entri lain tanpa mengorbankan
kasus negatif ini.

### 4.5 Provider HTTP PUSTIK

`PustikIdentityProvider` menerima fungsi transport yang dapat disuntikkan:

```python
class PustikIdentityProvider(IdentityProvider):
    def __init__(self, base_url, api_key, timeout, transport=None): ...
```

Transport bawaan memakai `requests`. Pengujian menyuntikkan transport palsu, sehingga tidak
perlu dependensi tambahan seperti `requests_mock` dan tidak ada permintaan jaringan saat tes.

Perilaku yang wajib:

- `base_url` kosong → `ProviderMisconfigured` saat dipakai.
- Timeout, kegagalan koneksi, dan status 5xx → `ProviderUnavailable`.
- Status 404, atau 200 dengan penanda "tidak ditemukan" → `IdentityNotFound`.
- Respons yang tidak dapat dipetakan → `ProviderUnavailable`, bukan crash tak tertangani.
- Seluruh detail teknis masuk log server lewat `app.logger`. Pesan ke pengguna hanya
  `user_message`.

Catatan penting dan jujur: kontrak PUSTIK yang sebenarnya belum diketahui. `_map_response()`
ditulis berdasarkan dugaan bentuk (`npm`/`nik`, `name`, `programStudy.name`, `faculty`,
`semester`, `cohort`, `academicStatus`, `nidn`, `positions`) yang berasal dari temuan di
`docs/INTEGRASI_PUSTIK.md`. Provider ini **belum boleh diarahkan ke PUSTIK sungguhan** sebelum
kontraknya dikonfirmasi. Yang dijamin oleh desain ini adalah bentuk keluaran `Identity` dan
penanganan galatnya, bukan kecocokan pemetaan field.

### 4.6 Konfigurasi

`.env.example` dan `.env` mendapat kunci berikut:

```
IDENTITY_PROVIDER=sample        # sample | pustik
PUSTIK_BASE_URL=
PUSTIK_API_KEY=
PUSTIK_TIMEOUT=8
IDENTITY_CHECK_RATE_LIMIT=10    # jumlah pemeriksaan identitas per menit per alamat IP
```

Nilai bawaan `IDENTITY_PROVIDER` adalah `sample`.

`IDENTITY_CHECK_RATE_LIMIT` sengaja dibuat dapat dikonfigurasi, bukan angka tetap di dalam
kode. Alasannya bukan keluwesan demi keluwesan: pengujian otomatis menjalankan banyak
pemeriksaan dari satu alamat IP yang sama dalam waktu singkat, sehingga batas yang dipatok mati
akan membuat tes saling merusak. Tes yang menguji pembatasan menurunkannya, tes lain
menaikkannya. Nilai `0` berarti tanpa pembatas.

Selama provider contoh aktif:

- Halaman register menampilkan lencana **"Mode data contoh"** yang terlihat.
- Server menulis peringatan di log saat aplikasi dibuat.

Peringatan ini disengaja sebagai pengaman lunak. Memblokir keras provider contoh ditolak karena
akan menghalangi pengembangan lokal, yang justru tujuan iterasi ini.

## 5. Perubahan basis data dan migrasi

Kolom baru pada `users`:

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `identity_source` | `String(20)`, nullable | `PUSTIK_API`, `SAMPLE`, atau `MANUAL`. NULL pada baris lama berarti MANUAL |
| `nidn` | `String(30)`, nullable | NIDN dosen, terpisah dari `employee_id` yang menyimpan NIK |

Kolom yang sudah ada dan dipakai: `npm` (mahasiswa), `employee_id` (NIK dosen), `program_id`,
`cohort`, `full_name`, `email`, `role`, `active`, `password_hash`.

**Migrasi.** Flask-Migrate sudah terpasang di `app/extensions.py` dan sudah diinisialisasi di
`app/__init__.py:31`, tetapi folder `migrations/` belum pernah dibuat. Langkahnya:

1. `flask db init` untuk membuat folder `migrations/`.
2. `flask db migrate -m "tambah identity_source dan nidn pada users"` untuk membuat revisi awal.
3. Tinjau berkas revisi yang dihasilkan. Revisi awal pada database yang sudah berisi tabel akan
   memuat seluruh tabel, bukan hanya dua kolom baru. Pastikan tidak ada operasi `drop` yang
   tidak disengaja sebelum menjalankannya.
4. `flask db upgrade`.

Database pengembangan saat ini berisi satu akun admin dan 15 program studi hasil `seed-demo`.
Migrasi harus mempertahankan keduanya. Setelah upgrade, jalankan
`flask --app run.py check-schema` dan pastikan hasilnya `OK`.

Mulai titik ini, setiap perubahan kolom memakai `flask db migrate` + `flask db upgrade`, bukan
`init-db`. Perintah `init-db` tetap ada untuk database kosong.

## 6. Alur register

### 6.1 Route

| Route | Metode | Fungsi |
| --- | --- | --- |
| `/register` | GET | Halaman register. Parameter `jenis` berisi `mahasiswa` (bawaan) atau `dosen` |
| `/register/check` | POST | Memeriksa identitas. Mengembalikan potongan HTML |
| `/register/student` | POST | Membuat akun mahasiswa |
| `/register/lecturer` | POST | Membuat akun dosen |

### 6.2 Prinsip keamanan yang tidak boleh dilanggar

**Server tidak pernah menerima nama, program studi, atau angkatan dari form.** Form hanya
mengirim identifier, email, dan kata sandi. Saat pembuatan akun, server memanggil provider
sekali lagi dan membangun akun dari hasil panggilan itu. Konsekuensinya:

- Menyisipkan `full_name` atau `program_id` palsu ke dalam POST tidak berpengaruh apa pun.
- Tombol "Cek" murni urusan tampilan. Identitas yang ditampilkan di kartu tidak dipercaya
  sebagai bukti.
- Identitas yang tidak valid saat pembuatan akun ditolak, walaupun pemeriksaan sebelumnya
  berhasil.

Ada pengujian khusus untuk memastikan `full_name` palsu pada POST diabaikan.

### 6.3 Validasi

| Aturan | Perilaku bila gagal |
| --- | --- |
| Identifier 4–20 karakter, hanya angka | "NPM/NIK tidak valid." |
| Email berformat sah | "Masukkan alamat email yang valid." |
| Email belum terdaftar | "Email sudah terdaftar. Silakan masuk." |
| Kata sandi minimal 8 karakter | "Password minimal 8 karakter." |
| Konfirmasi kata sandi cocok | "Konfirmasi kata sandi tidak cocok." |
| `npm` belum terdaftar (mahasiswa) | "NPM sudah terdaftar. Silakan masuk." |
| `employee_id` belum terdaftar (dosen) | "NIK sudah terdaftar. Silakan masuk." |

Pembatasan "hanya angka" dipilih karena NPM dan NIK di lingkungan ini berupa angka. Bila
ternyata ada NPM yang mengandung huruf, aturan ini yang pertama harus dilonggarkan.

### 6.4 Pemetaan program studi

Urutan pencocokan dari hasil identitas ke `study_programs`:

1. `program_code` (tanpa membedakan huruf besar/kecil).
2. `program_name` yang dinormalisasi: huruf kecil, spasi ganda disatukan, tanda baca dibuang.

Bila keduanya tidak menghasilkan kecocokan → `ProgramNotRegistered`, pendaftaran ditolak dengan
"Program studi Anda belum terdaftar di sistem. Hubungi administrator."

Program studi **tidak** dibuat otomatis dari data luar. Mengubah data master tanpa peninjauan
admin bukan hal yang pantas dilakukan modul integrasi. Admin menambahkannya lewat
`/admin/programs` yang sudah ada.

### 6.5 Kebijakan status akademik

Hanya `ACTIVE` yang boleh mendaftar.

| Status | Hasil |
| --- | --- |
| `ACTIVE` | Didaftarkan |
| `LEAVE` | Ditolak: "Status akademik Anda sedang cuti." |
| `GRADUATED` | Ditolak: "Status akademik Anda sudah lulus." |
| `DROPPED_OUT`, `RESIGNED`, `TRANSFERRED` | Ditolak: status ditampilkan apa adanya |
| `UNVERIFIED`, `UNKNOWN` | Ditolak: "Status akademik Anda belum dapat diverifikasi." |

Untuk dosen, `academic_status` dibaca sebagai status kepegawaian. Aturannya sama: hanya yang
aktif yang boleh mendaftar.

### 6.6 Field yang dibangun saat akun dibuat

| Field `users` | Mahasiswa | Dosen |
| --- | --- | --- |
| `role` | `student` | `lecturer` |
| `npm` | NPM | NULL |
| `employee_id` | NULL | NIK |
| `nidn` | NULL | NIDN |
| `full_name` | dari provider | dari provider |
| `program_id` | hasil pemetaan | hasil pemetaan |
| `cohort` | dari provider | dari provider |
| `email` | dari form | dari form |
| `password_hash` | dari form | dari form |
| `identity_source` | `provider.source_code` | `provider.source_code` |
| `active` | `True` | `True` |

`positions` (jabatan struktural) hanya ditampilkan di kartu konfirmasi. Tidak ada kolomnya, dan
tidak ditambahkan.

### 6.7 Pembatas laju

Endpoint `/register/check` dapat dipakai menyapu NPM berurutan untuk memanen nama dan program
studi. Pembatasnya:

- Maksimal `IDENTITY_CHECK_RATE_LIMIT` pemeriksaan per menit per alamat IP, bawaan 10.
  Kelebihan → "Terlalu banyak pemeriksaan. Tunggu sebentar."
- Kunci memakai `request.remote_addr`, **bukan** header `X-Forwarded-For`, karena header itu
  dapat dipalsukan oleh klien. Ini berbeda dari `log_action()` yang memang memakai
  `X-Forwarded-For` untuk keperluan catatan.
- Penyimpanan di memori proses dengan penguncian thread. Ditempatkan di `app/utils.py` sebagai
  fungsi `check_rate_limit()` dan `reset_rate_limit()`.
- `reset_rate_limit()` ada bukan untuk kelengkapan, melainkan karena hitungannya hidup di
  tingkat modul dan akan terbawa dari satu tes ke tes berikutnya. Fixture pengujian memanggilnya
  sebelum setiap tes.
- Batasnya berlaku juga untuk pemeriksaan yang gagal, karena percobaan gagal tetap membocorkan
  informasi.
- Nilai `IDENTITY_CHECK_RATE_LIMIT = 0` mematikan pembatas.

Batas yang diketahui: hitungan hilang saat proses dimulai ulang dan tidak dibagi antar-worker.
Untuk satu proses pengembangan hal ini memadai. Bila nanti dijalankan dengan beberapa worker,
pembatasnya perlu dipindah ke penyimpanan bersama.

## 7. Tampilan halaman register

### 7.1 Tata letak

Tata letak dua kolom yang sudah ada dipertahankan: hero navy dengan foto kampus dan daftar
langkah di kiri, panel form di kanan pada halaman yang sama-sama dipakai login. Halaman
referensi yang satu kolom minimalis **tidak** ditiru, supaya login dan register tetap terasa
satu keluarga. Yang diadopsi dari referensi adalah perilakunya, bukan gaya visualnya.

### 7.2 Isi panel kanan

1. **Toggle dua tab** — Mahasiswa dan Dosen. Berbentuk pill di dalam wadah abu membulat, tab
   aktif berlatar putih berteks biru. Tab berupa tautan ke `/register?jenis=...` sehingga tetap
   berfungsi tanpa JavaScript, lalu ditingkatkan oleh JS menjadi perpindahan tanpa muat ulang.
   Memakai `role="tablist"` dan `role="tab"` dengan `aria-selected`.
   Kedua panel selalu ada di dalam DOM; panel yang tidak aktif diberi atribut `hidden` oleh
   server berdasarkan `jenis`. Berganti tab mengosongkan kembali hasil pemeriksaan sebelumnya.
2. **Baris pemeriksaan identitas** — input NPM/NIK berikon di kiri, tombol "Cek" berbentuk pil
   di kanan. Tombol nonaktif selama input kosong. Label, placeholder, dan nama field berubah
   sesuai tab (`npm` untuk mahasiswa, `nik` untuk dosen).
3. **Kartu konfirmasi identitas** — muncul setelah pemeriksaan berhasil, memuat nama, nomor
   identitas, program studi, fakultas, semester, angkatan, dan lencana status. Untuk dosen
   ditambah NIDN dan jabatan struktural. Memakai kembali `.status-pill` dan `.detail-item` yang
   sudah ada.
4. **Form akun** — email, kata sandi, dan konfirmasi kata sandi. Muncul setelah identitas
   terkonfirmasi.
5. **Lencana "Mode data contoh"** saat provider contoh aktif.

### 7.3 Respons endpoint pemeriksaan

`/register/check` mengembalikan **potongan HTML** (`text/html`), bukan JSON:

- Berhasil → HTML dari partial `app/templates/auth/_identity_card.html`.
- Gagal → HTML dari partial `app/templates/auth/_identity_error.html`.

Alasannya: kartu identitas hanya boleh hidup di satu berkas. Bila endpoint mengembalikan JSON,
markup kartu harus ditulis dua kali — sekali di Jinja dan sekali lagi sebagai template di JS —
dan keduanya bisa berbeda diam-diam tanpa ada yang tahu. Dengan partial yang sama dipakai ulang
saat halaman dirender ulang setelah galat validasi, tidak ada markup kembar.

JS hanya bertugas menyuntikkan HTML ke wadah, menampilkan atau menyembunyikan form akun, dan
menyalakan atau mematikan tombol Cek. Ia tidak membangun markup apa pun.

### 7.4 Penyimpangan sadar dari halaman referensi

| Referensi | Di proyek ini | Alasan |
| --- | --- | --- |
| Modal "Gagal memeriksa identitas" | Alert sebaris di dalam halaman | Proyek belum punya pola modal; alert sebaris sudah dipakai di seluruh sistem |
| Kolom "ulangi email" | Tidak ada | Mengulang email menambah friksi tanpa mencegah salah ketik yang berarti |
| Konfirmasi kata sandi | Ada | Menangkap salah ketik kata sandi yang nyata |
| OTP WhatsApp | Tidak ada | Sesuai keputusan pada bagian 2 |

### 7.5 Kartu identitas dan status

Lencana status memakai `.status-pill` dengan tone yang sudah ada:

| Status | Tone |
| --- | --- |
| `ACTIVE` | `success` |
| `LEAVE` | `warning` |
| `UNVERIFIED`, `UNKNOWN` | `neutral` |
| `DROPPED_OUT`, `RESIGNED` | `danger` |
| `GRADUATED`, `TRANSFERRED` | `info` |
| Status lain yang tidak dikenali | `neutral`, dengan label "Status belum dikenali" |

### 7.6 Berkas tampilan

| Berkas | Perubahan |
| --- | --- |
| `app/templates/auth/register.html` | Ditulis ulang: dua panel tab, baris pemeriksaan, wadah kartu, form akun |
| `app/templates/auth/_identity_card.html` | Baru — partial kartu identitas |
| `app/templates/auth/_identity_error.html` | Baru — partial alert galat |
| `app/static/js/register.js` | Baru — toggle tab dan panggilan pemeriksaan |
| `app/static/css/app.css` | Aturan baru ditambahkan di akhir berkas, mengikuti kebiasaan proyek |

Kelas CSS baru dibatasi sekecil mungkin: `identity-tabs`, `identity-tab`, `identity-check-row`,
`identity-card`, `identity-badge-sample`. Sisanya memakai kembali kelas yang sudah ada.
`register-steps` pada panel kiri disesuaikan menjadi empat langkah: 01 Verifikasi identitas,
02 Buat akun, 03 Daftarkan wajah, 04 Pilih mata kuliah.

## 8. Penanganan galat

| Kejadian | Pesan ke pengguna | Tercatat di log |
| --- | --- | --- |
| Identifier tidak ada di sumber | "NPM tidak ditemukan di data akademik universitas." | identifier yang dicari |
| Sumber tidak dapat dihubungi | "Sistem data akademik sedang tidak dapat dihubungi. Coba beberapa saat lagi." | URL, status, penyebab |
| Konfigurasi provider kosong | "Integrasi data akademik belum dikonfigurasi. Hubungi administrator." | kunci konfigurasi yang kosong |
| Program studi belum ada di lokal | "Program studi Anda belum terdaftar di sistem. Hubungi administrator." | nama dan kode prodi dari provider |
| Status akademik tidak aktif | pesan sesuai tabel 6.5 | identifier dan statusnya |
| Pemeriksaan berlebihan | "Terlalu banyak pemeriksaan. Tunggu sebentar." | alamat IP dan jumlah percobaan |

Tidak ada isi `Identity` yang lebih luas daripada yang ditampilkan di kartu yang dikirim ke
browser. URL provider dan kunci API hanya ada di sisi server.

## 9. Strategi pengujian

Semua pengujian mengikuti pola yang sudah ada di `tests/test_web_smoke.py`: `create_app()` dengan
`TESTING` dan `WTF_CSRF_ENABLED` dimatikan, database `sqlite://` di memori.

**`tests/test_identity_provider.py`** — unit test tanpa Flask:

- Provider contoh mengembalikan identitas lengkap untuk NPM dan NIK yang benar.
- NPM yang tidak dikenal → `IdentityNotFound`.
- NPM pemicu → `ProviderUnavailable`.
- Seluruh entri data contoh yang **bukan** penanda kasus negatif memiliki nama program studi
  yang ada di daftar `seed-demo` (`app/__init__.py:128-144`). Ini menjaga agar data contoh tidak
  pernah lepas dari data seed, tanpa mengorbankan entri `23312003` yang memang harus tidak
  terdaftar.
- `PustikIdentityProvider` dengan transport palsu: status 200 terpetakan, 404 →
  `IdentityNotFound`, 500 dan timeout → `ProviderUnavailable`, `base_url` kosong →
  `ProviderMisconfigured`.

**`tests/test_register_flow.py`** — pengujian lewat `test_client`. Fixture-nya memanggil
`reset_rate_limit()` dan menyetel `IDENTITY_CHECK_RATE_LIMIT` ke nilai yang cukup tinggi,
sehingga urutan tes tidak saling memengaruhi. Tes pembatasan laju menyetel batasnya sendiri
menjadi rendah lalu mengembalikannya:

- `GET /register` dan `GET /register?jenis=dosen` mengembalikan 200 dan berisi field `npm`
  maupun `nik`.
- `POST /register/check` dengan NPM valid mengembalikan HTML yang memuat nama dari provider.
- `POST /register/check` dengan NPM tidak dikenal memuat pesan "tidak ditemukan".
- `POST /register/check` saat provider tidak dapat dihubungi memuat pesan gangguan, dan
  pesannya berbeda dari kasus tidak ditemukan.
- `POST /register/student` membuat `User` dengan `role="student"`, `npm` benar, `full_name` dari
  provider, `identity_source` terisi, dan `program_id` hasil pemetaan.
- **`full_name` dan `program_id` palsu pada POST diabaikan** — akun tetap memakai data provider.
- `POST /register/student` untuk identitas berstatus bukan ACTIVE ditolak.
- `POST /register/student` untuk identitas dengan program studi yang tidak ada di lokal ditolak.
- `POST /register/lecturer` membuat `User` dengan `role="lecturer"`, `employee_id` berisi NIK,
  dan `nidn` terisi.
- NPM, NIK, dan email yang sudah terdaftar ditolak dengan pesan masing-masing.
- Pembatas laju: pemeriksaan ke-11 dalam satu menit dari IP yang sama dijawab dengan pesan
  pembatasan.

**Pengujian yang sudah ada.** `tests/test_web_smoke.py::test_auth_pages_load` memeriksa
keberadaan `name="npm"` pada halaman register. Karena kedua panel selalu ada di DOM, field itu
tetap ada dan tes tersebut tidak perlu diubah. Bila ternyata harus diubah, hal itu akan
dilaporkan, bukan dikerjakan diam-diam.

## 10. Risiko dan hal yang belum selesai

| Risiko | Sikap |
| --- | --- |
| Kontrak PUSTIK belum diketahui | Pemetaan di `pustik.py` ditulis atas dasar dugaan dan wajib ditinjau saat dokumen asli tersedia. Provider tersebut belum boleh diarahkan ke PUSTIK sungguhan |
| Provider contoh terpakai di produksi | Pengaman lunak: lencana di halaman dan peringatan di log. Pengaman keras (menolak start) sengaja belum dibuat dan dicatat sebagai pekerjaan berikutnya |
| Revisi awal migrasi menyentuh seluruh tabel | Wajib ditinjau sebelum `upgrade`. Database pengembangan harus tetap memuat admin dan 15 program studi |
| Pembatas laju per proses | Hilang saat restart dan tidak dibagi antar-worker. Perlu penyimpanan bersama bila nanti dijalankan multi-worker |
| Endpoint pemeriksaan membocorkan nama dan program studi untuk NPM yang sah | Melekat pada fitur ini. Ditekan dengan pembatas laju, bukan dihilangkan |
| Duplikasi markup form akun pada dua panel | Ditekan dengan Jinja macro. Bila terasa mengganggu, alternatifnya kembali ke satu form dengan `jenis` sebagai field tersembunyi |
| Dependensi baru `requests` | Ditambahkan ke `requirements.txt`. Belum ada klien HTTP lain di proyek ini |

## 11. Berkas yang berubah

| Berkas | Jenis |
| --- | --- |
| `app/integrations/__init__.py` | baru |
| `app/integrations/base.py` | baru |
| `app/integrations/sample.py` | baru |
| `app/integrations/pustik.py` | baru |
| `app/blueprints/auth.py` | diubah — route register |
| `app/utils.py` | diubah — `check_rate_limit()` |
| `app/models.py` | diubah — kolom `identity_source`, `nidn` |
| `app/templates/auth/register.html` | ditulis ulang |
| `app/templates/auth/_identity_card.html` | baru |
| `app/templates/auth/_identity_error.html` | baru |
| `app/static/js/register.js` | baru |
| `app/static/css/app.css` | diubah — aturan baru di akhir |
| `migrations/` | baru — revisi awal |
| `requirements.txt` | diubah — `requests` |
| `.env.example`, `.env` | diubah — kunci provider |
| `tests/test_identity_provider.py` | baru |
| `tests/test_register_flow.py` | baru |
| `README.md` | diubah — keterangan provider dan migrasi |
