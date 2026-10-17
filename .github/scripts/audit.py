#!/usr/bin/env python3
"""Contrôles maison de la CI de Nebula (stdlib uniquement).

Ne regarde que les fichiers suivis par git (`git ls-files`), donc rien
de ce qui est ignoré ou local. Code de sortie 1 si au moins un contrôle
échoue ; les avertissements ne font pas échouer.

Usage : python .github/scripts/audit.py [racine_du_depot]
"""
from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Racine : argument optionnel, sinon le dépôt qui contient ce script.
ROOT = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
        else Path(__file__).resolve().parents[2])
DASH = ROOT / "dashboard"
TIRET_LONG = "\u2014"

erreurs: list[str] = []
avertissements: list[str] = []


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True).stdout


def fichiers_suivis() -> list[str]:
    sortie = git("ls-files", "-z").decode("utf-8", "replace")
    return [p for p in sortie.split("\0") if p and (ROOT / p).is_file()]


def fichiers_skip_worktree() -> set[str]:
    """Fichiers marqués skip-worktree (étiquette 'S') : sur le poste de
    l'auteur, le disque porte des données perso, seul l'index est publié."""
    sortie = git("ls-files", "-v", "-z").decode("utf-8", "replace")
    return {e[2:] for e in sortie.split("\0") if e.startswith("S ")}


SKIP = fichiers_skip_worktree()


def lire(rel: str) -> str | None:
    """Texte UTF-8 du fichier (version indexée si skip-worktree), ou None
    s'il est binaire / illisible."""
    try:
        if rel in SKIP:
            return git("show", f":{rel}").decode("utf-8")
        return (ROOT / rel).read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def titre(txt: str) -> None:
    print(f"\n== {txt}")


# ---------------------------------------------------------------- 1
def controle_tiret_long(fichiers: list[str]) -> None:
    titre("1. Tiret long U+2014")
    lignes = (lire("CHANGELOG.md") or "").splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.startswith("## ")), None)
    if debut is None:
        erreurs.append("CHANGELOG.md : aucune section '## ' trouvée")
    else:
        fin = next((i for i in range(debut + 1, len(lignes))
                    if lignes[i].startswith("## ")), len(lignes))
        for i in range(debut, fin):
            if TIRET_LONG in lignes[i]:
                erreurs.append(f"CHANGELOG.md:{i + 1} : tiret long en section de tête")
    # Avertissement : .py et .js de dashboard/, y compris dashcore/ (il en existe
    # d'anciens : une dizaine de fichiers). Seul le CHANGELOG fait échouer.
    anciens = 0
    for rel in fichiers:
        if rel.startswith("dashboard/") and rel.endswith((".py", ".js")):
            nb = (lire(rel) or "").count(TIRET_LONG)
            if nb:
                anciens += nb
                avertissements.append(f"{rel} : {nb} tiret(s) long(s) (ancien)")
    print(f"   anciennes occurrences (avertissement) : {anciens} occurrence(s)")


# ---------------------------------------------------------------- 2
# `exemple` couvre aussi `git.exemple.lan`. Les exemples génériques
# (exemple.lan, nas.lan) ne correspondent à aucun motif : ils passent, tout
# comme le gabarit `C:\Users\<user>\` (espace réservé après Users\).
REFERENCES_INTERNES = re.compile(r"exemple|C:\\Users\\(?!<)|Antoine", re.IGNORECASE)
# Exemptés : la CI elle-même (elle cite les motifs) et la licence
# (nom du détenteur du droit d'auteur).
EXEMPTES_REFERENCES = {"LICENSE"}


def controle_references(fichiers: list[str]) -> None:
    titre("2. Références internes")
    trouve = 0
    for rel in fichiers:
        if rel.startswith(".github/") or rel in EXEMPTES_REFERENCES:
            continue
        txt = lire(rel)
        if txt is None:
            continue
        for n, ligne in enumerate(txt.splitlines(), 1):
            m = REFERENCES_INTERNES.search(ligne)
            if m:
                trouve += 1
                erreurs.append(f"{rel}:{n} : référence interne '{m.group(0)}'")
    print(f"   {trouve} occurrence(s)")


# ---------------------------------------------------------------- 3
# Suivis mais vides par conception (gabarits de départ du dépôt public) :
# leur contenu indexé doit rester sans entrée.
GABARITS_VIDES = {
    "dashboard/data/workspaces.json": "workspaces",
    "mcp/registry.json": "mcps",
}
INTERDITS = [
    "dashboard/data/ui_state.json",
    "dashboard/data/improve_auto.json",
    "dashboard/data/improve-jobs/*",
    "*/improve_auto.json",
    "*.env.local", "*.env.local.*",
    "*.credentials*",
    "memory/journal.md",
    "mcp/registry.json.bak",
]


def controle_donnees(fichiers: list[str]) -> None:
    titre("3. Fichiers de données personnelles")
    avant = len(erreurs)
    for rel in fichiers:
        # Les exemples (.env.local.example) sont publiés volontairement.
        if rel.endswith(".example") or rel in GABARITS_VIDES:
            continue
        for motif in INTERDITS:
            if fnmatch.fnmatch(rel, motif):
                erreurs.append(f"{rel} : fichier de données personnelles suivi")
                break
    for rel, cle in GABARITS_VIDES.items():
        if rel not in fichiers:
            continue
        try:
            # Contenu de l'index, pas du disque : sur le poste de l'auteur
            # ces fichiers portent des données réelles (skip-worktree).
            data = json.loads(git("show", f":{rel}"))
        except (subprocess.CalledProcessError, ValueError) as exc:
            erreurs.append(f"{rel} : illisible ({exc})")
            continue
        if data.get(cle):
            erreurs.append(f"{rel} : gabarit suivi non vide ('{cle}' contient des entrées)")
    print("   ok" if len(erreurs) == avant else "   voir échecs")


# ---------------------------------------------------------------- 4
def controle_version() -> None:
    titre("4. Version == CHANGELOG")
    init = (DASH / "dashcore" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init)
    c = re.search(r"^## (\d+\.\d+\.\d+)\b",
                  (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.MULTILINE)
    if not m or not c:
        erreurs.append("version introuvable (__init__.py ou CHANGELOG.md)")
        return
    print(f"   __version__ = {m.group(1)} ; CHANGELOG = {c.group(1)}")
    if m.group(1) != c.group(1):
        erreurs.append(f"__version__ {m.group(1)} != CHANGELOG {c.group(1)}")


# ---------------------------------------------------------------- 5
def controle_import() -> None:
    titre("5. import server")
    r = subprocess.run([sys.executable, "-c", "import server"], cwd=DASH,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        erreurs.append("import server a échoué :\n" + (r.stderr or r.stdout).strip())
    else:
        print("   ok")


# ---------------------------------------------------------------- 6
def controle_js(fichiers: list[str]) -> None:
    titre("6. node --check")
    node = shutil.which("node")
    if not node:
        avertissements.append("node absent : contrôle JS ignoré")
        print("   node absent, ignoré")
        return
    js = [f for f in fichiers if f.startswith("dashboard/") and f.endswith(".js")]
    for rel in js:
        r = subprocess.run([node, "--check", str(ROOT / rel)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            erreurs.append(f"{rel} : syntaxe JS invalide\n{r.stderr.strip()}")
    print(f"   {len(js)} fichier(s) vérifié(s)")


def main() -> int:
    # Sortie UTF-8 même sous la console Windows (cp1252).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    fichiers = fichiers_suivis()
    print(f"Dépôt : {ROOT} ({len(fichiers)} fichiers suivis)")
    controle_tiret_long(fichiers)
    controle_references(fichiers)
    controle_donnees(fichiers)
    controle_version()
    controle_import()
    controle_js(fichiers)

    print("\n== Bilan")
    for a in avertissements:
        print(f"AVERT  {a}")
    for e in erreurs:
        print(f"ECHEC  {e}")
    print(f"{len(erreurs)} échec(s), {len(avertissements)} avertissement(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
