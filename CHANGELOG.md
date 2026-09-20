# Changelog by Chenhao

## Summary

The project now has:

- a specification-compliant recursive backward-chaining proof procedure;
- direct use of the supplied `pl_fc_entails` in the full-grid forward solver;
- correct solutions for all five supplied puzzles with both algorithms;
- truthful, algorithm-specific reasoning traces;
- an executed English assignment notebook with all five conceptual answers;
- automated regression tests;
- stronger Streamlit validation, caching, accessibility, and error handling;
- version-bounded deployment dependencies.

The only remaining external action is deploying the revised commit to Streamlit Community Cloud and replacing the pending URL in the notebook.

## File-by-file changes

### `sudoku_solver.py`

#### Knowledge-base construction

- Preserved the correct general CNF encoding:
  - given facts;
  - one positive at-least-one clause per cell;
  - pairwise at-most-one clauses;
  - row, column, and box uniqueness clauses.
- Preserved duplicate avoidance for box cell pairs already covered by row or column rules.
- Preserved the definite-clause encoding based on explicit `Is` and `Not` atoms, peer elimination, and last-candidate rules.
- Removed the direct standard-library import so this assignment file imports only from `utils.py` and `logic_.py`, as required.

#### Forward chaining

- Added an indexed Horn-rule lookup to avoid the supplied implementation's repeated linear premise scans.
- Added one complete closure pass to identify cell candidates efficiently.
- `solve_full_grid_fc` now confirms every inferred cell value by calling the supplied `pl_fc_entails` function.
- Added consistency detection for cells with multiple entailed values.

#### Backward chaining

- Replaced the previous “backward relevance scan followed by forward chaining” with an actual recursive AND/OR proof procedure.
- Candidate rules are combined with OR semantics.
- Premises within one rule are combined with AND semantics.
- Added a recursion-path set to stop cyclic proof branches.
- Added successful-subgoal memoization and safe top-level negative caching.
- Added a complete Horn-derivability table as sound pruning for impossible candidates. Successful goals are still proved recursively.
- The engine is cached on an unchanged KB so repeated full-grid queries reuse proof work.
- `solve_full_grid_bc` no longer mutates the KB by re-adding already entailed facts.

#### Trace support

- Added structured backward proof explanations.
- Added forward rule-firing traces based on the actual inferred premises and conclusions.
- Added full-grid trace functions for both selected algorithms.
- Trace data uses plain serializable values suitable for the Streamlit interface.

### `sudoku_app.py`

- Rebuilt the app around the revised solver functions.
- Puzzle loading now resolves `puzzles.json` relative to the application file, so the app is not dependent on the current working directory.
- Removed the unused loading of supplied solutions; the app operates only on givens.
- Added explicit grid validation before displaying a success message:
  - all 81 cells must be present;
  - givens must be unchanged;
  - every row, column, and box must contain exactly `1..9`.
- Added cached definite KBs and cached reasoning traces.
- Normal solving no longer pays the additional cost of generating a trace unless the user requests tutor mode.
- Tutor mode now follows the selected algorithm:
  - forward chaining displays real rule firings and their supporting peer facts;
  - backward chaining displays a recursive proof tree.
- Targeted query explanations now come from the actual backward proof.
- Removed fabricated “eliminated through inference chain” statements.
- Changed negative-query wording from “invalid solution value” to the logically accurate “not provable from the current KB.”
- Added representative missing premises for failed queries.
- Replaced hard-coded KB counts with formulas derived from grid and box dimensions.
- Replaced hard-coded “eight alternatives” wording with `n - 1`.
- Added safe handling for empty traces and partial solver results.
- Added accessible table labels and clearer visual legends.

### `Sudoku_Assignment.ipynb`

- Added the previously missing submission notebook to the project.
- Added and executed puzzle loading, KB construction, clause-count validation, all-puzzle solver validation, timing, and 729 backward-entailment checks.
- Added complete answers for:
  1. general versus definite representation;
  2. completeness versus tractability;
  3. backward-chaining pseudocode and termination challenges;
  4. a definite-clause Naked Pairs encoding and its rule-count cost;
  5. data-driven versus goal-driven performa