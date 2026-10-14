# Contributing

- Add a knowledge card: one JSON file in `src/calcaudit/cards/` with `id`, `name`, `equation`, `variables` (symbol to unit),
  `assumptions`, `source`, optional numeric `validity`. Every card needs a source note.
- Add a rule: a function in a pack under `src/calcaudit/packs/` returning `Finding` records, a documented false-alarm
  case in `docs/RULES.md`, and tests in `tests/`.
- Run `python -m unittest discover -s tests` and `python -m calcaudit selftest` before a pull request.
- Test data must be invented or public. Never commit documents, data or parameter values from real projects.
