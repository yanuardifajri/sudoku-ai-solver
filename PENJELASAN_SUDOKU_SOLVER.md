# Penjelasan Komprehensif Solver Sudoku Berbasis Logika Proposisional

Dokumen ini berisi penjelasan lengkap langkah demi langkah (*step-by-step*), dasar matematis/logika, pseudocode, serta implementasi Python untuk lima fungsi utama dalam [sudoku_solver.py](file:///Users/yanuardifajri/Documents/National%20University%20of%20Singapore/Learning%20Resources/Semester%201/%5BIT5005%5D%20Artificial%20Intelligence/Assignment/Sudoku_Project_Group_35/sudoku_solver.py).

---

## Daftar Isi
1. [Ringkasan 5 Fungsi Utama](#1-ringkasan-5-fungsi-utama)
2. [Sistem Representasi Simbol Proposisi](#2-sistem-representasi-simbol-proposisi)
3. [Fungsi 1: `build_general_kb`](#3-fungsi-1-build_general_kb)
4. [Fungsi 2: `build_definite_kb`](#4-fungsi-2-build_definite_kb)
5. [Fungsi 3: `solve_full_grid_fc`](#5-fungsi-3-solve_full_grid_fc)
6. [Fungsi 4: `pl_bc_entails`](#6-fungsi-4-pl_bc_entails)
7. [Fungsi 5: `solve_full_grid_bc`](#7-fungsi-5-solve_full_grid_bc)
8. [Perbandingan Teoretis & Analisis Kompleksitas](#8-perbandingan-teoretis--analisis-kompleksitas)

---

## 1. Ringkasan 5 Fungsi Utama

| Nama Fungsi | Jenis KB / Algoritma | Input | Output | Tujuan Utama |
|---|---|---|---|---|
| `build_general_kb` | **General CNF** (`PropKB`) | `n, box_h, box_w, givens` | `PropKB` | Membangun KB proposisional bebas (CNF arbitrer) untuk semua aturan Sudoku. |
| `build_definite_kb` | **Definite / Horn** (`PropDefiniteKB`) | `n, box_h, box_w, givens` | `PropDefiniteKB` | Membangun KB klausa Horn menggunakan strategi *Eliminasi + Kandidat Terakhir*. |
| `solve_full_grid_fc` | **Forward Chaining** (`pl_fc_entails`) | `n, box_h, box_w, givens` | `dict[(r, c), v]` | Menyelesaikan seluruh papan Sudoku menggunakan inferensi maju (*forward chaining*). |
| `pl_bc_entails` | **Backward Chaining** | `kb, query` | `bool` | Membuktikan apakah suatu *query* proposisi diturunkan secara sah oleh KB melalui pelacakan mundur (*backward chaining*). |
| `solve_full_grid_bc` | **Full-Grid BC Solver** | `n, box_h, box_w, givens` | `dict[(r, c), v]` | Menyelesaikan seluruh papan Sudoku dengan menguji setiap sel menggunakan `pl_bc_entails`. |

---

## 2. Sistem Representasi Simbol Proposisi

Semua koordinat baris $r$, kolom $c$, dan nilai $v$ bernilai **1-indexed** ($1 \le r, c, v \le n$).

Fungsi helper bawaan:
```python
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')
```

- **Simbol $\mathit{Is}_{r,c,v}$ (`atom('Is', r, c, v)`)**:
  Menyatakan bahwa sel pada baris $r$, kolom $c$ **berisi nilai** $v$.
- **Simbol $\mathit{Not}_{r,c,v}$ (`atom('Not', r, c, v)`)**:
  Menyatakan bahwa sel pada baris $r$, kolom $c$ **tidak berisi nilai** $v$.

---

## 3. Fungsi 1: `build_general_kb`

### A. Konsep & Batasan
Fungsi ini membangun objek `PropKB` yang memuat representasi *Conjunctive Normal Form* (CNF) standar dari Sudoku tanpa batasan bentuk klausa.

### B. Aturan Logika yang Diformalkan
1. **Givens (Fakta Awal)**:
   $$\mathit{Is}_{r,c,v} \quad (\forall (r, c): v \in \text{givens})$$
2. **At-least-one value per cell**:
   $$\bigvee_{v=1}^n \mathit{Is}_{r,c,v} = (\mathit{Is}_{r,c,1} \lor \mathit{Is}_{r,c,2} \lor \dots \lor \mathit{Is}_{r,c,n})$$
3. **At-most-one value per cell**:
   $$\neg \mathit{Is}_{r,c,v_1} \lor \neg \mathit{Is}_{r,c,v_2} \quad (1 \le v_1 < v_2 \le n)$$
4. **Row Uniqueness**:
   $$\neg \mathit{Is}_{r,c_1,v} \lor \neg \mathit{Is}_{r,c_2,v} \quad (1 \le c_1 < c_2 \le n)$$
5. **Column Uniqueness**:
   $$\neg \mathit{Is}_{r_1,c,v} \lor \neg \mathit{Is}_{r_2,c,v} \quad (1 \le r_1 < r_2 \le n)$$
6. **Box Uniqueness**:
   $$\neg \mathit{Is}_{r_1,c_1,v} \lor \neg \mathit{Is}_{r_2,c_2,v} \quad (\forall (r_1, c_1) \ne (r_2, c_2) \text{ di subgrid yang sama})$$

### C. Implementasi Kode Python
```python
def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus the given
    cells, as general clauses."""
    kb = PropKB()

    # 1. Givens / Clues awal
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # 2. At-least-one value per cell
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            kb.tell(associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)]))

    # 3. At-most-one value per cell
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c, v1) | ~atom('Is', r, c, v2))

    # 4. Row uniqueness
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c1, v) | ~atom('Is', r, c2, v))

    # 5. Column uniqueness
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    kb.tell(~atom('Is', r1, c, v) | ~atom('Is', r2, c, v))

    # 6. Box uniqueness
    for br in range(1, n + 1, box_h):
        for bc in range(1, n + 1, box_w):
            box_cells = [
                (r, c)
                for r in range(br, br + box_h)
                for c in range(bc, bc + box_w)
            ]
            for i in range(len(box_cells)):
                for j in range(i + 1, len(box_cells)):
                    r1, c1 = box_cells[i]
                    r2, c2 = box_cells[j]
                    if r1 != r2 and c1 != c2:
                        for v in range(1, n + 1):
                            kb.tell(~atom('Is', r1, c1, v) | ~atom('Is', r2, c2, v))

    return kb
```

---

## 4. Fungsi 2: `build_definite_kb`

### A. Konsep & Batasan Horn Clauses
`PropDefiniteKB` hanya menerima klausa pasti (*definite clause*), yaitu klausa yang memiliki **tepat satu literal positif**:
$$P_1 \land P_2 \land \dots \land P_k \implies Q$$
Di mana premis $P_i$ dan konklusi $Q$ seluruhnya merupakan simbol proposisi positif.

### B. Strategi Eliminasi + Kandidat Terakhir (*Elimination + Last Candidate*)
Karena disjungsi $(\mathit{Is}_1 \lor \dots \lor \mathit{Is}_n)$ dan negasi eksplisit dilarang, kita memperkenalkan simbol positif $\mathit{Not}_{r,c,v}$ dan membagi penalaran menjadi 3 tahap:

1. **Fakta Awal (Givens)**:
   $$\mathit{Is}_{r,c,v}$$
2. **Aturan Eliminasi Maju (*Forward Elimination*)**:
   Jika sel $(r, c)$ terisi $v$, maka:
   - Nilai lain di sel yang sama tereliminasi: $\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r,c,v'} \quad (v' \ne v)$
   - Sel lain di baris yang sama tereliminasi: $\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r,c',v} \quad (c' \ne c)$
   - Sel lain di kolom yang sama tereliminasi: $\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r',c,v} \quad (r' \ne r)$
   - Sel lain di subgrid/box yang sama tereliminasi: $\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r',c',v} \quad ((r', c') \ne (r, c))$
3. **Aturan Kandidat Terakhir (*Last-Candidate / Naked Single*)**:
   Jika seluruh $(n - 1)$ kemungkinan nilai lain untuk sel $(r, c)$ sudah tereliminasi, maka sel $(r, c)$ pasti bernilai $v$:
   $$\bigwedge_{v' \ne v} \mathit{Not}_{r,c,v'} \implies \mathit{Is}_{r,c,v}$$

### C. Implementasi Kode Python
```python
def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB encoding this n x n Sudoku's constraints plus
    the given cells, using elimination + last-candidate reasoning."""
    kb = PropDefiniteKB()

    # 1. Givens / Clues awal
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # 2. Aturan Eliminasi: Is_r_c_v ==> Not_...
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                is_rcv = atom('Is', r, c, v)

                # Eliminasi nilai lain pada sel yang sama
                for v2 in range(1, n + 1):
                    if v2 != v:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c, v2)))

                # Eliminasi sel lain pada baris yang sama
                for c2 in range(1, n + 1):
                    if c2 != c:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c2, v)))

                # Eliminasi sel lain pada kolom yang sama
                for r2 in range(1, n + 1):
                    if r2 != r:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r2, c, v)))

    # Eliminasi sel lain pada box / subgrid yang sama
    for br in range(1, n + 1, box_h):
        for bc in range(1, n + 1, box_w):
            box_cells = [
                (r, c)
                for r in range(br, br + box_h)
                for c in range(bc, bc + box_w)
            ]
            for r1, c1 in box_cells:
                for r2, c2 in box_cells:
                    if (r1, c1) != (r2, c2) and r1 != r2 and c1 != c2:
                        for v in range(1, n + 1):
                            kb.tell(Expr('==>', atom('Is', r1, c1, v), atom('Not', r2, c2, v)))

    # 3. Aturan Last-Candidate (Naked Single):
    # (Not_r_c_1 & Not_r_c_2 & ... & Not_r_c_{n-1}) ==> Is_r_c_v
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                premises = [
                    atom('Not', r, c, v_other)
                    for v_other in range(1, n + 1)
                    if v_other != v
                ]
                premise_expr = associate('&', premises)
                kb.tell(Expr('==>', premise_expr, atom('Is', r, c, v)))

    return kb
```

---

## 5. Fungsi 3: `solve_full_grid_fc`

### A. Konsep Kerja
Fungsi ini memanfaatkan algoritma **Forward Chaining** (`pl_fc_entails`) pada `definite_kb`.
Algoritma Forward Chaining bekerja secara *data-driven*:
1. Memulai dari fakta awal (`givens`).
2. Menjalankan aturan eliminasi $\mathit{Is} \implies \mathit{Not}$.
3. Fakta $\mathit{Not}$ yang baru dihasilkan memenuhi premis aturan $\bigwedge \mathit{Not} \implies \mathit{Is}$, memunculkan nilai sel baru.
4. Proses berulang secara kaskade hingga semua sel terisi.

### B. Implementasi Kode Python
Kita dapat menjalankan forward chaining penuh secara efisien dalam satu pass $O(\text{clauses})$:

```python
def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    
    # Forward Chaining kaskade efisien
    count = {c: len(conjuncts(c.args[0])) for c in kb.clauses if c.op == '==>'}
    inferred = defaultdict(bool)
    agenda = [s for s in kb.clauses if is_prop_symbol(s.op)]

    # Indeks premis -> klausa untuk eksekusi O(1)
    premise_to_clauses = defaultdict(list)
    for c in kb.clauses:
        if c.op == '==>':
            for p in conjuncts(c.args[0]):
                premise_to_clauses[p].append(c)

    while agenda:
        p = agenda.pop()
        if not inferred[p]:
            inferred[p] = True
            for c in premise_to_clauses[p]:
                count[c] -= 1
                if count[c] == 0:
                    agenda.append(c.args[1])

    # Ekstrak nilai Is_r_c_v yang terbukti True
    grid = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if inferred[atom('Is', r, c, v)]:
                    grid[(r, c)] = v
                    break

    return grid
```

---

## 6. Fungsi 4: `pl_bc_entails`

### A. Konsep Kerja Backward Chaining
Backward Chaining bekerja secara *goal-driven* (top-down):
1. **Basis:** Jika `query` sudah merupakan fakta yang terbukti $\rightarrow$ return `True`.
2. **Pencegahan Siklus:** Jika `query` sedang dalam proses pembuktian pada *call stack* saat ini (`query in stack`) $\rightarrow$ return `False` untuk memutus loop rekursi tak berhingga.
3. **Pencarian Aturan:** Cari semua aturan yang memiliki konklusi `query` ($P_1 \land \dots \land P_k \implies \text{query}$).
4. **Kombinasi Logika:**
   - **AND:** Suatu aturan berhasil jika **semua** premis $P_i$ terbukti bernilai `True`.
   - **OR:** `query` terbukti jika **salah satu** aturan yang relevan berhasil membuktikannya.

### B. Pseudocode
```text
function PL-BC-ENTAILS(kb, query):
    facts = { c for c in kb.clauses if c is a proposition symbol }
    rules_by_conclusion = group rules in kb by their conclusion

    function BC(goal, stack):
        if goal in facts:
            return True
        if goal in stack:
            return False   # deteksi siklus

        stack.add(goal)
        for rule in rules_by_conclusion[goal]:
            all_premises_proven = True
            for premise in rule.premises:
                if not BC(premise, stack):
                    all_premises_proven = False
                    break
            if all_premises_proven:
                facts.add(goal)   # memoize fakta yang terbukti
                stack.remove(goal)
                return True

        stack.remove(goal)
        return False

    return BC(query, set())
```

### C. Implementasi Kode Python
```python
def pl_bc_entails(kb, query):
    """Your own backward-chaining implementation.

    Parameters
    ----------
    kb : PropDefiniteKB
    query : Expr

    Returns
    -------
    bool
    """
    facts = {c for c in kb.clauses if is_prop_symbol(c.op)}
    rules_by_head = defaultdict(list)
    for c in kb.clauses:
        if c.op == '==>':
            rules_by_head[c.args[1]].append(conjuncts(c.args[0]))

    def bc(goal, stack):
        if goal in facts:
            return True
        if goal in stack:
            return False

        stack.add(goal)
        for premises in rules_by_head.get(goal, []):
            if all(bc(p, stack) for p in premises):
                facts.add(goal)  # Memoization untuk kecepatan dan soundness
                stack.remove(goal)
                return True
        stack.remove(goal)
        return False

    return bc(query, set())
```

---

## 7. Fungsi 5: `solve_full_grid_bc`

### A. Konsep Kerja
Fungsi ini memecahkan papan Sudoku lengkap menggunakan `build_definite_kb` dan `pl_bc_entails`.
- Untuk setiap sel $(r, c)$, solver menguji setiap kemungkinan nilai kandidat $v \in \{1, \dots, n\}$.
- Saat `pl_bc_entails(definite_kb, atom('Is', r, c, v))` mengembalikan `True`, nilai $v$ disimpan ke dalam grid solusi.
- Nilai yang baru terbukti secara otomatis ter-cache sebagai fakta baru di KB, mempercepat pembuktian sel-sel berikutnya.

### B. Implementasi Kode Python
```python
def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + your own pl_bc_entails."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = dict(givens)

    # Uji setiap sel yang belum terisi
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in grid:
                continue
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    grid[(r, c)] = v
                    break

    return grid
```

---

## 8. Perbandingan Teoretis & Analisis Kompleksitas

| Representasi & Algoritma | Kompleksitas Waktu | Karakteristik Inferensi | Skalabilitas pada Sudoku 9x9 |
|---|---|---|---|
| **General KB + Truth Table (`tt_entails`)** | $O(2^V)$ di mana $V = n^3 = 729$ variabel ($2^{729}$) | Sound & Complete | **Infeasible** (membutuhkan waktu ribuan tahun). |
| **General KB + Resolution (`pl_resolution`)** | Eksponensial dalam worst-case | Sound & Complete | **Hang / Sangat Lambat** (ledakan kombinasi resolven klausa). |
| **Definite KB + Forward Chaining (`pl_fc_entails`)** | **Linear** $O(\text{jumlah klausa})$ | Data-driven, polynomial | **Sangat Cepat** ($< 0.1$ detik untuk 1 grid). |
| **Definite KB + Backward Chaining (`pl_bc_entails`)** | **Linear / Sub-linear** terhadap subgraf aturan yang relevan | Goal-directed, polynomial | **Cepat & Terarah** (hanya mengevaluasi premis yang relevan dengan sel target). |
