# Role, Menu, dan Alur Sistem

## Admin
Admin mengelola program studi, semester, katalog mata kuliah, penawaran kelas, dosen pengampu, satu atau beberapa slot jadwal mingguan, moda online/offline, kapasitas, persetujuan enrolmen, monitoring Face Profile, rekap presensi dan log. Form pembukaan kelas menampilkan kode, nama mata kuliah, program studi, semester kurikulum, W/P, SKS, semester akademik, dosen, kelas, jadwal, moda, ruang/tautan.

## Dosen
Dosen dapat memilih dari katalog atau menambahkan data mata kuliah baru sekaligus menawarkan kelas yang diajar. Dosen mengatur jadwal kelas, lalu membuka sesi presensi dengan durasi hadir normal dan toleransi terlambat. Sistem membuat QR untuk smartphone dan token singkat untuk laptop/komputer. Dosen melihat jadwal mengajar, statistik kehadiran harian/bulanan/semester, serta ekspor PDF/Excel. Sesi yang melewati batas waktu difinalisasi sebagai CLOSED pada permintaan aplikasi berikutnya; peserta APPROVED yang belum punya catatan ditandai ABSENT.

## Mahasiswa
Mahasiswa mendaftar dengan NPM, nama, email, program studi, password, dan angkatan opsional. Pendaftaran wajah dilakukan setelah login, memakai sampel depan, kedipan, menoleh kiri dan kanan. Mahasiswa memilih penawaran kelas dari program studi sendiri. Setelah APPROVED, jadwal otomatis tampil dan dapat diunduh PDF/Excel. Presensi dilakukan setelah membuka sesi melalui QR/token, lalu sistem meminta sampel mata terbuka dan kedipan dan memvalidasi identitas, enrolmen, sesi, waktu, dan duplikasi. Mahasiswa dapat melihat riwayat dan statistik kehadiran.

## Data program studi yang disediakan
Sastra Inggris, Pendidikan Matematika, Pendidikan Bahasa Inggris, Pendidikan Olahraga, Bahasa Inggris, D3 Bahasa Inggris, Sistem Informasi, Informatika, Teknologi Informasi, Teknik Sipil, Teknik Elektro, Teknik Komputer, Ilmu Komputer, Manajemen, dan Akuntansi.

## Batasan prototipe
Challenge kedip/gerak kepala saat ini merupakan liveness dasar berbasis landmark dari sampel gambar, bukan anti-spoofing tingkat produksi. Pengujian di perangkat sebenarnya dan kalibrasi threshold wajib dilakukan sebelum pemakaian selain demo akademik.
