"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

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


class _IndexedDefiniteKB(PropDefiniteKB):
    """The supplied KB with a cached premise lookup for library FC.

    Inference remains in logic_.pl_fc_entails; only its repeated linear
    clause lookup is indexed. Neither support file is changed.
    """

    def tell(self, sentence):
        super().tell(sentence)
        self._premise_index = None

    def retract(self, sentence):
        super().retract(sentence)
        self._premise_index = None

    def clauses_with_premise(self, premise):
        if getattr(self, '_premise_index', None) is None:
            index = defaultdict(list)
            for clause in self.clauses:
                if clause.op == '==>':
                    for item in conjuncts(clause.args[0]):
                        index[item].append(clause)
            self._premise_index = index
        return self._premise_index.get(premise, [])


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
    kb = _IndexedDefiniteKB()

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
    """Query each cell/value using the supplied pl_fc_entails algorithm."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = dict(givens)
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in grid:
                continue
            for v in range(1, n + 1):
                if pl_fc_entails(kb, atom('Is', r, c, v)):
                    grid[(r, c)] = v
                    break
    return grid


def pl_bc_entails(kb, query):
    """Recursive AND/OR backward proof with cycle-safe positive tabling.

    A failed cyclic branch is not a global disproof. Retry the query with a
    fresh failure table whenever a pass has proved new facts. This computes
    only proofs reached from the query, without a forward-closure prepass.
    Cached results are invalidated whenever the KB clauses change.
    """
    snapshot = tuple(kb.clauses)
    if getattr(kb, '_bc_snapshot', None) != snapshot:
        rules = defaultdict(list)
        facts = set()
        for clause in kb.clauses:
            if clause.op == '==>':
                rules[clause.args[1]].append(tuple(conjuncts(clause.args[0])))
            else:
                facts.add(clause)
        kb._bc_snapshot = snapshot
        kb._bc_rules = rules
        kb._bc_proved = facts
        kb._bc_false = set()

    proved = kb._bc_proved
    if query in proved:
        return True
    if query in kb._bc_false:
        return False

    def prove(goal, visiting, failed):
        if goal in proved:
            return True
        if goal in visiting or goal in failed:
            return False
        visiting.add(goal)
        for premises in kb._bc_rules.get(goal, []):  # OR across rules
            if all(prove(p, visiting, failed) for p in premises):  # AND
                visiting.remove(goal)
                proved.add(goal)
                return True
        visiting.remove(goal)
        failed.add(goal)  # Valid only for this pass, not a permanent disproof.
        return False

    while True:
        before = len(proved)
        if prove(query, set(), set()):
            return True
        if len(proved) == before:
            kb._bc_false.add(query)
            return False


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Query each cell/value with recursive backward chaining."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = dict(givens)
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in grid:
                continue
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    grid[(r, c)] = v
                    break
    return grid
