"""Interactive Streamlit interface for the IT5005 Sudoku assignment."""

import json
import time
from pathlib import Path

import streamlit as st

from sudoku_solver import (
    atom,
    build_definite_kb,
    build_general_kb,
    pl_bc_entails,
    pl_bc_entails_with_trace,
    solve_full_grid_bc,
    solve_full_grid_bc_with_trace,
    solve_full_grid_fc,
    solve_full_grid_fc_with_trace,
)


APP_DIR = Path(__file__).resolve().parent
PUZZLE_PATH = APP_DIR / 'puzzles.json'

st.set_page_config(
    page_title='Sudoku Propositional Logic Solver',
    page_icon='🧩',
    layout='wide',
)

st.markdown(
    """
    <style>
      .sudoku-container {display:flex; justify-content:center; margin:1rem 0;}
      .sudoku-board {border:3px solid #1e293b; border-collapse:collapse;
                     background:#fff; box-shadow:0 4px 12px rgba(15,23,42,.12);}
      .sudoku-cell {width:44px; height:44px; text-align:center; vertical-align:middle;
                    font-size:20px; border:1px solid #cbd5e1;}
      .cell-given {font-weight:800; background:#eef2ff; color:#1e3a8a;}
      .cell-solved {font-weight:700; background:#ecfdf5; color:#047857;}
      .cell-empty {background:#fff; color:#94a3b8;}
      .cell-target {outline:3px solid #2563eb; background:#dbeafe !important;}
      .cell-peer {outline:2px dashed #f59e0b; background:#fef3c7 !important;}
      .border-right {border-right:3px solid #1e293b !important;}
      .border-bottom {border-bottom:3px solid #1e293b !important;}
      .legend {display:flex; flex-wrap:wrap; gap:.7rem; margin-bottom:.5rem;}
      .pill {padding:.2rem .55rem; border-radius:999px; font-size:.82rem; font-weight:650;}
      .pill-given {background:#e0e7ff; color:#3730a3;}
      .pill-solved {background:#d1fae5; color:#065f46;}
      .pill-target {background:#dbeafe; color:#1d4ed8;}
      .pill-peer {background:#fef3c7; color:#b45309;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_puzzle_data(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream)


def decode_mapping(raw_mapping):
    return {
        tuple(int(part) for part in key.split('_')): value
        for key, value in raw_mapping.items()
    }


@st.cache_resource(show_spinner=False)
def cached_definite_kb(n, box_h, box_w, givens_items):
    return build_definite_kb(n, box_h, box_w, dict(givens_items))


@st.cache_data(show_spinner=False)
def cached_reasoning_trace(algorithm, n, box_h, box_w, givens_items):
    givens = dict(givens_items)
    if algorithm == 'Forward Chaining':
        return solve_full_grid_fc_with_trace(n, box_h, box_w, givens)
    return solve_full_grid_bc_with_trace(n, box_h, box_w, givens)


def validate_grid(grid, givens, n, box_h, box_w):
    if len(grid) != n * n:
        return False, f'The solver returned {len(grid)} of {n * n} cells.'
    if any(grid.get(cell) != value for cell, value in givens.items()):
        return False, 'The result changed at least one initial given.'

    required = set(range(1, n + 1))
    for r in range(1, n + 1):
        if {grid[(r, c)] for c in range(1, n + 1)} != required:
            return False, f'Row {r} is invalid.'
    for c in range(1, n + 1):
        if {grid[(r, c)] for r in range(1, n + 1)} != required:
            return False, f'Column {c} is invalid.'
    for br in range(1, n + 1, box_h):
        for bc in range(1, n + 1, box_w):
            values = {
                grid[(r, c)]
                for r in range(br, br + box_h)
                for c in range(bc, bc + box_w)
            }
            if values != required:
                return False, f'The box beginning at ({br}, {bc}) is invalid.'
    return True, 'The grid satisfies every row, column, box, and given constraint.'


def render_board_html(grid, givens, n, box_h, box_w, target=None, peers=None):
    peers = set(peers or ())
    html = ['<div class="sudoku-container"><table class="sudoku-board" aria-label="Sudoku board">']
    for r in range(1, n + 1):
        html.append('<tr>')
        for c in range(1, n + 1):
            classes = ['sudoku-cell']
            if c % box_w == 0 and c < n:
                classes.append('border-right')
            if r % box_h == 0 and r < n:
                classes.append('border-bottom')
            if target == (r, c):
                classes.append('cell-target')
            elif (r, c) in peers:
                classes.append('cell-peer')

            if (r, c) in givens:
                classes.append('cell-given')
                value = givens[(r, c)]
                label = f'Given {value}'
            elif (r, c) in grid:
                classes.append('cell-solved')
                value = grid[(r, c)]
                label = f'Solved {value}'
            else:
                classes.append('cell-empty')
                value = '&middot;'
                label = 'Empty'
            html.append(
                f'<td class="{" ".join(classes)}" aria-label="Row {r}, column {c}: {label}">{value}</td>'
            )
        html.append('</tr>')
    html.append('</table></div>')
    return ''.join(html)


def describe_atom(name):
    for prefix in ('Is', 'Not'):
        if name.startswith(prefix):
            parts = name[len(prefix):].split('_')
            if len(parts) == 3:
                r, c, v = parts
                if prefix == 'Is':
                    return f'Cell ({r}, {c}) has value {v}'
                return f'Cell ({r}, {c}) cannot have value {v}'
    return name


def proof_lines(tree, depth=0, limit=40, lines=None):
    if lines is None:
        lines = []
    if len(lines) >= limit:
        return lines
    indent = '&nbsp;' * (depth * 4)
    status = tree.get('status')
    goal = describe_atom(tree.get('goal', ''))
    if status == 'fact':
        lines.append(f'{indent}✅ **{goal}** — initial fact')
    elif status == 'rule':
        lines.append(f'{indent}✅ **{goal}** — all rule premises were proved')
        for child in tree.get('premises', ()):
            proof_lines(child, depth + 1, limit, lines)
    elif status in {'proved', 'shared'}:
        lines.append(f'{indent}↪ **{goal}** — already established in the proof table')
    else:
        lines.append(f'{indent}❌ **{goal}** — not proved')
    return lines


def fact_cells_from_tree(tree):
    cells = set()
    if tree.get('status') == 'fact' and tree.get('goal', '').startswith('Is'):
        parts = tree['goal'][2:].split('_')
        if len(parts) == 3:
            cells.add((int(parts[0]), int(parts[1])))
    for child in tree.get('premises', ()):
        cells.update(fact_cells_from_tree(child))
    return cells


def kb_statistics(n, box_h, box_w, given_count):
    pairs = n * (n - 1) // 2
    cell_binary = n * n * pairs
    boxes = (n // box_h) * (n // box_w)
    box_cells = box_h * box_w
    box_pairs = boxes * (box_cells * (box_h - 1) * (box_w - 1) // 2) * n
    general_fixed = n * n + 3 * cell_binary + box_pairs

    one_direction = n * n * n * (n - 1)
    box_rules = boxes * box_cells * (box_h - 1) * (box_w - 1) * n
    definite_fixed = 3 * one_direction + box_rules + n ** 3
    return {
        'general_total': general_fixed + given_count,
        'definite_total': definite_fixed + given_count,
        'at_least': n * n,
        'cell_binary': cell_binary,
        'box_binary': box_pairs,
        'is_symbols': n ** 3,
    }


pool = load_puzzle_data(str(PUZZLE_PATH))
n, box_h, box_w = pool['n'], pool['box_h'], pool['box_w']
puzzles = pool['puzzles']

defaults = {
    'selected_puzzle_idx': 0,
    'current_solution': None,
    'solve_time': None,
    'solver_used': None,
    'solve_error': None,
    'query_result': None,
    'highlight_target': None,
    'highlight_peers': set(),
    'traces': None,
    'step_index': 0,
    'view_mode': 'full',
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_results():
    for key, value in defaults.items():
        if key != 'selected_puzzle_idx':
            st.session_state[key] = value


st.title('🧩 Sudoku Propositional Logic Solver')
st.caption('Explore Horn-clause knowledge representation, forward chaining, and recursive backward chaining.')

with st.sidebar:
    st.header('Puzzle settings')
    choice = st.selectbox(
        'Select a puzzle',
        range(len(puzzles)),
        format_func=lambda i: f"Puzzle {i + 1} ({puzzles[i]['given_count']} givens)",
        index=st.session_state.selected_puzzle_idx,
    )
    if choice != st.session_state.selected_puzzle_idx:
        st.session_state.selected_puzzle_idx = choice
        reset_results()

    selected = puzzles[st.session_state.selected_puzzle_idx]
    givens = decode_mapping(selected['givens'])
    st.divider()
    st.write(f'Grid: **{n} × {n}**')
    st.write(f'Box: **{box_h} × {box_w}**')
    st.write(f'Givens: **{len(givens)}**')
    st.write(f'Cells to infer: **{n * n - len(givens)}**')
    if st.button('Reset puzzle', use_container_width=True):
        reset_results()
        st.rerun()


board_col, control_col = st.columns([1, 1.35], gap='large')

with board_col:
    st.subheader('Sudoku board')
    st.markdown(
        '<div class="legend">'
        '<span class="pill pill-given">Given</span>'
        '<span class="pill pill-solved">Inferred</span>'
        '<span class="pill pill-target">Current goal</span>'
        '<span class="pill pill-peer">Proof fact</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.view_mode == 'stepper' and st.session_state.traces:
        index = min(st.session_state.step_index, len(st.session_state.traces))
        if index == 0:
            displayed_grid, target, peers = givens, None, set()
        else:
            active = st.session_state.traces[index - 1]
            displayed_grid = active['grid_after']
            target = active['cell']
            peers = active.get('peer_cells', ())
    else:
        displayed_grid = st.session_state.current_solution or givens
        target = st.session_state.highlight_target
        peers = st.session_state.highlight_peers

    st.markdown(
        render_board_html(displayed_grid, givens, n, box_h, box_w, target, peers),
        unsafe_allow_html=True,
    )

    if st.session_state.solve_error:
        st.error(st.session_state.solve_error)
    elif st.session_state.solve_time is not None:
        st.success(
            f"Validated solution: {st.session_state.solver_used} completed in "
            f"{st.session_state.solve_time:.4f} seconds."
        )


with control_col:
    solver_tab, query_tab, kb_tab = st.tabs([
        'Full-grid solver', 'Targeted entailment query', 'Knowledge-base explorer'
    ])

    with solver_tab:
        st.markdown('### Full-grid auto-solver')
        solver_choice = st.radio(
            'Inference algorithm',
            ['Forward Chaining', 'Backward Chaining'],
            horizontal=True,
        )
        solve_col, trace_col = st.columns(2)
        solve_clicked = solve_col.button('Solve full grid', type='primary', use_container_width=True)
        trace_clicked = trace_col.button('Solve with tutor trace', use_container_width=True)

        if solve_clicked or trace_clicked:
            with st.spinner(f'Running {solver_choice.lower()}...'):
                started = time.perf_counter()
                if solver_choice == 'Forward Chaining':
                    solved = solve_full_grid_fc(n, box_h, box_w, givens)
                else:
                    solved = solve_full_grid_bc(n, box_h, box_w, givens)
                elapsed = time.perf_counter() - started
                valid, message = validate_grid(solved, givens, n, box_h, box_w)

                st.session_state.current_solution = solved
                st.session_state.solve_time = elapsed
                st.session_state.solver_used = solver_choice
                st.session_state.solve_error = None if valid else message
                st.session_state.highlight_target = None
                st.session_state.highlight_peers = set()

                if valid and trace_clicked:
                    traced_grid, traces = cached_reasoning_trace(
                        solver_choice, n, box_h, box_w, tuple(sorted(givens.items()))
                    )
                    trace_valid, trace_message = validate_grid(
                        traced_grid, givens, n, box_h, box_w
                    )
                    if trace_valid and traced_grid == solved:
                        st.session_state.traces = traces
                        st.session_state.step_index = 0
                        st.session_state.view_mode = 'stepper'
                    else:
                        st.session_state.solve_error = (
                            trace_message if not trace_valid else 'Trace and solver results disagree.'
                        )
                else:
                    st.session_state.traces = None
                    st.session_state.view_mode = 'full'
                st.rerun()

        if st.session_state.solve_time is not None:
            metric_a, metric_b = st.columns(2)
            metric_a.metric('Execution time', f'{st.session_state.solve_time:.4f} s')
            metric_b.metric('Solved cells', len(st.session_state.current_solution or {}))

    with query_tab:
        st.markdown('### Is a cell/value proposition entailed?')
        st.caption('The verdict uses recursive backward chaining over the definite-clause KB.')
        q1, q2, q3 = st.columns(3)
        target_r = q1.number_input('Row', 1, n, 1)
        target_c = q2.number_input('Column', 1, n, 1)
        target_v = q3.number_input('Value', 1, n, 1)

        if st.button('Test proposition', use_container_width=True):
            kb = cached_definite_kb(n, box_h, box_w, tuple(sorted(givens.items())))
            query = atom('Is', target_r, target_c, target_v)
            entailed, explanation = pl_bc_entails_with_trace(kb, query, max_depth=4)
            st.session_state.query_result = {
                'r': target_r,
                'c': target_c,
                'v': target_v,
                'entailed': entailed,
                'explanation': explanation,
            }
            st.session_state.view_mode = 'full'
            st.session_state.highlight_target = (target_r, target_c)
            st.session_state.highlight_peers = fact_cells_from_tree(explanation)

        result = st.session_state.query_result
        if result:
            proposition = f"Is{result['r']}_{result['c']}_{result['v']}"
            if result['entailed']:
                st.success(f'Entailed (True): the KB proves `{proposition}`.')
            else:
                st.warning(
                    f'Not entailed (False): the current KB cannot prove `{proposition}`. '
                    'This verdict means “not provable,” not an automatic proof of its negation.'
                )

            with st.expander('View the actual backward-chaining proof', expanded=True):
                explanation = result['explanation']
                if result['entailed']:
                    lines = proof_lines(explanation)
                    for line in lines:
                        st.markdown(line, unsafe_allow_html=True)
                    if len(lines) >= 40:
                        st.caption('The displayed proof is truncated after 40 proof nodes.')
                else:
                    st.write(
                        f"The goal has {explanation.get('candidate_rule_count', 0)} "
                        'candidate rule(s), but none had every premise proved.'
                    )
                    failed = explanation.get('failed_premises', ())
                    if failed:
                        st.write('Representative unproved premises:')
                        for premise in failed:
                            st.write(f'- {describe_atom(premise)}')

    with kb_tab:
        st.markdown('### General versus definite knowledge bases')
        stats = kb_statistics(n, box_h, box_w, len(givens))
        view = st.segmented_control(
            'Representation',
            ['Definite / Horn KB', 'General CNF KB', 'Comparison'],
            default='Definite / Horn KB',
        )
        if view == 'Definite / Horn KB':
            a, b, c = st.columns(3)
            a.metric('Clauses', f"{stats['definite_total']:,}")
            b.metric('Symbols', f"{2 * stats['is_symbols']:,}")
            c.metric('Inference', 'FC and BC')
            st.markdown(
                r'`Is` facts trigger explicit `Not` atoms for cell, row, column, and box '
                r'elimination. If all other values are `Not`, a last-candidate rule entails `Is`.'
            )
        elif view == 'General CNF KB':
            a, b, c = st.columns(3)
            a.metric('Clauses', f"{stats['general_total']:,}")
            b.metric('Symbols', f"{stats['is_symbols']:,}")
            c.metric('Inference', 'Resolution / TT')
            st.markdown(
                f"""
                | Constraint | Clause count |
                |---|---:|
                | Givens | {len(givens):,} |
                | At least one value per cell | {stats['at_least']:,} |
                | At most one value per cell | {stats['cell_binary']:,} |
                | Row uniqueness | {stats['cell_binary']:,} |
                | Column uniqueness | {stats['cell_binary']:,} |
                | Box-only uniqueness | {stats['box_binary']:,} |
                """
            )
        else:
            st.markdown(
                r"""
                | Dimension | General KB | Definite / Horn KB |
                |---|---|---|
                | Symbols | $Is_{r,c,v}$ | $Is_{r,c,v}$ and explicit $Not_{r,c,v}$ atoms |
                | Clause form | Arbitrary CNF | Facts and $P_1\land\cdots\land P_k\Rightarrow Q$ |
                | At least one | Positive disjunction | Last-candidate implication |
                | Uniqueness | Binary negative clauses | Forward elimination rules |
                | Algorithms | Resolution and truth tables | Forward and backward chaining |
                """
            )


st.divider()
st.subheader('Tutor mode: dynamic reasoning trace')

traces = st.session_state.traces
if not traces:
    st.info('Choose “Solve with tutor trace” to inspect the actual inference steps.')
else:
    total = len(traces)
    st.caption(
        f"{st.session_state.solver_used} produced {total} inferred-cell steps. "
        'The trace is generated by the same inference representation as the selected algorithm.'
    )
    nav1, nav2, nav3, nav4 = st.columns([1, 1, 4, 1])
    if nav1.button('First'):
        st.session_state.step_index = 0
        st.session_state.view_mode = 'stepper'
        st.rerun()
    if nav2.button('Previous'):
        st.session_state.step_index = max(0, st.session_state.step_index - 1)
        st.session_state.view_mode = 'stepper'
        st.rerun()
    selected_step = nav3.slider('Trace step', 0, total, st.session_state.step_index)
    if selected_step != st.session_state.step_index:
        st.session_state.step_index = selected_step
        st.session_state.view_mode = 'stepper'
        st.rerun()
    if nav4.button('Next'):
        st.session_state.step_index = min(total, st.session_state.step_index + 1)
        st.session_state.view_mode = 'stepper'
        st.rerun()

    if st.session_state.step_index == 0:
        st.info('Step 0 shows the initial givens. Move to Step 1 to see the first inference.')
    else:
        step = traces[st.session_state.step_index - 1]
        r, c = step['cell']
        v = step['value']
        st.markdown(
            f"### Step {st.session_state.step_index} of {total}: "
            f"cell ({r}, {c}) is inferred as {v}"
        )
        st.write(step['summary'])

        if step['algorithm'] == 'Forward Chaining':
            with st.expander('Actual rule firing and supporting facts', expanded=True):
                for item in step.get('evidence', ()):
                    value = item.get('eliminated_value', '?')
                    if 'source_cell' in item:
                        sr, sc = item['source_cell']
                        st.write(
                            f"- Eliminate {value}: the {item['scope']} contains value "
                            f"{item['source_value']} at cell ({sr}, {sc})."
                        )
                    else:
                        st.write(f"- Eliminate {value}: `{item['premise']}` was previously inferred.")
                st.code(step['rule'], language='text')
        else:
            with st.expander('Recursive AND/OR proof tree', expanded=True):
                for line in proof_lines(step['proof'], limit=35):
                    st.markdown(line, unsafe_allow_html=True)
