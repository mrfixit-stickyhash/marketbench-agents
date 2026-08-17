# Agent instructions

Read `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACT.md`, `docs/METRICS.md`, `docs/AUTORESEARCH.md`, and `docs/PROJECT_STATE.md` before changing benchmark behavior.

Non-negotiable boundaries:

- Never expose information whose `available_at` is after the current replay step.
- Decisions execute no earlier than the next bar.
- Keep risk enforcement deterministic and outside model control.
- Do not place secrets, private Discord content, licensed datasets or real-wallet signing material in the repository.
- Do not change frozen evaluation code during an AutoResearch candidate experiment.
- Add tests for schema, metric or execution changes.
- Run `python -m unittest discover -s tests -v` before handoff.

Record durable architectural decisions in `docs/`. Local scratch context belongs in `.agent-context/`, which is intentionally ignored and must never contain secrets.
