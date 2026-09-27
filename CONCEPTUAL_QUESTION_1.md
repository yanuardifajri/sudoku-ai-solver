# Conceptual Question 1: Detailed Representation Strategy (General vs. Definite / Horn Encoding)

---

## Overview

In propositional logic, formalizing Sudoku constraints requires mapping the grid's combinatorial rules (row, column, 3x3 box uniqueness, and cell assignment) into well-formed logical clauses. In this project, we designed and implemented two distinct knowledge base representations in [`sudoku_solver.py`](file:///Users/yanuardifajri/Documents/National%20University%20of%20Singapore/Learning%20Resources/Semester%201/%5BIT5005%5D%20Artificial%20Intelligence/Assignment/Sudoku_Project_Group_35/sudoku_solver.py):

1. **General Knowledge Base (`build_general_kb`)**: Implemented using `PropKB` as unrestricted Conjunctive Normal Form (CNF) clauses.
2. **Definite / Horn Knowledge Base (`build_definite_kb`)**: Implemented using `PropDefiniteKB` strictly conforming to definite (Horn) clause structure.

---

## (a) General KB Strategy (`build_general_kb`)

### 1. Representation & Vocabulary
In `build_general_kb`, we only require a single family of positive atomic propositions:
$$\mathit{Is}_{r,c,v} \quad \text{where } r, c, v \in \{1, \dots, n\}$$
meaning that **cell $(r, c)$ contains value $v$**. For a standard $9 \times 9$ grid ($n=9$), there are $9 \times 9 \times 9 = 729$ atomic propositions.

### 2. Constraint Translation to Conjunctive Normal Form (CNF)

A general propositional knowledge base (`PropKB`) accepts arbitrary disjunctions of positive and negative literals without restriction on the number of positive literals per clause. The standard Sudoku rules are encoded directly as follows:

#### 1. Givens (Initial Clues / Unit Facts)
Each predetermined clue $(r, c) \mapsto v$ in the puzzle is added as a unit positive clause:
$$\mathit{Is}_{r,c,v} \quad \forall (r, c, v) \in \text{givens}$$

#### 2. At-Least-One Value per Cell (Definedness / Cell Existence)
Every cell $(r, c)$ must hold at least one value from $\{1, \dots, n\}$. This translates to an $n$-ary disjunction of positive literals:
$$\bigvee_{v=1}^n \mathit{Is}_{r,c,v} \equiv (\mathit{Is}_{r,c,1} \lor \mathit{Is}_{r,c,2} \lor \dots \lor \mathit{Is}_{r,c,n}) \quad \forall r, c \in \{1, \dots, n\}$$
*Clause count for $9 \times 9$:* $9 \times 9 = 81$ clauses (each containing $9$ positive literals).

#### 3. At-Most-One Value per Cell (Cell Uniqueness)
A cell $(r, c)$ cannot hold two distinct values $v_1 \ne v_2$ simultaneously:
$$\neg (\mathit{Is}_{r,c,v_1} \land \mathit{Is}_{r,c,v_2}) \equiv (\neg \mathit{Is}_{r,c,v_1} \lor \neg \mathit{Is}_{r,c,v_2}) \quad \forall r, c, \forall 1 \le v_1 < v_2 \le n$$
*Clause count for $9 \times 9$:* $81 \times \binom{9}{2} = 81 \times 36 = 2{,}916$ binary clauses.

#### 4. Row Uniqueness (No Duplicate Values in a Row)
For any row $r$ and value $v$, no two distinct columns $c_1 < c_2$ can both hold $v$:
$$\neg (\mathit{Is}_{r,c_1,v} \land \mathit{Is}_{r,c_2,v}) \equiv (\neg \mathit{Is}_{r,c_1,v} \lor \neg \mathit{Is}_{r,c_2,v}) \quad \forall r, v, \forall 1 \le c_1 < c_2 \le n$$
*Clause count for $9 \times 9$:* $9 \times 9 \times \binom{9}{2} = 81 \times 36 = 2{,}916$ binary clauses.

#### 5. Column Uniqueness (No Duplicate Values in a Column)
For any column $c$ and value $v$, no two distinct rows $r_1 < r_2$ can both hold $v$:
$$\neg (\mathit{Is}_{r_1,c,v} \land \mathit{Is}_{r_2,c,v}) \equiv (\neg \mathit{Is}_{r_1,c,v} \lor \neg \mathit{Is}_{r_2,c,v}) \quad \forall c, v, \forall 1 \le r_1 < r_2 \le n$$
*Clause count for $9 \times 9$:* $9 \times 9 \times \binom{9}{2} = 81 \times 36 = 2{,}916$ binary clauses.

#### 6. Box Uniqueness (No Duplicate Values in a Subgrid/Box)
For any $3 \times 3$ box and value $v$, no two distinct cells $(r_1, c_1) \ne (r_2, c_2)$ in the same box can both hold $v$. To prevent redundant clauses already covered by row/column constraints, we enforce $r_1 \ne r_2$ and $c_1 \ne c_2$:
$$\neg (\mathit{Is}_{r_1,c_1,v} \land \mathit{Is}_{r_2,c_2,v}) \equiv (\neg \mathit{Is}_{r_1,c_1,v} \lor \neg \mathit{Is}_{r_2,c_2,v}) \quad \forall \text{box}, v, (r_1,c_1) \ne (r_2,c_2)$$
*Clause count for $9 \times 9$:* $9 \text{ boxes} \times 9 \text{ values} \times 18 \text{ cell-pairs} = 1{,}458$ binary clauses.

### Summary of General KB Characteristics
- **Total Clauses ($9 \times 9$, excluding givens):** $81 + 2{,}916 + 2{,}916 + 2{,}916 + 1{,}458 = 10{,}287$ clauses.
- **Expressiveness:** Exact representation of the complete Sudoku model.
- **Inference Limitation:** Because the "at-least-one" clauses contain $n=9$ positive literals (non-Horn), solving requires full propositional resolution (`pl_resolution`) or model checking (`tt_entails`), which exhibit exponential worst-case time complexity $O(2^V)$ or super-exponential search spaces, making full-grid solving computationally intractable.

---

## (b) Definite KB Strategy (`build_definite_kb`)

### 1. The Horn Constraint Dilemma
A **definite (Horn) clause** is formally defined as a disjunction of literals with **exactly one positive literal**:
$$\neg P_1 \lor \neg P_2 \lor \dots \lor \neg P_k \lor Q \quad \equiv \quad (P_1 \land P_2 \land \dots \land P_k \implies Q)$$
where all $P_i$ and $Q$ are positive atomic propositions.

`PropDefiniteKB.tell()` strictly rejects:
1. Clauses with **more than one positive literal** (e.g., $\mathit{Is}_{r,c,1} \lor \mathit{Is}_{r,c,2} \lor \dots \lor \mathit{Is}_{r,c,n}$, which contains $n$ positive literals).
2. Purely negative clauses / constraints with **zero positive literals** (e.g., $\neg \mathit{Is}_{r,c,1} \lor \neg \mathit{Is}_{r,c,2}$).
3. Explicit logical negations in implication premises or conclusions.

### 2. Step-by-Step Resolution: The "Elimination + Last Candidate" Strategy

To overcome this limitation and enable deterministic linear-time forward/backward chaining, we redesigned the knowledge representation using an **Elimination + Naked Single** deduction model.

#### Step 1: Dual Symbol Vocabulary ($\mathit{Is}$ and $\mathit{Not}$)
We introduce a second family of positive propositional symbols:
$$\mathit{Not}_{r,c,v} \quad \text{meaning: cell } (r, c) \text{ definitely does \textbf{not} contain value } v$$
By treating $\mathit{Not}_{r,c,v}$ as an independent positive atomic symbol (rather than a logical negation $\neg \mathit{Is}_{r,c,v}$), assertions that eliminate candidate values can be represented as valid definite implications with a single positive head.

#### Step 2: Forward Elimination Rules ($Is \implies Not$)
Whenever a cell $(r, c)$ holds value $v$, it immediately eliminates conflicting candidates across all four Sudoku scopes:

1. **Same Cell, Other Values:**
   $$\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r,c,v'} \quad \forall v' \ne v$$
2. **Same Row, Other Columns:**
   $$\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r,c',v} \quad \forall c' \ne c$$
3. **Same Column, Other Rows:**
   $$\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r',c,v} \quad \forall r' \ne r$$
4. **Same $3 \times 3$ Box, Other Cells:**
   $$\mathit{Is}_{r_1,c_1,v} \implies \mathit{Not}_{r_2,c_2,v} \quad \forall (r_2, c_2) \ne (r_1, c_1) \text{ in the same box}$$

*Structure check:* Every rule above is of the form $P \implies Q$ with $1$ positive body literal and $1$ positive head literal—a valid definite clause.

#### Step 3: Last-Candidate / Naked Single Rule ($\bigwedge Not \implies Is$)
Instead of the disjunctive rule $\bigvee_{v=1}^n \mathit{Is}_{r,c,v}$, we use constructive elimination (the contrapositive formulation of "Naked Single"):

> *If $n-1$ candidate values for cell $(r, c)$ are ruled out, then cell $(r, c)$ must be assigned the remaining value $v$.*

Formally:
$$\left( \bigwedge_{v' \ne v} \mathit{Not}_{r,c,v'} \right) \implies \mathit{Is}_{r,c,v} \quad \forall r, c, v$$
For $n=9$, the conjunction contains $8$ positive premises ($\mathit{Not}_{r,c,v'}$) and concludes $1$ positive literal ($\mathit{Is}_{r,c,v}$):
$$(\mathit{Not}_{r,c,2} \land \mathit{Not}_{r,c,3} \land \dots \land \mathit{Not}_{r,c,9}) \implies \mathit{Is}_{r,c,1}$$

*Structure check:* This is a definite clause with $8$ positive body literals and exactly $1$ positive head literal, fully accepted by `PropDefiniteKB`.

---

## 3. Propagation Mechanics: How the Definite KB Solves Puzzles

The inference pipeline in the Definite KB operates as a self-sustaining deduction cascade:

```
[ Givens: Is_r_c_v ]
         │
         ▼
[ Forward Elimination Rules ] ──► Infers: Not_r,c,v' across row/col/box
                                           │
                                           ▼
                              [ Last-Candidate Rule ] ──► Infers new: Is_r',c',v''
                                                               │
                                                               └──► (Triggers next wave of eliminations)
```

1. **Initial Facts**: Given clues insert facts $\mathit{Is}_{r,c,v}$ into the KB.
2. **Phase 1 (Elimination)**: $\mathit{Is}$ facts trigger forward elimination rules, deriving hundreds of $\mathit{Not}$ propositions.
3. **Phase 2 (Deduction)**: When a cell accumulates $(n-1)$ distinct $\mathit{Not}$ facts, the corresponding Last-Candidate rule fires, entailing a new $\mathit{Is}_{r',c',v'}$ fact.
4. **Phase 3 (Cascading)**: The newly entailed $\mathit{Is}$ fact acts as a new premise, propagating subsequent eliminations until the entire puzzle is solved.

---

## 4. Comparison Table: General vs. Definite Representation

| Dimension | General KB (`build_general_kb`) | Definite / Horn KB (`build_definite_kb`) |
|---|---|---|
| **KB Class** | `PropKB` | `PropDefiniteKB` |
| **Symbol Families** | Only $\mathit{Is}_{r,c,v}$ (729 symbols) | Dual: $\mathit{Is}_{r,c,v}$ and $\mathit{Not}_{r,c,v}$ (1,458 symbols) |
| **Clause Restrictions** | None (arbitrary CNF clauses) | Strictly $\le 1$ positive literal ($P_1 \land \dots \land P_k \implies Q$) |
| **At-Least-One Encoding** | $\mathit{Is}_{r,c,1} \lor \dots \lor \mathit{Is}_{r,c,n}$ ($n$ positive literals) | $(\bigwedge_{v' \ne v} \mathit{Not}_{r,c,v'}) \implies \mathit{Is}_{r,c,v}$ |
| **Uniqueness Encoding** | Negative binary clauses: $\neg \mathit{Is}_1 \lor \neg \mathit{Is}_2$ | Forward elimination rules: $\mathit{Is}_{r,c,v} \implies \mathit{Not}_{r',c',v}$ |
| **Applicable Algorithms** | `pl_resolution`, `tt_entails` (Model Checking) | `pl_fc_entails` (Forward Chaining), `pl_bc_entails` (Backward Chaining) |
| **Inference Time Complexity** | Worst-case exponential $O(2^V)$ / intractable | Linear in the size of the KB $O(\text{Number of Literals})$ |
| **Soundness & Completeness** | Sound & Complete for general propositional logic | Sound & Complete for Horn-deducible subgrid reasoning (Naked Singles) |
