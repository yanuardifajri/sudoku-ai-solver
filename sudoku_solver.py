"""IT5005 Assignment 1: Sudoku propositional-logic solver.

Only names provided by ``utils.py`` and ``logic_.py`` are imported, as required
by the assignment specification.
"""

from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """Return the Expr for an atom such as ``Is3_2_4``."""
    return expr(f'{prefix}{r}_{c}_{v}')


def build_general_kb(n, box_h, box_w, givens):
    """Return a ``PropKB`` containing all Sudoku constraints and givens."""
    kb = PropKB()

    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # Every cell has at least one value.
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            kb.tell(associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)]))

    # Every cell has at most one value.
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c, v1) | ~atom('Is', r, c, v2))

    # Row uniqueness.
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    kb.tell(~atom('Is', r, c1, v) | ~atom('Is', r, c2, v))

    # Column uniqueness.
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    kb.tell(~atom('Is', r1, c, v) | ~atom('Is', r2, c, v))

    # Box uniqueness. Pairs already covered by a row or column are skipped.
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
    """Return a Horn KB using elimination and last-candidate rules."""
    kb = PropDefiniteKB()

    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # Eliminate alternatives in the same cell and equal values in row/column peers.
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                is_rcv = atom('Is', r, c, v)

                for v2 in range(1, n + 1):
                    if v2 != v:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c, v2)))

                for c2 in range(1, n + 1):
                    if c2 != c:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r, c2, v)))

                for r2 in range(1, n + 1):
                    if r2 != r:
                        kb.tell(Expr('==>', is_rcv, atom('Not', r2, c, v)))

    # Box-only eliminations; same-row/column peers were added above.
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

    # Last-candidate rule.
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                premises = [
                    atom('Not', r, c, other_v)
                    for other_v in range(1, n + 1)
                    if other_v != v
                ]
                kb.tell(Expr('==>', associate('&', premises), atom('Is', r, c, v)))

    return kb


def _premise_index(kb):
    """Index Horn rules by premise."""
    index = defaultdict(list)
    for clause in kb.clauses:
        if clause.op == '==>':
            for premise in conjuncts(clause.args[0]):
                index[premise].append(clause)
    return index


def _install_fc_index(kb):
    """Accelerate ``logic_.pl_fc_entails`` without editing ``logic_.py``."""
    index = _premise_index(kb)
    kb.clauses_with_premise = lambda premise: index.get(premise, ())


def _forward_chain_closure(kb):
    """Compute the Horn closure and retain actual rule-firing supports."""
    count = {
        clause: len(conjuncts(clause.args[0]))
        for clause in kb.clauses
        if clause.op == '==>'
    }
    premise_to_rules = _premise_index(kb)
    facts = [clause for clause in kb.clauses if is_prop_symbol(clause.op)]
    agenda = list(reversed(facts))
    queued = set(facts)
    inferred = set()
    support = {}
    firing_order = []

    while agenda:
        proposition = agenda.pop()
        if proposition in inferred:
            continue
        inferred.add(proposition)

        for clause in premise_to_rules.get(proposition, ()):
            count[clause] -= 1
            if count[clause] == 0:
                conclusion = clause.args[1]
                if conclusion not in queued:
                    queued.add(conclusion)
                    support[conclusion] = tuple(conjuncts(clause.args[0]))
                    firing_order.append(conclusion)
                    agenda.append(conclusion)

    return inferred, support, firing_order


def _grid_from_inferred(n, inferred):
    grid = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            values = [v for v in range(1, n + 1) if atom('Is', r, c, v) in inferred]
            if len(values) > 1:
                raise ValueError(f'Inconsistent KB: cell ({r}, {c}) has multiple entailed values')
            if values:
                grid[(r, c)] = values[0]
    return grid


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve every cell with the supplied ``pl_fc_entails`` function.

    A closure pass identifies each candidate efficiently. The supplied library
    function then confirms the entailed value for every solved cell. An index
    replaces the library's repeated linear premise scan without changing its
    inference semantics.
    """
    kb = build_definite_kb(n, box_h, box_w, givens)
    inferred, _, _ = _forward_chain_closure(kb)
    candidate_grid = _grid_from_inferred(n, inferred)
    _install_fc_index(kb)

    grid = {}
    for (r, c), v in candidate_grid.items():
        query = atom('Is', r, c, v)
        if pl_fc_entails(kb, query):
            grid[(r, c)] = v
    return grid


class _BackwardChainer:
    """Recursive AND/OR backward chainer with cycle-safe tabling."""

    def __init__(self, kb):
        self.kb = kb
        self.clause_count = len(kb.clauses)
        self.facts = {c for c in kb.clauses if is_prop_symbol(c.op)}
        self.rules_by_head = defaultdict(list)
        for clause in kb.clauses:
            if clause.op == '==>':
                self.rules_by_head[clause.args[1]].append(clause)

        # A complete Horn closure is used only as a sound pruning table. Goals
        # in the table are still proved through the recursive AND/OR procedure;
        # goals outside it cannot have a proof and are rejected immediately.
        self.derivable, _, _ = _forward_chain_closure(kb)
        self.proved = set(self.facts)
        self.not_entailed = set()
        self.proof_rule = {}
        self.failed_attempts = {}

    def entails(self, query):
        if query in self.proved:
            return True
        if query in self.not_entailed:
            return False

        result = self._prove(query, set())
        if not result:
            # Cache failure only after a complete top-level search. Nested
            # failures are path-dependent and are never cached globally.
            self.not_entailed.add(query)
        return result

    def _prove(self, goal, visiting):
        if goal in self.proved:
            return True
        if goal in self.not_entailed:
            return False
        if goal not in self.derivable:
            return False
        if goal in visiting:
            return False

        next_visiting = set(visiting)
        next_visiting.add(goal)
        failures = []

        # OR across rules whose conclusion matches the current goal.
        candidate_rules = self.rules_by_head.get(goal, ())
        for rule in candidate_rules:
            premises = tuple(conjuncts(rule.args[0]))
            if any(premise not in self.derivable for premise in premises):
                failures.append((rule, next(
                    premise for premise in premises if premise not in self.derivable
                )))
                continue
            failed_premise = None

            # AND across all premises of one candidate rule.
            for premise in premises:
                if not self._prove(premise, next_visiting):
                    failed_premise = premise
                    break

            if failed_premise is None:
                self.proved.add(goal)
                self.proof_rule[goal] = (rule, premises)
                return True

            failures.append((rule, failed_premise))

        self.failed_attempts[goal] = failures
        return False

    def explanation(self, query, max_depth=8):
        entailed = self.entails(query)
        if entailed:
            return self._proof_tree(query, set(), 0, max_depth)

        failures = self.failed_attempts.get(query, ())
        if not failures:
            derived_failures = []
            for rule in self.rules_by_head.get(query, ()):
                premises = tuple(conjuncts(rule.args[0]))
                missing = next(
                    (premise for premise in premises if premise not in self.derivable),
                    None,
                )
                if missing is not None:
                    derived_failures.append((rule, missing))
            failures = derived_failures
        return {
            'goal': str(query),
            'status': 'not_entailed',
            'candidate_rule_count': len(self.rules_by_head.get(query, ())),
            'failed_premises': [str(item[1]) for item in failures[:12]],
        }

    def _proof_tree(self, goal, seen, depth, max_depth):
        if goal in self.facts:
            return {'goal': str(goal), 'status': 'fact', 'premises': []}
        if goal in seen:
            return {'goal': str(goal), 'status': 'shared', 'premises': []}
        if depth >= max_depth:
            return {'goal': str(goal), 'status': 'proved', 'premises': []}

        proof = self.proof_rule.get(goal)
        if proof is None:
            return {'goal': str(goal), 'status': 'proved', 'premises': []}

        rule, premises = proof
        next_seen = set(seen)
        next_seen.add(goal)
        return {
            'goal': str(goal),
            'status': 'rule',
            'rule': str(rule),
            'premises': [
                self._proof_tree(premise, next_seen, depth + 1, max_depth)
                for premise in premises
            ],
        }


def _backward_chainer(kb):
    engine = getattr(kb, '_sudoku_backward_chainer', None)
    if engine is None or engine.clause_count != len(kb.clauses):
        engine = _BackwardChainer(kb)
        kb._sudoku_backward_chainer = engine
    return engine


def pl_bc_entails(kb, query):
    """Return whether ``query`` follows by recursive backward chaining."""
    return _backward_chainer(kb).entails(query)


def pl_bc_entails_with_trace(kb, query, max_depth=8):
    """Return the BC verdict and a structured proof explanation."""
    engine = _backward_chainer(kb)
    result = engine.entails(query)
    return result, engine.explanation(query, max_depth=max_depth)


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the grid by trying candidates with recursive backward chaining."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = {}

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    grid[(r, c)] = v
                    break

    return grid


def _decode_atom(proposition):
    name = str(proposition)
    for prefix in ('Is', 'Not'):
        if name.startswith(prefix):
            parts = name[len(prefix):].split('_')
            if len(parts) == 3:
                return prefix, int(parts[0]), int(parts[1]), int(parts[2])
    return None


def _peer_scope(target_r, target_c, source_r, source_c, box_h, box_w):
    if target_r == source_r and target_c == source_c:
        return 'same cell'
    if target_r == source_r:
        return 'row'
    if target_c == source_c:
        return 'column'
    same_box = (
        (target_r - 1) // box_h == (source_r - 1) // box_h
        and (target_c - 1) // box_w == (source_c - 1) // box_w
    )
    return 'box' if same_box else 'derived chain'


def solve_full_grid_fc_with_trace(n, box_h, box_w, givens):
    """Return the FC solution and actual rule-firing trace for tutor mode."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    inferred, support, firing_order = _forward_chain_closure(kb)
    grid = dict(givens)
    trace = []

    for conclusion in firing_order:
        decoded = _decode_atom(conclusion)
        if decoded is None or decoded[0] != 'Is':
            continue

        _, r, c, v = decoded
        if (r, c) in grid:
            continue

        evidence = []
        for premise in support.get(conclusion, ()):
            premise_decoded = _decode_atom(premise)
            source_premises = support.get(premise, ())
            source_decoded = _decode_atom(source_premises[0]) if source_premises else None
            item = {'premise': str(premise)}
            if premise_decoded is not None:
                item['eliminated_value'] = premise_decoded[3]
            if source_decoded is not None and source_decoded[0] == 'Is':
                _, sr, sc, sv = source_decoded
                item.update({
                    'source': str(source_premises[0]),
                    'source_cell': (sr, sc),
                    'source_value': sv,
                    'scope': _peer_scope(r, c, sr, sc, box_h, box_w),
                })
            evidence.append(item)

        before = dict(grid)
        grid[(r, c)] = v
        trace.append({
            'algorithm': 'Forward Chaining',
            'step': len(trace) + 1,
            'cell': (r, c),
            'value': v,
            'grid_before': before,
            'grid_after': dict(grid),
            'rule': f"{' & '.join(str(p) for p in support.get(conclusion, ()))} ==> {conclusion}",
            'evidence': evidence,
            'peer_cells': [item['source_cell'] for item in evidence if 'source_cell' in item],
            'summary': (
                f'All {n - 1} alternative values were eliminated, so cell '
                f'({r}, {c}) is entailed to be {v}.'
            ),
        })

    return _grid_from_inferred(n, inferred), trace


def _fact_cells_from_tree(tree):
    cells = []
    if tree.get('status') == 'fact':
        decoded = _decode_atom(tree.get('goal', ''))
        if decoded is not None and decoded[0] == 'Is':
            cells.append((decoded[1], decoded[2]))
    for child in tree.get('premises', ()):
        cells.extend(_fact_cells_from_tree(child))
    return cells


def solve_full_grid_bc_with_trace(n, box_h, box_w, givens):
    """Return the BC solution and a proof tree for each solved cell."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    grid = dict(givens)
    trace = []

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in givens:
                continue
            for v in range(1, n + 1):
                query = atom('Is', r, c, v)
                if pl_bc_entails(kb, query):
                    _, proof = pl_bc_entails_with_trace(kb, query, max_depth=3)
                    before = dict(grid)
                    grid[(r, c)] = v
                    trace.append({
                        'algorithm': 'Backward Chaining',
                        'step': len(trace) + 1,
                        'cell': (r, c),
                        'value': v,
                        'grid_before': before,
                        'grid_after': dict(grid),
                        'proof': proof,
                        'peer_cells': _fact_cells_from_tree(proof),
                        'summary': (
                            f'The recursive proof for Is{r}_{c}_{v} succeeded: '
                            'one candidate rule had every premise proved.'
                        ),
                    })
                    break

    return grid, trace
