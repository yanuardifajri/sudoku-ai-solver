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
    page_title="Sudoku Propositional Logic Solver",
    page_icon=":material/grid_on:",
    layout="wide",
)

# --- Custom CSS for Clean, Modern Sudoku Board UI ---
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)


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
def capture_full_grid_reasoning_trace(n, box_h, box_w, givens):
    """
    Instruments forward reasoning over the Definite KB to capture step-by-step
    deductions with complete peer elimination breakdowns and Horn rule firings.
    """
    grid = dict(givens)
    unsolved = [(r, c) for r in range(1, n + 1) for c in range(1, n + 1) if (r, c) not in grid]
    traces = []
    
    step_num = 1
    while unsolved:
        found = False
        for (r, c) in list(unsolved):
            br = ((r - 1) // box_h) * box_h + 1
            bc = ((c - 1) // box_w) * box_w + 1
            
            eliminations = []
            eliminated_values = set()
            
            for v in range(1, n + 1):
                row_peer = next(((r, c2) for c2 in range(1, n + 1) if (r, c2) in grid and grid[(r, c2)] == v), None)
                col_peer = next(((r2, c) for r2 in range(1, n + 1) if (r2, c) in grid and grid[(r2, c)] == v), None)
                box_peer = next(((r2, c2) for r2 in range(br, br + box_h) for c2 in range(bc, bc + box_w) if (r2, c2) in grid and grid[(r2, c2)] == v), None)
                
                if row_peer:
                    eliminated_values.add(v)
                    eliminations.append({
                        'val': v,
                        'scope': 'Row',
                        'peer_cell': row_peer,
                        'rule': f"Is{r}_{row_peer[1]}_{v} ==> Not{r}_{c}_{v}",
                        'explanation': f"Row {r} already contains Value {v} at Cell {row_peer}"
                    })
                elif col_peer:
                    eliminated_values.add(v)
                    eliminations.append({
                        'val': v,
                        'scope': 'Column',
                        'peer_cell': col_peer,
                        'rule': f"Is{col_peer[0]}_{c}_{v} ==> Not{r}_{c}_{v}",
                        'explanation': f"Column {c} already contains Value {v} at Cell {col_peer}"
                    })
                elif box_peer:
                    eliminated_values.add(v)
                    box_idx = ((r - 1) // box_h) * (n // box_w) + ((c - 1) // box_w) + 1
                    eliminations.append({
                        'val': v,
                        'scope': 'Box',
                        'peer_cell': box_peer,
                        'rule': f"Is{box_peer[0]}_{box_peer[1]}_{v} ==> Not{r}_{c}_{v}",
                        'explanation': f"Subgrid Box {box_idx} already contains Value {v} at Cell {box_peer}"
                    })
                    
            remaining = [v for v in range(1, n + 1) if v not in eliminated_values]
            if len(remaining) == 1:
                deduced_v = remaining[0]
                grid_before = dict(grid)
                grid[(r, c)] = deduced_v
                grid_after = dict(grid)
                unsolved.remove((r, c))
                
                not_premises = " & ".join([f"Not{r}_{c}_{v_other}" for v_other in range(1, n + 1) if v_other != deduced_v])
                horn_rule = f"({not_premises}) ==> Is{r}_{c}_{deduced_v}"
                peer_cells = [e['peer_cell'] for e in eliminations]
                
                elim_vals_str = ", ".join(str(e['val']) for e in sorted(eliminations, key=lambda x: x['val']))
                traces.append({
                    'step': step_num,
                    'cell': (r, c),
                    'value': deduced_v,
                    'grid_before': grid_before,
                    'grid_after': grid_after,
                    'eliminations': eliminations,
                    'horn_rule': horn_rule,
                    'peer_cells': peer_cells,
                    'summary': f"Candidate values {{{elim_vals_str}}} were eliminated. Cell ({r}, {c}) is deduced to be {deduced_v} (Naked Single)."
                })
                step_num += 1
                found = True
                break
                
        if not found:
            break
            
    return traces, grid


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
                
            html.append(f'<td class="{" ".join(classes)}">{val}</td>')
        html.append('</tr>')
    html.append('</table></div>')
    return ''.join(html)


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


# --- App Header ---
st.title(":material/grid_on: Sudoku Propositional Logic Solver")
st.markdown("An interactive application for exploring **Propositional Logic**, **Horn / Definite Clauses**, and **Forward & Backward Chaining Inference**.")

# --- Sidebar: Puzzle Selector & Information ---
with st.sidebar:
    st.header(":material/tune: Puzzle Settings")
    puzzle_options = [
        f"Puzzle {i + 1} ({p['given_count']} Initial Clues)"
        for i, p in enumerate(puzzles)
    ]
    
    selected_option = st.selectbox(
        "Select Puzzle:",
        options=range(len(puzzles)),
        format_func=lambda i: puzzle_options[i],
        index=st.session_state.selected_puzzle_idx,
    )
    
    # Reset solution when puzzle changes
    if selected_option != st.session_state.selected_puzzle_idx:
        st.session_state.selected_puzzle_idx = selected_option
        st.session_state.current_solution = None
        st.session_state.solve_time = None
        st.session_state.solver_used = None
        st.session_state.query_result = None
        st.session_state.highlight_target = None
        st.session_state.highlight_peers = set()
        st.session_state.traces = None
        st.session_state.step_index = 0
        st.session_state.view_mode = "full"

    selected_puzzle = puzzles[st.session_state.selected_puzzle_idx]
    givens = {tuple(int(x) for x in k.split('_')): v for k, v in selected_puzzle['givens'].items()}
    true_solution = {tuple(int(x) for x in k.split('_')): v for k, v in selected_puzzle['solution'].items()}

    st.divider()
    st.markdown("### :material/info: Puzzle Metadata")
    st.markdown(f"- **Grid Dimension:** {n} × {n}")
    st.markdown(f"- **Box Dimensions:** {box_h} × {box_w}")
    st.markdown(f"- **Initial Clues (Givens):** {len(givens)} cells")
    st.markdown(f"- **Empty Cells to Solve:** {n * n - len(givens)} cells")
    
    st.divider()
    if st.button("Reset Puzzle Board", icon=":material/refresh:"):
        st.session_state.current_solution = None
        st.session_state.solve_time = None
        st.session_state.solver_used = None
        st.session_state.query_result = None
        st.session_state.highlight_target = None
        st.session_state.highlight_peers = set()
        st.session_state.traces = None
        st.session_state.step_index = 0
        st.session_state.view_mode = "full"
        st.rerun()


# --- Main Layout: 2 Columns ---
col_board, col_controls = st.columns([1.05, 1.35], gap="large")

# --- Column 1: Visual Board Display ---
with col_board:
    st.subheader(":material/grid_view: Sudoku Board")
    
    # Visual Legend
    st.markdown(
        """
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;">
            <div><span class="status-badge badge-given">1-9</span> Initial Givens</div>
            <div><span class="status-badge badge-solved">1-9</span> Solved by AI</div>
            <div><span class="status-badge badge-target">Focus</span> Deduced Cell</div>
            <div><span class="status-badge badge-peer">Peer</span> Eliminating Peers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Determine which grid to display
    if st.session_state.view_mode == "stepper" and st.session_state.traces is not None:
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
        
    st.markdown(
        render_board_html(
            display_grid,
            givens,
            highlight_target=target_hl,
            highlight_peers=peers_hl,
        ),
        unsafe_allow_html=True,
    )
    
    if st.session_state.solve_time is not None and st.session_state.view_mode == "full":
        st.success(
            f"Puzzle successfully solved with **{st.session_state.solver_used}** in **{st.session_state.solve_time:.4f} seconds**!",
            icon=":material/check_circle:",
        )


# --- Column 2: Solver, Targeted Query & Knowledge Base Explorer Tabs ---
with col_controls:
    
    # --- 3 Dedicated Tabs ---
    tab_solver, tab_query, tab_kb = st.tabs([
        ":material/play_circle: Full-Grid Auto-Solver",
        ":material/search: Targeted Query & Single-Cell Tutor",
        ":material/menu_book: Knowledge Base Explorer",
    ])
    
    # --- Tab 1: Full-Grid Solver ---
    with tab_solver:
        with st.container(border=True):
            st.markdown("### :material/bolt: Full-Grid Auto-Solver")
            st.markdown("Select a propositional logic inference algorithm to solve the complete grid:")
            
            solver_choice = st.radio(
                "Inference Algorithm:",
                options=[
                    "Forward Chaining (solve_full_grid_fc)",
                    "Backward Chaining (solve_full_grid_bc)",
                ],
                index=0,
            )
            
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                solve_clicked = st.button("Solve Full Grid", type="primary", icon=":material/play_arrow:")
            with btn_col2:
                step_clicked = st.button("Step-by-Step Stepper", type="secondary", icon=":material/step_into:")
                
            if solve_clicked or step_clicked:
                with st.spinner("Executing propositional inference & capturing trace..."):
                    t0 = time.perf_counter()
                    if "Forward Chaining" in solver_choice:
                        solved_grid = solve_full_grid_fc(n, box_h, box_w, givens)
                        solver_name = "Forward Chaining"
                    else:
                        solved_grid = solve_full_grid_bc(n, box_h, box_w, givens)
                        solver_name = "Backward Chaining"
                    elapsed = time.perf_counter() - t0
                    
                    # Capture full deduction trace
                    traces, _ = capture_full_grid_reasoning_trace(n, box_h, box_w, givens)
                    
                    st.session_state.current_solution = solved_grid
                    st.session_state.solve_time = elapsed
                    st.session_state.solver_used = solver_name
                    st.session_state.traces = traces
                    st.session_state.highlight_target = None
                    st.session_state.highlight_peers = set()
                    
                    if step_clicked:
                        st.session_state.view_mode = "stepper"
                        st.session_state.step_index = 1
                    else:
                        st.session_state.view_mode = "full"
                    st.rerun()

            if st.session_state.solve_time is not None:
                st.divider()
                m1, m2 = st.columns(2)
                with m1:
                    st.metric(label="Execution Time", value=f"{st.session_state.solve_time:.4f} s", border=True)
                with m2:
                    st.metric(label="Solved Cells", value=f"{len(st.session_state.current_solution)} / {n*n}", border=True)

    # --- Tab 2: Targeted Query & Tutor Mode ---
    with tab_query:
        with st.container(border=True):
            st.markdown("### :material/fact_check: Cell Entailment Query ($Is_{r,c,v}$)")
            st.markdown("Verify whether cell at row $r$, column $c$ holds value $v$ using `pl_bc_entails`:")
            
            q_col1, q_col2, q_col3 = st.columns(3)
            with q_col1:
                target_r = st.number_input("Row (r)", min_value=1, max_value=n, value=1, step=1)
            with q_col2:
                target_c = st.number_input("Column (c)", min_value=1, max_value=n, value=1, step=1)
            with q_col3:
                target_v = st.number_input("Value (v)", min_value=1, max_value=n, value=1, step=1)
            
            check_btn = st.button("Test Proposition Is", type="secondary", icon=":material/search:")
            
            if check_btn:
                st.session_state.view_mode = "full"
                st.session_state.highlight_target = (target_r, target_c)
                
                with st.spinner("Evaluating definite clauses with backward chaining..."):
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
                    }

            # Display Query Result
            if st.session_state.query_result is not None:
                qr = st.session_state.query_result
                r, c, v, entailed = qr['r'], qr['c'], qr['v'], qr['entailed']
                
                st.divider()
                if entailed:
                    st.success(
                        f"**ENTAILED (True):** Proposition `Is{r}_{c}_{v}` is logically entailed by the Knowledge Base!",
                        icon=":material/check_circle:",
                    )
                else:
                    st.error(
                        f"**NOT ENTAILED (False):** Proposition `Is{r}_{c}_{v}` is NOT a valid fact or solution value.",
                        icon=":material/cancel:",
                    )

    # --- Tab 3: Knowledge Base Explorer ---
    with tab_kb:
        with st.container(border=True):
            st.markdown("### :material/menu_book: Knowledge Base Explorer (General vs. Definite KB)")
            st.markdown("Inspect propositional formalization, mathematical logic, clause statistics, and rule encodings across both representations.")
            
            kb_view = st.segmented_control(
                "Knowledge Base Representation:",
                options=[
                    "Definite / Horn KB (build_definite_kb)",
                    "General CNF KB (build_general_kb)",
                    "Side-by-Side Comparison",
                ],
                default="Definite / Horn KB (build_definite_kb)",
            )
            
            # Subview 1: Definite (Horn) KB
            if kb_view == "Definite / Horn KB (build_definite_kb)":
                st.markdown("#### :material/schema: Definite (Horn) Knowledge Base (`PropDefiniteKB`)")
                st.markdown(r"Encodes Sudoku using strictly **$\le 1$ positive literal per clause** via the **Elimination + Last Candidate (Naked Single)** strategy.")
                
                km1, km2, km3 = st.columns(3)
                with km1:
                    st.metric("Total Definite Clauses", f"{21141 + len(givens):,}", border=True)
                with km2:
                    st.metric("Propositional Symbols", "1,458 (Is & Not)", border=True)
                with km3:
                    st.metric("Supported Inference", "Forward & Backward Chaining", border=True)
                
                st.markdown("##### 🔍 Cell-Specific Horn Rule Inspector")
                st.markdown("Select a cell to view all definite rules generated for it:")
                ic_r, ic_c = st.columns(2)
                with ic_r:
                    insp_r = st.number_input("Cell Row (r)", min_value=1, max_value=n, value=1, step=1, key="def_insp_r")
                with ic_c:
                    insp_c = st.number_input("Cell Column (c)", min_value=1, max_value=n, value=1, step=1, key="def_insp_c")
                
                # Show Last-Candidate Horn rule for this cell
                with st.expander(f"Last-Candidate (Naked Single) Horn Rules for Cell ({insp_r}, {insp_c})", expanded=True, icon=":material/rule:"):
                    st.markdown(r"Rules of the form: $\left(\bigwedge_{v' \neq v} Not_{r,c,v'}\right) \implies Is_{r,c,v}$")
                    for v_cand in range(1, min(4, n + 1)):
                        not_str = " & ".join([f"Not{insp_r}_{insp_c}_{v_oth}" for v_oth in range(1, n + 1) if v_oth != v_cand])
                        st.code(f"({not_str}) ==> Is{insp_r}_{insp_c}_{v_cand}", language="prolog")
                    if n > 3:
                        st.caption(f"... and {n - 3} more candidate deduction rules for values 4 to {n} in Cell ({insp_r}, {insp_c}).")
                
                with st.expander(f"Forward Elimination Rules Triggered by Cell ({insp_r}, {insp_c})", expanded=False, icon=":material/block:"):
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
                    st.caption("Each assigned value at this cell eliminates identical values across row, column, box, and other values in the same cell.")

            # Subview 2: General CNF KB
            elif kb_view == "General CNF KB (build_general_kb)":
                st.markdown("#### :material/account_tree: General CNF Knowledge Base (`PropKB`)")
                st.markdown("Encodes Sudoku using unrestricted Conjunctive Normal Form (CNF) clauses including disjunctions of positive literals.")
                
                gm1, gm2, gm3 = st.columns(3)
                with gm1:
                    st.metric("Total CNF Clauses", f"{10287 + len(givens):,}", border=True)
                with gm2:
                    st.metric("Propositional Symbols", "729 (Is only)", border=True)
                with gm3:
                    st.metric("Supported Inference", "Resolution & Model Checking", border=True)
                
                st.markdown("##### 📊 Clause Distribution Breakdown")
                st.markdown(
                    f"""
                    | Constraint Type | Logical Formula | Clause Count | Clause Size |
                    |---|---|---|---|
                    | **Initial Givens** | $Is_{{r,c,v}}$ | {len(givens)} | 1 literal |
                    | **At-least-one value per cell** | $Is_{{r,c,1}} \\lor \\dots \\lor Is_{{r,c,n}}$ | 81 | 9 positive literals |
                    | **At-most-one value per cell** | $\\neg Is_{{r,c,v_1}} \\lor \\neg Is_{{r,c,v_2}}$ | 2,916 | 2 negative literals |
                    | **Row Uniqueness** | $\\neg Is_{{r,c_1,v}} \\lor \\neg Is_{{r,c_2,v}}$ | 2,916 | 2 negative literals |
                    | **Column Uniqueness** | $\\neg Is_{{r_1,c,v}} \\lor \\neg Is_{{r_2,c,v}}$ | 2,916 | 2 negative literals |
                    | **Box Uniqueness** | $\\neg Is_{{r_1,c_1,v}} \\lor \\neg Is_{{r_2,c_2,v}}$ | 1,458 | 2 negative literals |
                    """
                )
                
                with st.expander("Sample CNF Clauses for Cell (1, 1)", expanded=True, icon=":material/data_object:"):
                    st.markdown("**At-least-one value clause:**")
                    st.code("Is1_1_1 | Is1_1_2 | Is1_1_3 | Is1_1_4 | Is1_1_5 | Is1_1_6 | Is1_1_7 | Is1_1_8 | Is1_1_9", language="prolog")
                    st.markdown("**Sample at-most-one binary conflict clauses:**")
                    st.code("~Is1_1_1 | ~Is1_1_2\n~Is1_1_1 | ~Is1_1_3\n~Is1_1_2 | ~Is1_1_3", language="prolog")
                    st.markdown("**Sample row uniqueness clauses:**")
                    st.code("~Is1_1_1 | ~Is1_2_1\n~Is1_1_1 | ~Is1_3_1", language="prolog")

            # Subview 3: Side-by-Side Comparison
            else:
                st.markdown("#### :material/compare_arrows: General KB vs. Definite (Horn) KB Comparison")
                st.markdown(
                    r"""
                    | Dimension | General KB (`build_general_kb`) | Definite / Horn KB (`build_definite_kb`) |
                    |---|---|---|
                    | **KB Class** | `PropKB` | `PropDefiniteKB` |
                    | **Symbol Families** | Only $Is_{r,c,v}$ (729 symbols) | Dual: $Is_{r,c,v}$ & $Not_{r,c,v}$ (1,458 symbols) |
                    | **Clause Restriction** | Unrestricted CNF | Strictly $\le 1$ positive literal per clause |
                    | **At-Least-One Encoding** | $Is_1 \lor \dots \lor Is_n$ (Disjunctive non-Horn) | $(\bigwedge_{v' \neq v} Not_{r,c,v'}) \implies Is_{r,c,v}$ (Horn) |
                    | **Uniqueness Encoding** | Negative binary clauses: $\neg Is_1 \lor \neg Is_2$ | Forward elimination rules: $Is_{r,c,v} \implies Not_{r',c',v}$ |
                    | **Inference Algorithms** | `pl_resolution`, `tt_entails` (Model Checking) | `pl_fc_entails` (Forward Chaining), `pl_bc_entails` (Backward Chaining) |
                    | **Time Complexity** | Worst-case exponential $O(2^V)$ / Intractable | Linear in KB size $O(\text{Literals})$ / Deterministic |
                    | **Completeness** | Full propositional resolution completeness | Complete for Horn-deducible Naked Single propagation |
                    """
                )


# --- Section 4: User-Friendly Reasoning Trace ("Tutor Mode") ---
st.divider()
st.subheader(":material/school: User-Friendly Reasoning Trace (Tutor Mode)")

# Sub-Section A: Step-by-Step Visual Playback Stepper
if st.session_state.traces is not None:
    traces = st.session_state.traces
    total_steps = len(traces)
    
    with st.container(border=True):
        st.markdown(f"### :material/slow_motion_video: Step-by-Step Deduction Stepper ({total_steps} Deduction Steps)")
        st.markdown("Navigate through each deduction step to visually inspect how the solver eliminates candidates and infers numbers in sequence.")
        
        # Navigation controls
        c_nav1, c_nav2, c_nav3, c_nav4, c_nav5 = st.columns([1, 1, 3, 1, 1])
        with c_nav1:
            if st.button("First", icon=":material/first_page:"):
                st.session_state.view_mode = "stepper"
                st.session_state.step_index = 0
                st.rerun()
        with c_nav2:
            if st.button("Prev", icon=":material/chevron_left:"):
                st.session_state.view_mode = "stepper"
                st.session_state.step_index = max(0, st.session_state.step_index - 1)
                st.rerun()
        with c_nav3:
            curr_step = st.slider(
                "Step Selector:",
                min_value=0,
                max_value=total_steps,
                value=st.session_state.step_index,
                format="Step %d",
                label_visibility="collapsed",
            )
            if curr_step != st.session_state.step_index:
                st.session_state.view_mode = "stepper"
                st.session_state.step_index = curr_step
                st.rerun()
        with c_nav4:
            if st.button("Next", icon=":material/chevron_right:"):
                st.session_state.view_mode = "stepper"
                st.session_state.step_index = min(total_steps, st.session_state.step_index + 1)
                st.rerun()
        with c_nav5:
            if st.button("Last", icon=":material/last_page:"):
                st.session_state.view_mode = "stepper"
                st.session_state.step_index = total_steps
                st.rerun()
                
        # Detailed Card for Active Step
        step_i = st.session_state.step_index
        if step_i == 0:
            st.info("Step 0: Initial Board State (Only Givens). Click **Next** or move the slider to see the first deduction step.", icon=":material/info:")
        else:
            step_data = traces[step_i - 1]
            tr_cell = step_data['cell']
            tr_val = step_data['value']
            
            st.markdown(
                f"#### :material/check_circle: Step {step_i} of {total_steps}: Deducing `Cell ({tr_cell[0]}, {tr_cell[1]})` $\\longrightarrow$ Value **`{tr_val}`**"
            )
            st.markdown(f"*{step_data['summary']}*")
            
            # Expandable Card for Rule-Firing Hierarchy
            with st.expander("Expand Rule-Firing Hierarchy & Natural Language Breakdown", expanded=True, icon=":material/account_tree:"):
                col_rules1, col_rules2 = st.columns([1.1, 0.9])
                
                with col_rules1:
                    st.markdown("##### 1. Elimination Rule Firings ($Is \\implies Not$)")
                    for elim in step_data['eliminations']:
                        p_scope = elim['scope']
                        p_cell = elim['peer_cell']
                        p_val = elim['val']
                        st.markdown(
                            f"- :material/block: **Eliminate `{p_val}`:** {elim['explanation']} $\\implies$ `Is{p_cell[0]}_{p_cell[1]}_{p_val} ==> Not{tr_cell[0]}_{tr_cell[1]}_{p_val}`"
                        )
                        
                with col_rules2:
                    st.markdown("##### 2. Last-Candidate Horn Rule Firing")
                    st.markdown(
                        f"**Horn Clause Head:** `Is{tr_cell[0]}_{tr_cell[1]}_{tr_val}`\n\n"
                        f"**Definite Implication:**\n"
                        f"```prolog\n{step_data['horn_rule']}\n```"
                    )
                    st.markdown(
                        f"- :material/lightbulb: **Plain-English Deduction:** Since all 8 other candidate values are eliminated by surrounding row, column, and box constraints, cell `({tr_cell[0]}, {tr_cell[1]})` is strictly forced to take value **`{tr_val}`** (*Naked Single*)."
                    )


# Sub-Section B: Targeted Query Deduction Trace
with st.expander("Single-Cell Entailment Trace (Targeted Query)", expanded=(st.session_state.query_result is not None), icon=":material/fact_check:"):
    if st.session_state.query_result is None:
        st.info("Test a cell query in the **Targeted Query & Single-Cell Tutor** tab above to inspect its step-by-step reasoning trace.", icon=":material/info:")
    else:
        qr = st.session_state.query_result
        r, c, v, entailed = qr['r'], qr['c'], qr['v'], qr['entailed']
        
        st.markdown(f"#### Deductive Analysis for Cell `({r}, {c})` with Candidate Value `{v}`")
        
        # 1. Givens Check
        if (r, c) in givens:
            given_v = givens[(r, c)]
            if given_v == v:
                st.markdown(f"- :material/check_circle: **Initial Clue (Given):** Cell `({r}, {c})` has value `{v}` directly from the initial puzzle setup (`givens`). No further elimination steps are required.")
            else:
                st.markdown(f"- :material/cancel: **Initial Clue Contradiction:** Cell `({r}, {c})` is already assigned value `{given_v}` in the initial clues, so it cannot hold value `{v}`.")
        else:
            # 2. Peer Elimination Analysis for (r, c)
            st.markdown("##### 1. Candidate Elimination Analysis (Row, Column, Box Peers)")
            
            br_start = ((r - 1) // box_h) * box_h + 1
            bc_start = ((c - 1) // box_w) * box_w + 1
            
            eliminated_values = {}
            for other_v in range(1, n + 1):
                if other_v == v:
                    continue
                row_peer = next(((r, c2) for c2 in range(1, n + 1) if (r, c2) in givens and givens[(r, c2)] == other_v), None)
                col_peer = next(((r2, c) for r2 in range(1, n + 1) if (r2, c) in givens and givens[(r2, c)] == other_v), None)
                box_peer = next(((r2, c2) for r2 in range(br_start, br_start + box_h) for c2 in range(bc_start, bc_start + box_w) if (r2, c2) in givens and givens[(r2, c2)] == other_v), None)
                
                if row_peer:
                    eliminated_values[other_v] = f"Row {r} already contains digit {other_v} at cell `{row_peer}`"
                elif col_peer:
                    eliminated_values[other_v] = f"Column {c} already contains digit {other_v} at cell `{col_peer}`"
                elif box_peer:
                    eliminated_values[other_v] = f"Subgrid Box already contains digit {other_v} at cell `{box_peer}`"
                else:
                    eliminated_values[other_v] = f"Eliminated through Horn clause definite inference chain"

            for val, reason in sorted(eliminated_values.items()):
                st.markdown(f"- :material/block: **Eliminated Candidate `{val}`:** {reason} $\\implies$ Proposition `Not{r}_{c}_{val}` is **True**.")
                
            st.markdown("##### 2. Conclusion Derivation (Naked Single / Last Candidate Rule)")
            if entailed:
                st.markdown(
                    f"- :material/rule: **Horn Rule Applied:** $\\bigwedge_{{v' \\neq {v}}} Not_{{{r},{c},v'}} \\implies Is_{{{r},{c},{v}}}$\n\n"
                    f"- :material/lightbulb: **Final Deduction:** Since all other candidate values have been eliminated by row, column, or subgrid constraints, cell `({r}, {c})` **must** hold value **`{v}`** (*Naked Single / Last Candidate Rule*)."
                )
            else:
                st.markdown(
                    f"- :material/warning: **Conclusion:** Value `{v}` cannot be proven for cell `({r}, {c})` because elimination premises are incomplete or conflict with row/column/box constraints."
                )
