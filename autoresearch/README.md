# MarketBench AutoResearch harness

This directory contains the human-authored research policy. It does not grant an agent permission to modify the evaluator or test data.

Use an external controller to:

1. create a candidate Git branch;
2. expose only the editable files listed in `program.md`;
3. run fixed-budget MarketBench suites;
4. call `marketbench evaluate-research` against read-only hidden results;
5. keep or revert the candidate;
6. append the experiment, score and Git commit to an audit log.

See `docs/AUTORESEARCH.md` for the complete boundary.
