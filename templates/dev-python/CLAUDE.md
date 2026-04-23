# Workspace — {{label}}

## Contexte
{{description}}

## Structure
- `src/`           — code source
- `tests/`         — tests (pytest)
- `requirements.txt` — dépendances
- `README.md`      — usage

## Tâches fréquentes
1. Ajouter une fonctionnalité avec tests pytest
2. Déboguer une stacktrace
3. Intégrer une API REST (requests + retry)
4. Créer un CLI avec argparse ou click
5. Packager en wheel

## Conventions
- Python 3.10+, type hints sur fonctions publiques
- `logging` (pas `print`) pour tout output
- `requirements.txt` tenu à jour (ou pyproject.toml si poetry/hatch)
- Pas de `except:` nu
- Tests : un fichier `test_<module>.py` par module
- Virtualenv : `python -m venv .venv && .venv\Scripts\activate`
