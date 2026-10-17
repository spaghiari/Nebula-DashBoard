"""Applicateur de diff unifié STRICT, un seul fichier (boucle d'amélioration).

Le diff vient du critique (sortie d'un modèle) : rien n'y est deviné.

  - un seul fichier : deux en-têtes `---` / `+++` exactement, même chemin
    (préfixes `a/` et `b/` retirés) ; création (`/dev/null`) et suppression
    refusées ; plusieurs fichiers refusés ;
  - chemin vérifié AVANT tout accès (`check_rel_path`) : relatif posix, sans
    `\\`, `:`, segment vide, `.` ni `..` ; résolu sous la racine et égal
    au chemin demandé une fois résolu (aucun lien ni jonction, même interne) ;
    puis filtre `allowed(rel)` de l'appelant (liste blanche) ;
  - contexte exact : chaque ligne ` ` et `-` d'un hunk doit se retrouver à
    l'identique. Les numéros de ligne de l'en-tête `@@` sont indicatifs :
    le bloc ancien est cherché à la position annoncée, sinon ailleurs après
    le hunk précédent, et doit alors y être UNIQUE (jamais de fuzz sur le
    contenu) ;
  - fichier jamais modifié en cas d'échec : tout est calculé en mémoire,
    écriture atomique (tmp + os.replace) seulement si tout passe.

Fins de ligne (LF / CRLF), BOM UTF-8 et présence du saut de ligne final du
fichier sont conservés. Stdlib only.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class DiffError(ValueError):
    """Diff refusé (format, chemin, contexte) : aucun fichier n'a été écrit."""


# --- Chemins -------------------------------------------------------------------

def check_rel_path(root: Path, rel: str, strict_case: bool = False) -> Path:
    """Chemin `rel` (posix, relatif à `root`) résolu, ou DiffError.

    Refusé : vide, absolu, `\\`, `:`, NUL, segment vide / `.` / `..` ;
    chemin qui, résolu (liens et jonctions suivis), sort de `root` ou ne
    désigne plus exactement `rel` (lien ou jonction sur le trajet).

    Sous Windows, la comparaison avec le chemin résolu ignore la casse
    (système de fichiers insensible à la casse) ; `strict_case=True` exige
    au contraire que `rel` soit identique, casse comprise, au chemin RÉEL
    résolu (`Critic.md` qui désigne `critic.md` est alors refusé)."""
    if not isinstance(rel, str) or not rel.strip():
        raise DiffError("chemin vide")
    if rel != rel.strip():
        raise DiffError(f"chemin avec espaces de bord refusé : {rel!r}")
    if "\\" in rel or ":" in rel or "\0" in rel:
        raise DiffError(f"chemin refusé (antislash, deux-points ou NUL) : {rel}")
    if rel.startswith("/"):
        raise DiffError(f"chemin absolu refusé : {rel}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise DiffError(f"chemin refusé (segment vide, . ou ..) : {rel}")
    base = Path(root).resolve()
    try:
        target = (base / rel).resolve()
    except (OSError, ValueError) as e:
        raise DiffError(f"chemin non résoluble : {rel} ({e})") from e
    if not target.is_relative_to(base):
        raise DiffError(f"chemin hors du workspace : {rel}")
    got = target.relative_to(base).as_posix()
    same = got.lower() == rel.lower() if sys.platform == "win32" else got == rel
    if not same:
        raise DiffError(f"chemin refusé (lien ou jonction sur le trajet) : {rel}")
    if strict_case and got != rel:
        raise DiffError(f"chemin refusé (casse différente du chemin réel {got}) : {rel}")
    return target


# --- Analyse -------------------------------------------------------------------

def _header_path(line: str, prefix: str) -> str:
    raw = line[len(prefix):].split("\t", 1)[0].strip()
    if raw == "/dev/null":
        return raw
    if raw.startswith(("a/", "b/")):
        raw = raw[2:]
    return raw


def parse_unified_diff(text: str) -> tuple[str, list[dict]]:
    """(chemin, hunks) d'un diff unifié à UN fichier. Hunk = {"start":
    numéro annoncé (1-based), "lines": [(op, texte)]} avec op ∈ ' ', '-', '+'."""
    if not isinstance(text, str) or not text.strip():
        raise DiffError("diff vide")
    lines = text.replace("\r\n", "\n").split("\n")
    old_paths, new_paths = [], []
    hunks: list[dict] = []
    cur = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old_paths.append(_header_path(line, "--- "))
            new_paths.append(_header_path(lines[i + 1], "+++ "))
            cur = None
            i += 2
            continue
        m = _HUNK_RE.match(line)
        if m:
            if not new_paths:
                raise DiffError("hunk avant les en-têtes --- / +++")
            cur = {"start": int(m.group(1)), "lines": []}
            hunks.append(cur)
        elif cur is not None and line[:1] in (" ", "-", "+"):
            cur["lines"].append((line[0], line[1:]))
        elif cur is not None and line.startswith("\\"):
            pass  # « \ No newline at end of file » : fin de fichier conservée
        elif cur is not None and line == "":
            # Ligne vide de contexte dont l'espace initial a été retiré
            # (fréquent dans un diff produit par un modèle), sauf en fin de diff.
            if any(x.strip() for x in lines[i + 1:]):
                cur["lines"].append((" ", ""))
        elif line.startswith(("diff ", "index ", "similarity ", "rename ", "new file",
                              "deleted file", "old mode", "new mode")):
            if line.startswith(("new file", "deleted file", "rename ")):
                raise DiffError("création, suppression ou renommage de fichier refusés")
        elif line.strip():
            if cur is not None:
                raise DiffError(f"ligne de hunk invalide : {line[:80]!r}")
        i += 1
    if len(new_paths) != 1:
        raise DiffError("un seul fichier attendu dans le diff "
                        f"({len(new_paths)} en-têtes --- / +++ trouvés)")
    old, new = old_paths[0], new_paths[0]
    if "/dev/null" in (old, new):
        raise DiffError("création ou suppression de fichier refusées")
    if old != new:
        raise DiffError(f"chemins --- et +++ différents : {old} / {new}")
    if not hunks or not any(op != " " for h in hunks for op, _ in h["lines"]):
        raise DiffError("diff sans modification")
    return new, hunks


# --- Application -----------------------------------------------------------------

def _find_block(src: list[str], block: list[str], expected: int, floor: int) -> int:
    if not block:
        # Hunk de pur ajout : position annoncée (0 = début de fichier).
        pos = max(expected, floor)
        if pos > len(src):
            raise DiffError("position d'ajout au-delà de la fin du fichier")
        return pos
    n = len(block)
    if floor <= expected <= len(src) - n and src[expected:expected + n] == block:
        return expected
    found = [k for k in range(floor, len(src) - n + 1) if src[k:k + n] == block]
    if not found:
        raise DiffError(f"contexte introuvable à l'identique (hunk annoncé ligne {expected + 1})")
    if len(found) > 1:
        raise DiffError(f"contexte ambigu : {len(found)} positions possibles "
                        f"(hunk annoncé ligne {expected + 1})")
    return found[0]


def apply_hunks(original: str, hunks: list[dict]) -> str:
    """Texte après application stricte des hunks (DiffError sinon)."""
    newline = "\r\n" if "\r\n" in original else "\n"
    trailing = original.endswith(("\n",))
    body = original.replace("\r\n", "\n")
    src = body.split("\n")
    if trailing:
        src = src[:-1]
    out: list[str] = []
    pos = 0
    for h in hunks:
        old = [t for op, t in h["lines"] if op in (" ", "-")]
        new = [t for op, t in h["lines"] if op in (" ", "+")]
        at = _find_block(src, old, max(h["start"] - 1, 0) if old else h["start"], pos)
        out.extend(src[pos:at])
        out.extend(new)
        pos = at + len(old)
    out.extend(src[pos:])
    text = newline.join(out)
    if trailing and out:
        text += newline
    return text


def apply_diff(diff_text: str, root: Path, allowed=None, expected_path: str | None = None,
               write: bool = True) -> dict:
    """Applique un diff unifié à un fichier sous `root`.

    `allowed(rel) -> bool` : liste blanche de l'appelant, testée APRÈS la
    vérification du chemin. `expected_path` : chemin annoncé ailleurs (champ
    `target` du critique), doit être identique. `write=False` : calcule sans
    écrire. Retourne {"path", "before", "after"} (textes). DiffError sinon,
    fichier intact."""
    rel, hunks = parse_unified_diff(diff_text)
    if expected_path is not None and rel != expected_path:
        raise DiffError(f"le diff vise {rel}, la cible annoncée est {expected_path}")
    target = check_rel_path(root, rel)
    if allowed is not None and not allowed(rel):
        raise DiffError(f"cible non autorisée : {rel}")
    if not target.is_file():
        raise DiffError(f"fichier cible absent : {rel}")
    raw = target.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        before = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise DiffError(f"fichier cible non UTF-8 : {rel}") from e
    after = apply_hunks(before, hunks)
    if write:
        write_text_atomic(target, after, bom=bom)
    return {"path": rel, "before": before, "after": after}


def write_text_atomic(path: Path, text: str, bom: bool = False) -> None:
    """Écriture atomique (tmp dans le même dossier + os.replace), UTF-8."""
    data = (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
