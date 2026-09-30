import json
import time
import streamlit as st
from utils import *
from logic_ import *
from sudoku_solver import (
    atom,
    build_definite_kb,
    build_general_kb,
    solve_full_grid_fc,
    solve_full_grid_bc,
    pl_bc_entails,
)

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Sudoku solver",
    page_icon=":material/grid_on:",
    layout="wide",
)

# --- Custom CSS for Clean, Modern Sudoku board UI ---
BOARD_CSS = """

    .sudoku-container {
        display: flex;
        justify-content: center;
        margin: 1.2rem 0;
    }
    .sudoku-board {
        border: 3px solid #1e293b;
        border-collapse: collapse;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    .sudoku-cell {
        width: 44px;
        height: 44px;
        text-align: center;
        vertical-align: middle;
        font-size: 20px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        border: 1px solid #cbd5e1;
        transition: all 0.2s ease;
    }
    .cell-given {
        font-weight: 800;
        background-color: #f1f5f9;
        color: #1e3a8a;
    }
    .cell-solved {
        font-weight: 700;
        background-color: #ecfdf5;
        color: #047857;
    }
    .cell-empty {
        background-color: #ffffff;
        color: #94a3b8;
    }
    .cell-highlight-target {
        outline: 3px solid #2563eb !important;
        background-color: #dbeafe !important;
        color: #1d4ed8 !important;
        font-weight: 800 !important;
    }
    .cell-highlight-peer {
        outline: 2px dashed #f59e0b !important;
        background-color: #fef3c7 !important;
        color: #b45309 !important;
        font-weight: 700 !important;
    }
    /* 3x3 Box Thick Borders */
    .border-right-thick {
        border-right: 3px solid #1e293b !important;
    }
    .border-bottom-thick {
        border-bottom: 3px solid #1e293b !important;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .badge-given {
        background-color: #e0e7ff;
        color: #3730a3;
    }
    .badge-solved {
        background-color: #d1fae5;
        color: #065f46;
    }
    .badge-target {
        background-color: #dbeafe;
        color: #1d4ed8;
        border: 1px solid #93c5fd;
    }
    .badge-peer {
        background-color: #fef3c7;
        color: #b45309;
        border: 1px dashed #f59e0b;
    }
"""
st.markdown("<style>" + BOARD_CSS + "</style>", unsafe_allow_html=True)


BOARD_COMPONENT = st.components.v2.component(
    "sudoku_clickable_board",
    html="<div id='board-root'></div>",
    css=BOARD_CSS + """
    .sudoku-board { width: 100%; max-width: 420px; table-layout: fixed; }
    .sudoku-cell { padding: 0; width: auto; height: auto; }
    .sudoku-cell button { display: block; width: 100%; aspect-ratio: 1;
        border: 0; background: transparent; color: inherit; font: inherit;
        font-weight: inherit; cursor: pointer; padding: 0; }
    .sudoku-cell button:hover { box-shadow: inset 0 0 0 2px #64748b; }
    .sudoku-cell button:focus-visible { outline: 3px solid #2563eb; outline-offset: -3px; }
    """,
    js="""
    export default function(component) {
        const { parentElement, data, setTriggerValue } = component;
        const root = parentElement.querySelector('#board-root');
        const focused = root.querySelector('button:focus');
        const previous = focused ? [focused.dataset.row, focused.dataset.col] : null;
        root.innerHTML = data.html;
        const onClick = (event) => {
            const button = event.target.closest('button[data-row]');
            if (!button) return;
            setTriggerValue('selected_cell', {
                puzzle: data.puzzle, row: Number(button.dataset.row), col: Number(button.dataset.col)
            });
        };
        root.addEventListener('click', onClick);
        if (previous) root.querySelector(`button[data-row="${previous[0]}"][data-col="${previous[1]}"]`)?.focus();
        return () => root.removeEventListener('click', onClick);
    }
    """,
)


def choose_board_cell():
    event = st.session_state.get('sudoku_board', {}).get('selected_cell')
    if not event or event.get('puzzle') != st.session_state.selected_puzzle_idx:
        return
    row, col = event.get('row'), event.get('col')
    if not isinstance(row, int) or not isinstance(col, int) or not (1 <= row <= n and 1 <= col <= n):
        return
    st.session_state.query_row = row
    st.session_state.query_col = col
    select_query_cell()
    st.session_state.active_tab = ":material/search: Check a cell"


def select_query_cell():
    st.session_state.highlight_target = (st.session_state.query_row, st.session_state.query_col)
    st.session_state.highlight_peers = set()
    st.session_state.query_result = None


# --- Load Puzzle Pool ---
@st.cache_data
def load_puzzle_data():
    with open('puzzles.json') as f:
        return json.load(f)

pool = load_puzzle_data()
n = pool['n']
box_h = pool['box_h']
box_w = pool['box_w']
puzzles = pool['puzzles']


# --- Helper: Capture Dynamic Reasoning Trace (Forward Inference Stepper) ---
def capture_inference(n, box_h, box_w, givens):
    """Instrument actual Horn rule firings for the UI, recording proof parents."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    pending, uses, proofs = {}, defaultdict(list), {}
    agenda = []
    for clause in kb.clauses:
        if clause.op == '==>':
            premises = conjuncts(clause.args[0])
            pending[clause] = len(premises)
            for premise in premises:
                uses[premise].append(clause)
        else:
            agenda.append(clause)
            proofs[clause] = ()
    inferred, order = set(), []
    while agenda:
        fact = agenda.pop()
        if fact in inferred:
            continue
        inferred.add(fact)
        order.append(fact)
        for clause in uses[fact]:
            pending[clause] -= 1
            head = clause.args[1]
            if pending[clause] == 0 and head not in proofs:
                proofs[head] = tuple(conjuncts(clause.args[0]))
                agenda.append(head)
    return inferred, proofs, order


def symbol_parts(symbol):
    name = symbol.op
    prefix = 'Not' if name.startswith('Not') else 'Is'
    return prefix, *map(int, name[len(prefix):].split('_'))


def elimination_details(symbol, proofs):
    _, r, c, v = symbol_parts(symbol)
    source = proofs[symbol][0]
    _, pr, pc, pv = symbol_parts(source)
    if (r, c) == (pr, pc):
        scope = 'Cell'
        explanation = f'Cell ({r}, {c}) already has value {pv}'
    elif r == pr:
        scope = 'Row'
        explanation = f'Row {r} already contains value {v} at cell ({pr}, {pc})'
    elif c == pc:
        scope = 'Column'
        explanation = f'Column {c} already contains value {v} at cell ({pr}, {pc})'
    else:
        scope = 'Box'
        explanation = f'The same box contains value {v} at cell ({pr}, {pc})'
    return {'val': v, 'scope': scope, 'peer_cell': (pr, pc),
            'rule': f'{source} ==> {symbol}', 'explanation': explanation}


def capture_full_grid_reasoning_trace(n, box_h, box_w, givens):
    _, proofs, order = capture_inference(n, box_h, box_w, givens)
    grid, traces = dict(givens), []
    for symbol in order:
        prefix, r, c, v = symbol_parts(symbol)
        if prefix != 'Is' or (r, c) in givens:
            continue
        eliminations = [elimination_details(p, proofs) for p in proofs[symbol]]
        before = dict(grid)
        grid[(r, c)] = v
        traces.append({
            'step': len(traces) + 1, 'cell': (r, c), 'value': v,
            'grid_before': before, 'grid_after': dict(grid),
            'eliminations': eliminations,
            'horn_rule': f"({' & '.join(map(str, proofs[symbol]))}) ==> {symbol}",
            'peer_cells': [e['peer_cell'] for e in eliminations],
            'summary': f'All other values were eliminated by proven rules. Cell ({r}, {c}) must be {v}.',
        })
    return traces, grid


def capture_query_reasoning_trace(n, box_h, box_w, givens, r, c, v):
    inferred, proofs, order = capture_inference(n, box_h, box_w, givens)
    query, negative = atom('Is', r, c, v), atom('Not', r, c, v)
    target = query if query in inferred else negative if negative in inferred else None
    relevant = set()

    def visit(symbol):
        if symbol in relevant:
            return
        relevant.add(symbol)
        for premise in proofs[symbol]:
            visit(premise)

    if target is not None:
        visit(target)
    steps = []
    for symbol in order:
        if symbol not in relevant:
            continue
        prefix, sr, sc, sv = symbol_parts(symbol)
        if not proofs[symbol]:
            steps.append(f'Starting clue: row {sr}, column {sc} contains {sv}.')
        elif prefix == 'Not':
            details = elimination_details(symbol, proofs)
            steps.append(f"{details['explanation']}; eliminate {sv} from cell ({sr}, {sc}).")
        else:
            steps.append(f'All other numbers are ruled out in row {sr}, column {sc}, so the number must be {sv}.')
    return {
        'eliminated': [value for value in range(1, n + 1)
                       if atom('Not', r, c, value) in inferred],
        'ruled_out': negative in inferred, 'steps': steps,
        'entailed': query in inferred,
    }


# --- Helper Function to Render Visual Board ---
def render_board_html(grid_dict, givens_dict, highlight_target=None, highlight_peers=None):
    if highlight_peers is None:
        highlight_peers = set()
    else:
        highlight_peers = set(highlight_peers)
        
    html = ['<div class="sudoku-container"><table class="sudoku-board">']
    for r in range(1, n + 1):
        html.append('<tr>')
        for c in range(1, n + 1):
            classes = ['sudoku-cell']
            
            # Thick boundaries for 3x3 boxes
            if c % box_w == 0 and c < n:
                classes.append('border-right-thick')
            if r % box_h == 0 and r < n:
                classes.append('border-bottom-thick')
                
            # Highlights
            if highlight_target == (r, c):
                classes.append('cell-highlight-target')
            elif (r, c) in highlight_peers:
                classes.append('cell-highlight-peer')
                
            # Cell state
            is_given = (r, c) in givens_dict
            is_solved = (r, c) in grid_dict and not is_given
            
            if is_given:
                classes.append('cell-given')
                val = str(givens_dict[(r, c)])
            elif (r, c) in grid_dict:
                classes.append('cell-solved')
                val = str(grid_dict[(r, c)])
            else:
                classes.append('cell-empty')
                val = '&middot;'
                
            label = f"Row {r}, column {c}, " + (f"number {val}" if (r, c) in grid_dict or is_given else "empty")
            html.append(f'<td class="{" ".join(classes)}"><button type="button" data-row="{r}" data-col="{c}" aria-label="{label}" aria-pressed="{str(highlight_target == (r, c)).lower()}">{val}</button></td>')
        html.append('</tr>')
    html.append('</table></div>')
    return ''.join(html)


def select_step(index):
    st.session_state.step_index = index
    st.session_state.step_slider = index
    st.session_state.view_mode = "stepper"
    st.session_state.highlight_target = None
    st.session_state.highlight_peers = set()


def select_slider_step():
    select_step(st.session_state.step_slider)


def show_full_solution():
    st.session_state.view_mode = "full"
    st.session_state.highlight_target = None
    st.session_state.highlight_peers = set()


# --- Initialize Session State ---
if 'selected_puzzle_idx' not in st.session_state:
    st.session_state.selected_puzzle_idx = 0
if 'current_solution' not in st.session_state:
    st.session_state.current_solution = None
if 'solve_time' not in st.session_state:
    st.session_state.solve_time = None
if 'solver_used' not in st.session_state:
    st.session_state.solver_used = None
if 'query_result' not in st.session_state:
    st.session_state.query_result = None
if 'highlight_target' not in st.session_state:
    st.session_state.highlight_target = None
if 'highlight_peers' not in st.session_state:
    st.session_state.highlight_peers = set()
if 'traces' not in st.session_state:
    st.session_state.traces = None
if 'step_index' not in st.session_state:
    st.session_state.step_index = 0
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "full"  # "full" or "stepper"


st.session_state.setdefault('query_row', 1)
st.session_state.setdefault('query_col', 1)
st.session_state.setdefault('hint_traces', None)
st.session_state.setdefault('hint_count', 0)
st.session_state.setdefault('hint_message', None)


# --- App Header ---
st.title(":material/grid_on: Sudoku solver")
st.markdown("Choose a puzzle, solve it, and follow the clues one step at a time.")

# --- Sidebar: Puzzle Selector & Information ---
with st.sidebar:
    st.header(":material/tune: Your puzzle")
    puzzle_options = [
        f"Puzzle {i + 1} ({p['given_count']} clues)"
        for i, p in enumerate(puzzles)
    ]
    
    selected_option = st.selectbox(
        "Choose a puzzle",
        options=range(len(puzzles)),
        format_func=lambda i: puzzle_options[i],
        index=st.session_state.selected_puzzle_idx,
    )
    
    # Reset solution when puzzle changes
    if selected_option != st.session_state.selected_puzzle_idx:
        st.session_state.selected_puzzle_idx = selected_option
        st.session_state.current_solution = None
        st.session_state.hint_traces = None
        st.session_state.hint_count = 0
        st.session_state.hint_message = None
        st.session_state.query_row = 1
        st.session_state.query_col = 1
        st.session_state.solve_time = None
        st.session_state.solver_used = None
        st.session_state.query_result = None
        st.session_state.highlight_target = None
        st.session_state.highlight_peers = set()
        st.session_state.traces = None
        st.session_state.step_index = 0
        st.session_state.step_slider = 0
        st.session_state.view_mode = "full"

    selected_puzzle = puzzles[st.session_state.selected_puzzle_idx]
    givens = {tuple(int(x) for x in k.split('_')): v for k, v in selected_puzzle['givens'].items()}

    st.divider()
    st.markdown("### :material/info: Puzzle details")
    st.markdown(f"- **Board size:** {n} × {n}")
    st.markdown(f"- **Box size:** {box_h} × {box_w}")
    st.markdown(f"- **Starting clues:** {len(givens)} cells")
    st.markdown(f"- **Empty cells:** {n * n - len(givens)} cells")
    
    st.divider()
    if st.button("Reset puzzle", icon=":material/refresh:"):
        st.session_state.current_solution = None
        st.session_state.hint_traces = None
        st.session_state.hint_count = 0
        st.session_state.hint_message = None
        st.session_state.query_row = 1
        st.session_state.query_col = 1
        st.session_state.solve_time = None
        st.session_state.solver_used = None
        st.session_state.query_result = None
        st.session_state.highlight_target = None
        st.session_state.highlight_peers = set()
        st.session_state.traces = None
        st.session_state.step_index = 0
        st.session_state.step_slider = 0
        st.session_state.view_mode = "full"
        st.rerun()


# --- Main Layout: 2 Columns ---
col_board, col_controls = st.columns([1.05, 1.35], gap="large")

# --- Column 1: Visual Board Display ---
with col_board:
    st.subheader(":material/grid_view: Sudoku board")
    
    # Visual Legend
    st.markdown(
        """
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;">
            <div><span class="status-badge badge-given">1-9</span> Starting clues</div>
            <div><span class="status-badge badge-solved">1-9</span> Solved cells</div>
            <div><span class="status-badge badge-target">Focus</span> Selected cell</div>
            <div><span class="status-badge badge-peer">Clue</span> Related clues</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Determine which grid to display
    if st.session_state.view_mode == "hint":
        hint_count = st.session_state.hint_count
        hint = st.session_state.hint_traces[hint_count - 1] if hint_count else None
        display_grid = hint['grid_after'] if hint else givens
        target_hl = hint['cell'] if hint else None
        peers_hl = set(hint['peer_cells']) if hint else set()
    elif st.session_state.view_mode == "stepper" and st.session_state.traces is not None:
        idx = st.session_state.step_index
        if idx == 0:
            display_grid = givens
            target_hl = None
            peers_hl = set()
        else:
            trace_item = st.session_state.traces[idx - 1]
            display_grid = trace_item['grid_after']
            target_hl = trace_item['cell']
            peers_hl = set(trace_item['peer_cells'])
    else:
        display_grid = st.session_state.current_solution if st.session_state.current_solution else givens
        target_hl = st.session_state.highlight_target
        peers_hl = st.session_state.highlight_peers
        
    if st.session_state.highlight_target is not None:
        target_hl = st.session_state.highlight_target
        peers_hl = st.session_state.highlight_peers
    st.caption("Click a cell to open Check a cell automatically. You can also use the Row and Column inputs.")
    BOARD_COMPONENT(
        data={'html': render_board_html(display_grid, givens, target_hl, peers_hl),
              'puzzle': st.session_state.selected_puzzle_idx},
        key="sudoku_board", on_selected_cell_change=choose_board_cell,
    )
    if st.session_state.highlight_target is not None:
        selected_r, selected_c = st.session_state.highlight_target
        st.caption(f"Selected: row {selected_r}, column {selected_c}")

    if st.session_state.solve_time is not None and st.session_state.view_mode == "full":
        filled = len(st.session_state.current_solution)
        if filled == n * n:
            st.success(f"**Puzzle solved.** {st.session_state.solver_used} filled the board in {st.session_state.solve_time:.4f} seconds.", icon=":material/check_circle:")
        else:
            st.warning(f"**Some cells remain unresolved.** {n * n - filled} cells are still empty. The current rules cannot take this puzzle any further.")

    if st.session_state.view_mode == "hint":
        if st.session_state.hint_count:
            hint = st.session_state.hint_traces[st.session_state.hint_count - 1]
            hr, hc = hint['cell']
            st.info(f"**Hint {st.session_state.hint_count}: row {hr}, column {hc} must be {hint['value']}.** All other numbers are ruled out by the clues.", icon=":material/lightbulb:")
            with st.expander("Why this hint works", expanded=True):
                for elimination in sorted(hint['eliminations'], key=lambda e: e['val']):
                    st.write(f"{elimination['val']} does not fit: {elimination['explanation']}.")
        if st.session_state.hint_message:
            st.info(st.session_state.hint_message)


# --- Column 2: Solver, Targeted Query & Behind the scenes Tabs ---
with col_controls:
    
    # --- 3 Dedicated Tabs ---
    tab_solver, tab_query, tab_kb = st.tabs([
        ":material/play_circle: Solve the puzzle",
        ":material/search: Check a cell",
        ":material/menu_book: Behind the scenes",
    ], key="active_tab", on_change="rerun")
    
    # --- Tab 1: Full-Grid Solver ---
    with tab_solver:
        with st.container(border=True):
            st.markdown("### :material/bolt: Solve the puzzle")
            st.markdown("Choose how the solver works, then solve the puzzle or explore each step.")
            
            solver_choice = st.radio(
                "Solving method",
                options=[
                    "Forward chaining",
                    "Backward chaining",
                ],
                index=0,
                help="Forward chaining starts with the clues and applies rules. Backward chaining starts with a possible answer and checks what supports it.",
            )
            
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                solve_clicked = st.button("Solve puzzle", type="primary", icon=":material/play_arrow:")
            with btn_col2:
                step_clicked = st.button("Explore steps", type="secondary", icon=":material/step_into:")
                
            if st.button("Show a hint", icon=":material/lightbulb:", help="Reveal one more number and its explanation, without showing the full solution."):
                if st.session_state.hint_traces is None:
                    with st.spinner("Looking for the next step..."):
                        st.session_state.hint_traces, _ = capture_full_grid_reasoning_trace(n, box_h, box_w, givens)
                if st.session_state.hint_count < len(st.session_state.hint_traces):
                    st.session_state.hint_count += 1
                    st.session_state.hint_message = None
                elif len(givens) + st.session_state.hint_count == n * n:
                    st.session_state.hint_message = "You have reached the completed puzzle. There are no more hints."
                else:
                    st.session_state.hint_message = "No further hint is available. Some cells remain unresolved because the current rules cannot determine another number."
                st.session_state.view_mode = "hint"
                st.session_state.highlight_target = None
                st.session_state.highlight_peers = set()
                st.rerun()

            if solve_clicked or step_clicked:
                # Reuse the current solution when opening the tutorial again.
                reuse_solution = (
                    step_clicked
                    and st.session_state.current_solution is not None
                    and st.session_state.solver_used == solver_choice
                )
                if not reuse_solution:
                    with st.spinner("Solving the puzzle and preparing the steps..."):
                        t0 = time.perf_counter()
                        if solver_choice == "Forward chaining":
                            solved_grid = solve_full_grid_fc(n, box_h, box_w, givens)
                        else:
                            solved_grid = solve_full_grid_bc(n, box_h, box_w, givens)
                        elapsed = time.perf_counter() - t0
                        traces, _ = capture_full_grid_reasoning_trace(n, box_h, box_w, givens)
                        st.session_state.current_solution = solved_grid
                        st.session_state.solve_time = elapsed
                        st.session_state.solver_used = solver_choice
                        st.session_state.traces = traces
                        st.session_state.step_index = 0
                        st.session_state.step_slider = 0
                st.session_state.highlight_target = None
                st.session_state.highlight_peers = set()
                if step_clicked:
                    select_step(st.session_state.step_index or (1 if st.session_state.traces else 0))
                else:
                    show_full_solution()
                st.rerun()

            if st.session_state.solve_time is not None:
                st.divider()
                m1, m2 = st.columns(2)
                with m1:
                    st.metric(label="Solve time", value=f"{st.session_state.solve_time:.4f} s", border=True)
                with m2:
                    st.metric(label="Filled cells", value=f"{len(st.session_state.current_solution)} / {n*n}", border=True)

    # --- Tab 2: Targeted Query & Tutor Mode ---
    with tab_query:
        with st.container(border=True):
            st.markdown("### :material/fact_check: Check a cell")
            st.markdown("Pick a cell and a number to check whether the clues prove that it belongs there.")
            
            q_col1, q_col2, q_col3 = st.columns(3)
            with q_col1:
                target_r = st.number_input("Row", min_value=1, max_value=n, step=1, key="query_row", on_change=select_query_cell)
            with q_col2:
                target_c = st.number_input("Column", min_value=1, max_value=n, step=1, key="query_col", on_change=select_query_cell)
            with q_col3:
                target_v = st.number_input("Number", min_value=1, max_value=n, value=1, step=1)
            
            check_btn = st.button("Check this number", type="secondary", icon=":material/search:")
            
            if check_btn:
                if st.session_state.view_mode != "hint":
                    st.session_state.view_mode = "full"
                st.session_state.highlight_target = (target_r, target_c)
                
                with st.spinner("Checking the clues..."):
                    definite_kb = build_definite_kb(n, box_h, box_w, givens)
                    query_expr = atom('Is', target_r, target_c, target_v)
                    is_entailed = pl_bc_entails(definite_kb, query_expr)
                    
                    # Find eliminating peers for this cell
                    br_start = ((target_r - 1) // box_h) * box_h + 1
                    bc_start = ((target_c - 1) // box_w) * box_w + 1
                    
                    peers = set()
                    for other_v in range(1, n + 1):
                        r_p = next(((target_r, c2) for c2 in range(1, n + 1) if (target_r, c2) in givens and givens[(target_r, c2)] == other_v), None)
                        c_p = next(((r2, target_c) for r2 in range(1, n + 1) if (r2, target_c) in givens and givens[(r2, target_c)] == other_v), None)
                        b_p = next(((r2, c2) for r2 in range(br_start, br_start + box_h) for c2 in range(bc_start, bc_start + box_w) if (r2, c2) in givens and givens[(r2, c2)] == other_v), None)
                        if r_p: peers.add(r_p)
                        if c_p: peers.add(c_p)
                        if b_p: peers.add(b_p)
                    
                    st.session_state.highlight_peers = peers
                    st.session_state.query_result = {
                        'r': target_r,
                        'c': target_c,
                        'v': target_v,
                        'entailed': is_entailed,
                        'trace': capture_query_reasoning_trace(n, box_h, box_w, givens, target_r, target_c, target_v),
                    }
                st.rerun()

            # Display Query Result
            if st.session_state.query_result is not None:
                qr = st.session_state.query_result
                r, c, v, entailed = qr['r'], qr['c'], qr['v'], qr['entailed']
                
                st.divider()
                if entailed:
                    st.success(
                        f"**Yes (True).** Row {r}, column {c} must be **{v}**.",
                        icon=":material/check_circle:",
                    )
                elif qr['trace']['ruled_out']:
                    st.error(
                        f"**This number is ruled out (False).** Row {r}, column {c} cannot be **{v}**.",
                        icon=":material/cancel:",
                    )
                else:
                    st.info(
                        f"**Not yet confirmed (False).** The current rules cannot confirm **{v}** in row {r}, column {c} yet. This does not mean the number is wrong.",
                        icon=":material/help:",
                    )

    # --- Tab 3: Behind the scenes ---
    with tab_kb:
        with st.container(border=True):
            st.markdown("### :material/menu_book: Behind the scenes")
            st.markdown("See how Sudoku rules are stored and used. The technical details below are optional.")
            
            kb_view = st.segmented_control(
                "Rule format",
                options=[
                    "Step-by-step rules (Horn)",
                    "Sudoku constraints (CNF)",
                    "Compare formats",
                ],
                default="Step-by-step rules (Horn)",
            )
            
            # Subview 1: Definite (Horn) KB
            if kb_view == "Step-by-step rules (Horn)":
                st.markdown("#### :material/schema: Rules for finding numbers")
                st.markdown(r"These rules rule out numbers that do not fit. When only one number remains in a cell, the solver fills it in.")
                
                km1, km2, km3 = st.columns(3)
                with km1:
                    st.metric("Rules and clues", f"{21141 + len(givens):,}", border=True)
                with km2:
                    st.metric("Logic symbols", "1,458 (Is & Not)", border=True)
                with km3:
                    st.metric("Solving methods", "Forward & Backward Chaining", border=True)
                
                st.markdown("##### Rules for a cell")
                st.markdown("Choose a cell to see examples of its logic rules.")
                ic_r, ic_c = st.columns(2)
                with ic_r:
                    insp_r = st.number_input("Cell row", min_value=1, max_value=n, value=1, step=1, key="def_insp_r")
                with ic_c:
                    insp_c = st.number_input("Cell column", min_value=1, max_value=n, value=1, step=1, key="def_insp_c")
                
                # Show Last-Candidate Horn rule for this cell
                with st.expander(f"When one number remains in row {insp_r}, column {insp_c}", expanded=True, icon=":material/rule:"):
                    st.markdown(r"Rules of the form: $\left(\bigwedge_{v' \neq v} Not_{r,c,v'}\right) \implies Is_{r,c,v}$")
                    for v_cand in range(1, min(4, n + 1)):
                        not_str = " & ".join([f"Not{insp_r}_{insp_c}_{v_oth}" for v_oth in range(1, n + 1) if v_oth != v_cand])
                        st.code(f"({not_str}) ==> Is{insp_r}_{insp_c}_{v_cand}", language="prolog")
                    if n > 3:
                        st.caption(f"... and {n - 3} more candidate deduction rules for values 4 to {n} in Cell ({insp_r}, {insp_c}).")
                
                with st.expander(f"How this cell rules out other numbers", expanded=False, icon=":material/block:"):
                    st.markdown(r"Rules of the form: $Is_{r,c,v} \implies Not_{r',c',v}$ (Peer Elimination):")
                    sample_v = 1
                    sample_elims = [
                        f"Is{insp_r}_{insp_c}_{sample_v} ==> Not{insp_r}_{insp_c}_{v2}  % Other value in same cell" for v2 in range(2, 4)
                    ] + [
                        f"Is{insp_r}_{insp_c}_{sample_v} ==> Not{insp_r}_{c2}_{sample_v}  % Same row peer" for c2 in range(1, n + 1) if c2 != insp_c
                    ][:2] + [
                        f"Is{insp_r}_{insp_c}_{sample_v} ==> Not{r2}_{insp_c}_{sample_v}  % Same column peer" for r2 in range(1, n + 1) if r2 != insp_r
                    ][:2]
                    for ser in sample_elims:
                        st.code(ser, language="prolog")
                    st.caption("Once this cell is filled, its number cannot appear elsewhere in the same row, column, or box. The cell cannot hold another number either.")

            # Subview 2: General CNF KB
            elif kb_view == "Sudoku constraints (CNF)":
                st.markdown("#### :material/account_tree: Rules a completed Sudoku must follow")
                st.markdown("Every cell needs one number. A number cannot repeat within a row, column, or box. The formulas below describe these rules.")
                
                gm1, gm2, gm3 = st.columns(3)
                with gm1:
                    st.metric("Constraints and clues", f"{10287 + len(givens):,}", border=True)
                with gm2:
                    st.metric("Logic symbols", "729 (Is only)", border=True)
                with gm3:
                    st.metric("Solving methods", "Resolution & Model Checking", border=True)
                
                st.markdown("##### How the rules are counted")
                st.markdown(
                    f"""
                    | Constraint Type | Logical Formula | Clause Count | Clause Size |
                    |---|---|---|---|
                    | **Starting clues** | $Is_{{r,c,v}}$ | {len(givens)} | 1 literal |
                    | **At-least-one value per cell** | $Is_{{r,c,1}} \\lor \\dots \\lor Is_{{r,c,n}}$ | 81 | 9 positive literals |
                    | **At-most-one value per cell** | $\\neg Is_{{r,c,v_1}} \\lor \\neg Is_{{r,c,v_2}}$ | 2,916 | 2 negative literals |
                    | **Row Uniqueness** | $\\neg Is_{{r,c_1,v}} \\lor \\neg Is_{{r,c_2,v}}$ | 2,916 | 2 negative literals |
                    | **Column Uniqueness** | $\\neg Is_{{r_1,c,v}} \\lor \\neg Is_{{r_2,c,v}}$ | 2,916 | 2 negative literals |
                    | **Box Uniqueness** | $\\neg Is_{{r_1,c_1,v}} \\lor \\neg Is_{{r_2,c_2,v}}$ | 1,458 | 2 negative literals |
                    """
                )
                
                with st.expander("Example formulas for row 1, column 1", expanded=True, icon=":material/data_object:"):
                    st.markdown("**At-least-one value clause:**")
                    st.code("Is1_1_1 | Is1_1_2 | Is1_1_3 | Is1_1_4 | Is1_1_5 | Is1_1_6 | Is1_1_7 | Is1_1_8 | Is1_1_9", language="prolog")
                    st.markdown("**Sample at-most-one binary conflict clauses:**")
                    st.code("~Is1_1_1 | ~Is1_1_2\n~Is1_1_1 | ~Is1_1_3\n~Is1_1_2 | ~Is1_1_3", language="prolog")
                    st.markdown("**Sample row uniqueness clauses:**")
                    st.code("~Is1_1_1 | ~Is1_2_1\n~Is1_1_1 | ~Is1_3_1", language="prolog")

            # Subview 3: Compare formats
            else:
                st.markdown("#### :material/compare_arrows: Compare the two rule formats")
                st.markdown(
                    r"""
                    | Dimension | General KB (`build_general_kb`) | Definite / Horn KB (`build_definite_kb`) |
                    |---|---|---|
                    | **KB Class** | `PropKB` | `PropDefiniteKB` |
                    | **Symbol Families** | Only $Is_{r,c,v}$ (729 symbols) | Dual: $Is_{r,c,v}$ & $Not_{r,c,v}$ (1,458 symbols) |
                    | **Clause Restriction** | Unrestricted CNF | Exactly one positive literal per definite clause |
                    | **At-Least-One Encoding** | $Is_1 \lor \dots \lor Is_n$ (Disjunctive non-Horn) | $(\bigwedge_{v' \neq v} Not_{r,c,v'}) \implies Is_{r,c,v}$ (Horn) |
                    | **Uniqueness Encoding** | Negative binary clauses: $\neg Is_1 \lor \neg Is_2$ | Forward elimination rules: $Is_{r,c,v} \implies Not_{r',c',v}$ |
                    | **Inference Algorithms** | `pl_resolution`, `tt_entails` (Model Checking) | `pl_fc_entails` (Forward Chaining), `pl_bc_entails` (Backward Chaining) |
                    | **Time Complexity** | Worst-case exponential $O(2^V)$ / Intractable | One indexed FC pass is linear in literals; repeated queries and recursive BC have additional costs |
                    | **Completeness** | Full propositional resolution completeness | Complete for Horn-deducible Naked Single propagation |
                    """
                )


# --- Section 4: User-Friendly Reasoning Trace ("Tutor Mode") ---
st.divider()
st.subheader(":material/school: How the puzzle is solved")

# Sub-Section A: Step-by-step tutorial
if st.session_state.traces:
    traces = st.session_state.traces
    total_steps = len(traces)
    with st.container(border=True):
        st.markdown("### :material/slow_motion_video: Follow the clues")
        st.caption("Use the controls to see how each number is found. Step 0 shows the starting clues.")
        if st.session_state.view_mode == "stepper":
            st.button("View full solution", icon=":material/grid_on:", on_click=show_full_solution)
        else:
            st.button("Resume steps", icon=":material/step_into:", on_click=select_step,
                      args=(st.session_state.step_index,))
            st.caption("Choose Resume steps to return to the walkthrough.")

        if st.session_state.view_mode == "stepper":
            step_i = st.session_state.step_index
            st.markdown(f"**Step {step_i} of {total_steps}**")
            first, previous, following, last = st.columns(4)
            with first:
                st.button("Start", icon=":material/first_page:", disabled=step_i == 0,
                          on_click=select_step, args=(0,))
            with previous:
                st.button("Previous", icon=":material/chevron_left:", disabled=step_i == 0,
                          on_click=select_step, args=(max(0, step_i - 1),))
            with following:
                st.button("Next", icon=":material/chevron_right:", disabled=step_i == total_steps,
                          on_click=select_step, args=(min(total_steps, step_i + 1),))
            with last:
                st.button("Last step", icon=":material/last_page:", disabled=step_i == total_steps,
                          on_click=select_step, args=(total_steps,))
            # A hidden widget's state may be removed by Streamlit between views.
            st.session_state.setdefault('step_slider', step_i)
            st.slider("Go to step", min_value=0, max_value=total_steps,
                      key="step_slider", on_change=select_slider_step, format="Step %d")
            if step_i == 0:
                st.info("These are the starting clues. Choose Next to see the first number the solver finds.", icon=":material/info:")
            else:
                step_data = traces[step_i - 1]
                r, c = step_data['cell']
                value = step_data['value']
                st.markdown(f"#### Row {r}, column {c} must be {value}")
                st.write(f"The clues rule out all {n - 1} other numbers, leaving only {value}.")
                with st.expander("Why the other numbers do not fit", expanded=True):
                    for elimination in sorted(step_data['eliminations'], key=lambda e: e['val']):
                        st.markdown(f"- **{elimination['val']} does not fit:** {elimination['explanation']}.")
                with st.expander("Technical details: logic rules", expanded=False):
                    st.caption("These are the rules used for this step. Is means a cell has a number; Not means that number is ruled out.")
                    for elimination in step_data['eliminations']:
                        st.code(elimination['rule'], language="text")
                    st.code(step_data['horn_rule'], language="text")
else:
    st.info("Choose Explore steps above to follow the solution one number at a time.", icon=":material/info:")


# Sub-Section B: Targeted Query Deduction Trace
with st.expander("Why this cell check returned that result", expanded=(st.session_state.query_result is not None), icon=":material/fact_check:"):
    if st.session_state.query_result is None:
        st.info("Use **Check a cell** above to see the reasons behind the answer.", icon=":material/info:")
    else:
        qr = st.session_state.query_result
        r, c, v, entailed = qr['r'], qr['c'], qr['v'], qr['entailed']
        
        st.markdown(f"#### Row {r}, column {c}: checking {v}")
        
        trace = qr['trace']
        st.caption('These steps show which clues support the answer.')
        if trace['eliminated']:
            st.markdown('**Numbers ruled out:** ' + ', '.join(map(str, trace['eliminated'])))
        if trace['ruled_out']:
            st.info(f'The clues rule out {v} in row {r}, column {c}.')
        elif not entailed:
            st.info('The rules cannot decide this number yet. That does not necessarily mean it is wrong.')
        if trace['steps']:
            with st.expander('Show the explanation', expanded=True):
                for index, explanation in enumerate(trace['steps'], 1):
                    st.markdown(f'{index}. {explanation}')
        else:
            st.info('The current rules cannot confirm or rule out this number.')
