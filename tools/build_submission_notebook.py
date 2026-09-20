"""Build and execute the final assignment notebook using only the standard library."""

import contextlib
import io
import json
import os
import sys
import traceback
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Sudoku_Assignment.ipynb'


def markdown(source):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': source.splitlines(True)}


def code(source):
    return {
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': source.splitlines(True),
    }


cells = [
    markdown("""# Sudoku Knowledge Representation and Inference

**IT5005 Artificial Intelligence — Group Assignment**

This notebook documents, executes, and validates both propositional representations, the supplied forward-chaining inference procedure, and our recursive backward-chaining implementation. All solver functions are imported from `sudoku_solver.py`; none are duplicated here.
"""),
    code("""from utils import *
from logic_ import *
import json
import statistics
import time

from sudoku_solver import (
    atom,
    build_general_kb,
    build_definite_kb,
    solve_full_grid_fc,
    pl_bc_entails,
    solve_full_grid_bc,
)
"""),
    markdown("""## Load the puzzle pool

Only `givens` are passed to the solver. The supplied `solution` objects are used after inference solely as test oracles.
"""),
    code("""def load_pool(path):
    with open(path, encoding='utf-8') as stream:
        raw = json.load(stream)
    puzzles = []
    for item in raw['puzzles']:
        givens = {tuple(int(x) for x in key.split('_')): value for key, value in item['givens'].items()}
        solution = {tuple(int(x) for x in key.split('_')): value for key, value in item['solution'].items()}
        puzzles.append({'givens': givens, 'solution': solution, 'given_count': item['given_count']})
    return raw['n'], raw['box_h'], raw['box_w'], puzzles

n, box_h, box_w, puzzle_pool = load_pool('puzzles.json')
puzzle = puzzle_pool[0]
givens = puzzle['givens']
print(f'{len(puzzle_pool)} puzzles loaded; grid={n}x{n}; boxes={box_h}x{box_w}')
print('Given counts:', [item['given_count'] for item in puzzle_pool])
print('Working puzzle givens:', len(givens))
"""),
    markdown(r"""## 1. Detailed representation strategy

### General KB (`build_general_kb`)

The general representation uses only the 729 symbols $Is_{r,c,v}$. Every Sudoku condition is placed directly in CNF:

1. **Given:** $Is_{r,c,v}$.
2. **At least one value per cell:** $Is_{r,c,1}\lor\cdots\lor Is_{r,c,9}$.
3. **At most one value per cell:** $\neg Is_{r,c,v_1}\lor\neg Is_{r,c,v_2}$ for every $v_1<v_2$.
4. **Row uniqueness:** $\neg Is_{r,c_1,v}\lor\neg Is_{r,c_2,v}$ for every $c_1<c_2$.
5. **Column uniqueness:** $\neg Is_{r_1,c,v}\lor\neg Is_{r_2,c,v}$ for every $r_1<r_2$.
6. **Box uniqueness:** the analogous binary conflict clause for distinct cells in the same box. Pairs already covered by a row or column clause are skipped to avoid duplicates.

For a 9×9 puzzle this gives 81 at-least-one clauses, 2,916 at-most-one clauses, 2,916 row clauses, 2,916 column clauses, and 1,458 box-only clauses: **10,287 fixed clauses plus the givens**.

### Definite/Horn KB (`build_definite_kb`)

A definite clause cannot express the positive disjunction “one of these nine values holds.” We therefore use two *positive symbol families*: $Is_{r,c,v}$ and $Not_{r,c,v}$. `Not` is part of an atom name, not negation-as-failure.

1. Each given is an `Is` fact.
2. $Is_{r,c,v}\Rightarrow Not_{r,c,v'}$ eliminates other values in the same cell.
3. $Is_{r,c,v}\Rightarrow Not_{r,c',v}$, and the corresponding column and box rules, eliminate the same value from peers.
4. $(\bigwedge_{v'\ne v}Not_{r,c,v'})\Rightarrow Is_{r,c,v}$ implements last-candidate reasoning.

The fixed rule counts are 5,832 same-cell eliminations, 5,832 row eliminations, 5,832 column eliminations, 2,916 box-only eliminations, and 729 last-candidate rules: **21,141 fixed clauses plus the givens**.
"""),
    code("""general_kb = build_general_kb(n, box_h, box_w, givens)
definite_kb = build_definite_kb(n, box_h, box_w, givens)

print(type(general_kb).__name__, 'clauses:', len(general_kb.clauses), 'unique:', len(set(general_kb.clauses)))
print(type(definite_kb).__name__, 'clauses:', len(definite_kb.clauses), 'unique:', len(set(definite_kb.clauses)))
assert len(general_kb.clauses) == 10287 + len(givens)
assert len(definite_kb.clauses) == 21141 + len(givens)
"""),
    markdown("""## 2. Theoretical completeness versus computational tractability

I would not use truth-table model checking or resolution as the default full-grid Sudoku solver, despite both being sound and complete.

`tt_entails` enumerates assignments to the propositional symbols. The general KB has 729 `Is` symbols, so its worst-case model space is $2^{729}$. Even a single query therefore has an infeasible search space.

Resolution begins with 10,317 clauses for the first puzzle after its 30 givens are added. Each round considers many clause pairs and can generate a rapidly growing set of resolvents. Both pair generation and duplicate/subsumption work become prohibitive.

**Observed experiment:** one resolution query on a given cell had not returned after 30 seconds and was interrupted. One truth-table query had not returned after 10 seconds and was also interrupted. These observations are consistent with the clause-pair explosion of resolution and the exponential model space of truth-table enumeration. Horn forward/backward chaining is therefore the practical representation for these puzzles.
"""),
    markdown("""## Solve and validate every supplied puzzle

The forward solver computes one Horn closure, then confirms each inferred cell value with the supplied `pl_fc_entails`. The backward solver uses a recursive AND/OR proof procedure. A complete Horn-closure membership table safely prunes impossible goals; successful goals are still proved recursively through matching rules and their premises.
"""),
    code("""timing_rows = []
for index, item in enumerate(puzzle_pool, start=1):
    started = time.perf_counter()
    solved_fc = solve_full_grid_fc(n, box_h, box_w, item['givens'])
    fc_time = time.perf_counter() - started

    started = time.perf_counter()
    solved_bc = solve_full_grid_bc(n, box_h, box_w, item['givens'])
    bc_time = time.perf_counter() - started

    assert solved_fc == item['solution']
    assert solved_bc == item['solution']
    timing_rows.append((index, item['given_count'], fc_time, bc_time))
    print(f'Puzzle {index}: givens={item["given_count"]}, FC={fc_time:.4f}s, BC={bc_time:.4f}s, both correct')

print(f'Median FC: {statistics.median(row[2] for row in timing_rows):.4f}s')
print(f'Median BC: {statistics.median(row[3] for row in timing_rows):.4f}s')
"""),
    code("""# Completeness and soundness of BC on every cell/value query in Puzzle 1.
definite_kb = build_definite_kb(n, box_h, box_w, givens)
checked = 0
for (r, c), correct_value in puzzle['solution'].items():
    for candidate in range(1, n + 1):
        result = pl_bc_entails(definite_kb, atom('Is', r, c, candidate))
        assert result == (candidate == correct_value)
        checked += 1
print(f'Backward chaining passed all {checked} true/false cell-value checks.')
"""),
    markdown("""## 3. Backward chaining: design, pseudocode, and challenges

```text
BC-ENTAILS(KB, query):
    engine ← cached engine for this unchanged KB
    if query is not in the complete Horn-derivable table: return false
    return PROVE(query, empty visiting set)

PROVE(goal, visiting):
    if goal is a fact or already proved: return true
    if goal is in visiting: return false                 // cyclic branch
    add goal to a copy of visiting

    for each rule whose conclusion equals goal:          // OR across rules
        if any premise is absent from the derivable table:
            continue
        all_proved ← true
        for each premise of the rule:                     // AND across premises
            if PROVE(premise, visiting) is false:
                all_proved ← false
                break
        if all_proved:
            cache goal and its successful rule
            return true
    return false
```

The main challenges were repeated subgoals and cycles. Sudoku Horn rules contain paths such as `Is → Not → Is`, so recursion without a `visiting` set may never terminate. Successful subgoals are memoized so shared proofs are not recomputed. Failed nested subgoals are not blindly memoized because failure may depend on the current cyclic path. Finally, the complete Horn-derivable table provides sound pruning: if a symbol is absent from the Horn closure, no recursive proof can exist. The table does not replace successful backward proofs; it prevents exponential exploration of impossible candidates. Since the KB contains finitely many symbols, cycle detection plus memoization guarantees termination.
"""),
    markdown(r"""## 4. Expressive limits of Horn logic: Naked Pairs

Consider two cells $a$ and $b$ in one row, column, or box, and two candidate values $x,y$. If every other value has been eliminated from both cells, they form a Naked Pair. For every other cell $d$ in that unit, use two definite clauses:

$$
\left(\bigwedge_{z\notin\{x,y\}}Not_{a,z}\right)\land
\left(\bigwedge_{z\notin\{x,y\}}Not_{b,z}\right)
\Rightarrow Not_{d,x}
$$

$$
\left(\bigwedge_{z\notin\{x,y\}}Not_{a,z}\right)\land
\left(\bigwedge_{z\notin\{x,y\}}Not_{b,z}\right)
\Rightarrow Not_{d,y}
$$

These are valid definite clauses because each `Not` expression is a positive propositional atom and each rule has one positive conclusion. The limitation is size rather than expressibility. Directly expanding the schema over 27 units, 36 cell pairs, 36 value pairs, seven remaining cells, and two conclusions creates $27\times36\times36\times7\times2=489{,}888$ rules before removing overlap. This substantially increases construction time, memory use, indexing cost, and the length of explanations. A production solver would generate or index such rules lazily.
"""),
    markdown("""## 5. Data-driven versus goal-driven performance

Backward chaining is significantly faster when the KB is large but a query depends on a small subgraph. For example, a query about one cell may need only a few givens and elimination rules; BC follows those goal-relevant rules, while FC considers every rule reachable from every given.

Backward chaining loses this advantage when many queries share the same dependencies. Full-grid Sudoku requires checking many cell/value candidates, so a naive BC implementation repeatedly visits overlapping proof paths. FC can compute a complete closure once and reuse it. Conversely, our implementation uses a derivability table and memoized successful proofs, so impossible candidates are pruned cheaply and repeated positive subgoals are shared.

The executed timing cell above is the relevant measurement on this machine. The results should be interpreted as implementation-level measurements rather than universal complexity claims: FC includes one direct `pl_fc_entails` confirmation per cell, while BC benefits from its shared proof table. Different query workloads can reverse the ordering.
"""),
    markdown("""## Streamlit integration

The accompanying `sudoku_app.py` provides:

- selection of every puzzle in `puzzles.json`;
- a visual board distinguishing givens and inferred values;
- forward/backward full-grid solving with validated timing;
- targeted `Is(r,c,v)` queries using `pl_bc_entails`;
- truthful algorithm-specific traces: FC rule firings or BC proof trees;
- dynamic KB statistics and general/Horn comparison;
- explicit “not provable” wording for negative entailment results.

### Deployed Streamlit app URL

**Pending team deployment.** Replace this sentence with the final public `https://...streamlit.app` URL after the revised commit is pushed and verified on Streamlit Community Cloud.
"""),
    markdown("""## Final verification summary

- Both solvers match the supplied solutions for all five puzzles.
- Backward chaining returns `True` only for the correct value in all 729 queries on Puzzle 1.
- General and definite KB clause counts match their analytical formulas and contain no duplicates.
- The solver reads only `givens`; `solution` is used only in notebook assertions.
- All notebook code cells were executed and their outputs are visible.
"""),
]


def execute_code_cells(notebook_cells):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    # logic_.py imports networkx although the Sudoku functions do not use it.
    # The deployed/runtime environment installs the real dependency. A minimal
    # module here keeps this reproducible builder independent of local packages.
    if 'networkx' not in sys.modules:
        sys.modules['networkx'] = types.ModuleType('networkx')

    namespace = {'__name__': '__main__'}
    execution_count = 0
    for cell in notebook_cells:
        if cell['cell_type'] != 'code':
            continue
        execution_count += 1
        cell['execution_count'] = execution_count
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                exec(compile(''.join(cell['source']), f'<notebook-cell-{execution_count}>', 'exec'), namespace)
        except Exception as exc:
            cell['outputs'].append({
                'output_type': 'error',
                'ename': type(exc).__name__,
                'evalue': str(exc),
                'traceback': traceback.format_exc().splitlines(),
            })
            raise
        text = output.getvalue()
        if text:
            cell['outputs'].append({'output_type': 'stream', 'name': 'stdout', 'text': text})


execute_code_cells(cells)

notebook = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': f'{sys.version_info.major}.{sys.version_info.minor}'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}
OUTPUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'Wrote executed notebook: {OUTPUT}')
