# Penjelasan Implementasi & Desain UI Aplikasi Sudoku (`sudoku_app.py`)

Dokumen ini menjelaskan arsitektur, implementasi antarmuka (*UI Design*), dan integrasi modul inferensi logika proposisional pada aplikasi Streamlit [sudoku_app.py](file:///Users/yanuardifajri/Documents/National%20University%20of%20Singapore/Learning%20Resources/Semester%201/%5BIT5005%5D%20Artificial%20Intelligence/Assignment/Sudoku_Project_Group_35/sudoku_app.py).

---

## 1. Ikhtisar Aplikasi

Aplikasi [sudoku_app.py](file:///Users/yanuardifajri/Documents/National%20University%20of%20Singapore/Learning%20Resources/Semester%201/%5BIT5005%5D%20Artificial%20Intelligence/Assignment/Sudoku_Project_Group_35/sudoku_app.py) dibangun menggunakan framework **Streamlit** untuk memberikan antarmuka visual interaktif bagi pengguna dalam mempelajari dan menguji pemecahan teka-teki Sudoku menggunakan **Logika Proposisional** (*Propositional Logic*).

Aplikasi ini mengimpor fungsi inti langsung dari [sudoku_solver.py](file:///Users/yanuardifajri/Documents/National%20University%20of%20Singapore/Learning%20Resources/Semester%201/%5BIT5005%5D%20Artificial%20Intelligence/Assignment/Sudoku_Project_Group_35/sudoku_solver.py) tanpa menduplikasi logika inferensi:
- `atom`
- `build_definite_kb`
- `build_general_kb`
- `solve_full_grid_fc`
- `solve_full_grid_bc`
- `pl_bc_entails`

---

## 2. Struktur & Fitur Utama UI

Antarmuka aplikasi dibagi menjadi 4 bagian fungsional utama:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🧩 SUDOKU PROPOSITIONAL SOLVER                         │
│         Interactive AI Reasoning & Propositional Logic Inference            │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ 1. PANEL PAPAN & SELEKSI TEKA-TEKI   │ 2. PANEL PEMECAH & INFERENSI         │
│  - Dropdown Pilihan Puzzle           │  - Mode Auto-Solver (FC / BC)        │
│  - Board Visual (9x9 Grid HTML/CSS)  │  - Tombol "Solve Full Grid"          │
│    • Angka Awal (Givens): Biru Tebal │  - Metrik Waktu Eksekusi (⏱️ ms/s)   │
│    • Angka Terpecahkan: Hijau Tebal  │                                      │
│    • Sel Kosong: Titik Terang        │ 3. QUERY ENTAILMENT SEL TERTARGET    │
│                                      │  - Input Baris (r), Kolom (c), (v)   │
│                                      │  - Tombol "Check Entailment"         │
│                                      │  - Badge Status (✅ True / ❌ False) │
├──────────────────────────────────────┴──────────────────────────────────────┤
│ 4. MODE TUTOR & JEJAK PENALARAN (REASONING TRACE)                           │
│  - Langkah 1: Status Sel & Fakta Awal                                        │
│  - Langkah 2: Detail Eliminasi Nilai Lain (Baris, Kolom, Subgrid)           │
│  - Langkah 3: Kesimpulan Penarikan Inferensi (Naked Single / Definite Horn) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Rincian Implementasi Fitur

### Fitur 1: Seleksi Puzzle & Visualisasi Papan Grid
- **Pemilihan Data:** Membaca file `puzzles.json` dan menyediakan `st.selectbox` untuk memilih teka-teki berdasarkan indeks dan jumlah angka awal (*givens*).
- **Desain Grid Papan (HTML/CSS):**
  - Menggunakan CSS Grid dengan styling batas tebal (*thick borders*) berukuran 2px untuk setiap subgrid $3 \times 3$, dan batas tipis 1px antar sel.
  - **Givens (Clues):** Ditandai dengan latar belakang lembut (`#eef2ff`), teks tebal berwarna biru tua (`#3730a3`), membedakannya secara tegas dari sel kosong atau sel yang baru terisi.
  - **Solved Cells:** Ditandai dengan warna hijau emerald (`#059669`) dengan animasi highlight saat selesai dipecahkan.
  - **Empty Cells:** Ditampilkan bersih dengan titik transparan.

### Fitur 2: Full-Grid Auto-Solver dengan Pilihan Algoritma
- **Pilihan Metode:** Pengguna dapat memilih antara:
  1. ⚡ **Forward Chaining (`solve_full_grid_fc`)**: Inferensi maju berbasis kaskade fakta data-driven.
  2. 🎯 **Backward Chaining (`solve_full_grid_bc`)**: Inferensi mundur yang membuktikan kandidat per-sel secara goal-driven.
- **Eksekusi & Metrik:**
  - Menghitung waktu penyelesaian dengan presisi tinggi (`time.perf_counter()`).
  - Menampilkan hasil waktu pemecahan menggunakan `st.metric` sehingga perbandingan performa antara FC dan BC dapat diamati secara visual.
  - Menampilkan papan yang telah terisi penuh.

### Fitur 3: Targeted Cell Entailment Query
- Menyediakan 3 input bilangan interaktif ($r \in [1, 9]$, $c \in [1, 9]$, $v \in [1, 9]$).
- Menguji proposisi atomik $\mathit{Is}_{r,c,v}$ menggunakan fungsi `pl_bc_entails(definite_kb, atom('Is', r, c, v))`.
- Menampilkan alert verdict visual:
  - `st.success("✅ Terbukti ENTAILED (True)")` jika nilai tersebut benar merupakan nilai sel tersebut.
  - `st.error("❌ TIDAK Terbukti (False)")` jika nilai tersebut bukan nilai yang valid.

### Fitur 4: Tutor Mode & Jejak Penalaran (*Reasoning Trace*)
- Memberikan penjelasan langkah demi langkah (*human-readable natural language*) mengapa suatu nilai $v$ dapat atau tidak dapat ditarik sebagai kesimpulan untuk sel $(r, c)$.
- Menguraikan:
  1. **Aturan Baris:** Mengidentifikasi sel sebaris yang sudah memiliki angka tertentu.
  2. **Aturan Kolom:** Mengidentifikasi sel sekolom yang menolak kandidat angka tertentu.
  3. **Aturan Box:** Mengidentifikasi sel dalam subgrid $3 \times 3$ yang membatalkan kandidat angka.
  4. **Aturan Kandidat Terakhir (*Naked Single*):** Menjelaskan bahwa jika $(n-1)$ kandidat lainnya tereliminasi, maka sel $(r, c)$ pasti berisi angka $v$.
- Ditampilkan menggunakan komponen `st.expander` yang rapi dan terstruktur.

---

## 4. Cara Menjalankan Aplikasi

Jalankan perintah berikut di terminal:
```bash
streamlit run sudoku_app.py
```
Aplikasi akan otomatis terbuka pada browser di alamat `http://localhost:8501`.
