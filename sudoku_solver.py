"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from collections import defaultdict
from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')


def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus the given
    cells, as general clauses.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int]

    Returns
    -------
    PropKB
    """
    kb = PropKB()

    # 1. Given facts (clues)
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # 2. At-least-one value per cell: (Is_r_c_1 | ... | Is_r_c_n)
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            kb.tell(associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)]))

    # 3. At-most-one value per cell: ~Is_r_c_v1 | ~Is_r_c_v2 for v1 < v2
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c, v1) | ~atom('Is', r, c, v2))

    # 4. Row uniqueness: ~Is_r_c1_v | ~Is_r_c2_v for c1 < c2
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c1, v) | ~atom('Is', r, c2, v))

    # 5. Column uniqueness: ~Is_r1_c_v | ~Is_r2_c_v for r1 < r2
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    kb.tell(~atom('Is', r1, c, v) | ~atom('Is', r2, c, v))

    # 6. Box uniqueness: ~Is_r1_c1_v | ~Is_r2_c2_v for distinct cells in the same box
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


def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB encoding this n x n Sudoku's constraints plus
    the given cells, using elimination + last-candidate reasoning.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int] -- {(row, col): value}, 1-indexed

    Returns
    -------
    PropDefiniteKB
    """
    kb = PropDefiniteKB()

    # 1. Given facts (clues)
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # 2. Elimination rules: Is_r_c_v ==> Not_...
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                is_rcv = atom('Is', r, c, v)

                # Eliminate other values in the same cell
                for v2 in range(1, n + 1):
                    if v2 != v:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c, v2)))

                # Eliminate same value in other columns of the same row
                for c2 in range(1, n + 1):
                    if c2 != c:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c2, v)))

                # Eliminate same value in other rows of the same column
                for r2 in range(1, n + 1):
                    if r2 != r:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r2, c, v)))

    # Box elimination: eliminate same value in other cells of the same box
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

    # 3. Last-candidate (Naked single) rule:
    # (Not_r_c_1 & ... & Not_r_c_n except v) ==> Is_r_c_v
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                premises = [
                    atom('Not', r, c, v_other)
                    for v_other in range(1, n + 1)
                    if v_other != v
                ]
                kb.tell(Expr('==>', associate('&', premises), atom('Is', r, c, v)))

    return kb


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = build_definite_kb(n, box_h, box_w, givens)

    # Perform efficient forward chaining across all clauses
    count = {c: len(conjuncts(c.args[0])) for c in kb.clauses if c.op == '==>'}
    inferred = defaultdict(bool)
    agenda = [s for s in kb.clauses if is_prop_symbol(s.op)]

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

    grid = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if inferred[atom('Is', r, c, v)]:
                    grid[(r, c)] = v
                    break

    return grid


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
    if query in facts:
        return True

    # Goal-directed Backward Chaining:
    # 1. Trace backward from query to identify relevant dependency subgraph
    rules_by_head = defaultdict(list)
    for c in kb.clauses:
        if c.op == '==>':
            rules_by_head[c.args[1]].append(c)

    relevant_goals = {query}
    frontier = [query]
    while frontier:
        g = frontier.pop()
        for c in rules_by_head.get(g, []):
            for p in conjuncts(c.args[0]):
                if p not in relevant_goals:
                    relevant_goals.add(p)
                    frontier.append(p)

    # 2. Evaluate entailment over the goal-directed relevant clause subset
    relevant_clauses = [c for c in kb.clauses if c.op == '==>' and c.args[1] in relevant_goals]
    count = {c: len(conjuncts(c.args[0])) for c in relevant_clauses}
    premise_to_c = defaultdict(list)
    for c in relevant_clauses:
        for p in conjuncts(c.args[0]):
            premise_to_c[p].append(c)

    agenda = [s for s in facts if s in relevant_goals or s in premise_to_c]
    inferred = set(agenda)

    while agenda:
        p = agenda.pop()
        if p == query:
            return True
        for c in premise_to_c.get(p, []):
            count[c] -= 1
            if count[c] == 0:
                head = c.args[1]
                if head not in inferred:
                    inferred.add(head)
                    agenda.append(head)

    return query in inferred


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + your own pl_bc_entails.

    For each cell, try each candidate value until pl_bc_entails confirms one
    -- the same per-cell strategy as solve_full_grid_fc, but backed by
    backward chaining instead of a single shared forward-chaining pass.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = dict(givens)
    unsolved = [(r, c) for r in range(1, n + 1) for c in range(1, n + 1) if (r, c) not in grid]

    while unsolved:
        progress = False
        for (r, c) in list(unsolved):
            for v in range(1, n + 1):
                query = atom('Is', r, c, v)
                if pl_bc_entails(kb, query):
                    grid[(r, c)] = v
                    unsolved.remove((r, c))
                    kb.tell(query)
                    progress = True
                    break
        if not progress:
            break

    return grid

