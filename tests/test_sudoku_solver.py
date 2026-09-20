"""Regression tests for the IT5005 Sudoku solver."""

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from logic_ import PropDefiniteKB, PropKB, expr, pl_fc_entails
from sudoku_solver import (
    _install_fc_index,
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


class SudokuSolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads((PROJECT_ROOT / 'puzzles.json').read_text(encoding='utf-8'))
        cls.n = raw['n']
        cls.box_h = raw['box_h']
        cls.box_w = raw['box_w']
        cls.puzzles = []
        for item in raw['puzzles']:
            givens = {
                tuple(int(part) for part in key.split('_')): value
                for key, value in item['givens'].items()
            }
            solution = {
                tuple(int(part) for part in key.split('_')): value
                for key, value in item['solution'].items()
            }
            cls.puzzles.append((givens, solution))

    def test_atom_format(self):
        self.assertEqual(str(atom('Is', 3, 2, 4)), 'Is3_2_4')
        self.assertEqual(str(atom('Not', 9, 8, 7)), 'Not9_8_7')

    def test_kb_types_counts_and_no_duplicates(self):
        givens, _ = self.puzzles[0]
        general = build_general_kb(self.n, self.box_h, self.box_w, givens)
        definite = build_definite_kb(self.n, self.box_h, self.box_w, givens)
        self.assertIsInstance(general, PropKB)
        self.assertIsInstance(definite, PropDefiniteKB)
        self.assertEqual(len(general.clauses), 10287 + len(givens))
        self.assertEqual(len(definite.clauses), 21141 + len(givens))
        self.assertEqual(len(general.clauses), len(set(general.clauses)))
        self.assertEqual(len(definite.clauses), len(set(definite.clauses)))

    def test_all_puzzles_solve_with_both_algorithms(self):
        for index, (givens, solution) in enumerate(self.puzzles, start=1):
            with self.subTest(puzzle=index, algorithm='FC'):
                self.assertEqual(
                    solve_full_grid_fc(self.n, self.box_h, self.box_w, givens),
                    solution,
                )
            with self.subTest(puzzle=index, algorithm='BC'):
                self.assertEqual(
                    solve_full_grid_bc(self.n, self.box_h, self.box_w, givens),
                    solution,
                )

    def test_backward_chaining_true_and_false_queries(self):
        givens, solution = self.puzzles[0]
        kb = build_definite_kb(self.n, self.box_h, self.box_w, givens)
        for (r, c), correct in solution.items():
            self.assertTrue(pl_bc_entails(kb, atom('Is', r, c, correct)))
            for other in range(1, self.n + 1):
                if other != correct:
                    self.assertFalse(pl_bc_entails(kb, atom('Is', r, c, other)))

    def test_backward_chaining_terminates_on_cycles(self):
        kb = PropDefiniteKB()
        for clause in ['A ==> B', 'B ==> A', 'D ==> A', 'D', 'X ==> Y', 'Y ==> X']:
            kb.tell(expr(clause))
        self.assertTrue(pl_bc_entails(kb, expr('A')))
        self.assertTrue(pl_bc_entails(kb, expr('B')))
        self.assertFalse(pl_bc_entails(kb, expr('X')))
        self.assertFalse(pl_bc_entails(kb, expr('Y')))

    def test_backward_chaining_agrees_with_supplied_forward_chaining(self):
        givens, solution = self.puzzles[0]
        kb = build_definite_kb(self.n, self.box_h, self.box_w, givens)
        _install_fc_index(kb)
        for (r, c), value in list(solution.items())[:12]:
            query = atom('Is', r, c, value)
            self.assertEqual(pl_bc_entails(kb, query), pl_fc_entails(kb, query))

    def test_traces_are_structured_and_match_solutions(self):
        givens, solution = self.puzzles[0]
        fc_grid, fc_trace = solve_full_grid_fc_with_trace(
            self.n, self.box_h, self.box_w, givens
        )
        bc_grid, bc_trace = solve_full_grid_bc_with_trace(
            self.n, self.box_h, self.box_w, givens
        )
        self.assertEqual(fc_grid, solution)
        self.assertEqual(bc_grid, solution)
        self.assertEqual(len(fc_trace), self.n * self.n - len(givens))
        self.assertEqual(len(bc_trace), self.n * self.n - len(givens))
        self.assertTrue(all(item['evidence'] for item in fc_trace))
        self.assertTrue(all('proof' in item for item in bc_trace))

        sample_query = atom('Is', 1, 1, solution[(1, 1)])
        result, explanation = pl_bc_entails_with_trace(
            build_definite_kb(self.n, self.box_h, self.box_w, givens),
            sample_query,
        )
        self.assertTrue(result)
        self.assertIn(explanation['status'], {'fact', 'rule'})


if __name__ == '__main__':
    unittest.main()
