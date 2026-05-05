# Contributing

## Local Setup

```bash
git clone https://github.com/acefoxy/subtitler.git
cd subtitler
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[sync,hq-sync,docs]
```

## Validation

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build docs:

```bash
mkdocs build --strict
```

## Contribution Scope

Useful contributions include:

- provider reliability improvements
- better sync heuristics and diagnostics
- installation and compatibility documentation
- Windows and macOS validation
- tests for real-world filename parsing edge cases

## Pull Requests

Keep pull requests focused. If behavior changes, update the docs in `README.md` and `docs/` in the same PR.