"""Remappage des chemins absolus entre deux machines (migration d'environnement).

Un chemin source (`C:\\claude-workspace\\mcp\\x`) devient un chemin cible
(`/home/u/nebula/mcp/x`) par PRÉFIXE : la règle la plus spécifique (la plus
longue) gagne, à égalité une règle de l'utilisateur passe avant une règle
automatique. Les séparateurs du reste du chemin suivent le style de la cible
(`/` vers un POSIX, `\\` vers Windows), sauf pour une chaîne qui n'utilisait que
des `/` (clés de `~/.claude.json` sous Windows : on garde les `/`).

Le même principe vaut pour les noms de dossiers de sessions de Claude Code
(`~/.claude/projects/<chemin encodé>`) : l'encodage remplace tout caractère non
alphanumérique par `-`, donc un préfixe de chemin devient un préfixe du nom
encodé et se remappe SANS décoder (le décodage est ambigu dès qu'un segment
contient un `-`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def encode_project_name(path: str) -> str:
    """Nom de dossier de sessions Claude Code pour `path` (cf. pitfalls : tout
    caractère non alphanumérique ASCII devient `-`)."""
    return re.sub(r"[^A-Za-z0-9]", "-", path or "")


def is_windows_style(path: str) -> bool:
    """Chemin à la Windows : lettre de lecteur, UNC ou antislash."""
    p = path or ""
    return bool(re.match(r"^[A-Za-z]:", p)) or p.startswith("\\\\") or "\\" in p


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").rstrip("/")


@dataclass(frozen=True)
class Rule:
    source: str
    target: str
    origin: str = "auto"      # auto | workspace | user


class PathRemapper:
    """Applique une liste de règles préfixe -> préfixe (cf. docstring du module)."""

    def __init__(self, rules: list[Rule]):
        prio = {"workspace": 0, "user": 1, "auto": 2}
        ordered = sorted((r for r in rules if _norm(r.source) and (r.target or "").strip()),
                         key=lambda r: (-len(_norm(r.source)), prio.get(r.origin, 3)))
        cleaned: list[Rule] = []
        seen: set[str] = set()
        for r in ordered:
            f = _norm(r.source)
            key = f.lower() if is_windows_style(r.source) else f
            if key in seen:
                continue          # la règle la plus prioritaire pour ce préfixe est déjà retenue
            seen.add(key)
            if _norm(r.target) == f and r.source == r.target:
                continue          # règle identité : sans effet (mais retient le préfixe)
            cleaned.append(r)
        self.rules = cleaned
        self._regex = self._build(cleaned)

    @staticmethod
    def _build(rules: list[Rule]):
        if not rules:
            return None
        alts = []
        for i, r in enumerate(rules):
            body = "[\\\\/]".join(re.escape(part) for part in _norm(r.source).split("/"))
            flag = "(?i:" if is_windows_style(r.source) else "(?:"
            alts.append(f"(?P<r{i}>{flag}{body}))")
        pattern = (r"(?<![A-Za-z0-9_.\-])(?:" + "|".join(alts) + r")"
                   r"(?P<rest>(?:[\\/][^\s\"'<>|&;,()]*)?)(?![A-Za-z0-9_.\-])")
        return re.compile(pattern)

    def remap_text(self, s: str) -> str:
        """Remappe chaque occurrence d'un préfixe connu dans `s` (chemin entier,
        argument de commande, `cd /d X && Y`...)."""
        if not isinstance(s, str) or not s or self._regex is None:
            return s

        def repl(m: re.Match) -> str:
            idx = next(i for i in range(len(self.rules)) if m.group(f"r{i}") is not None)
            rule = self.rules[idx]
            orig = m.group(0)
            to = rule.target
            if is_windows_style(to):
                sep = "/" if ("/" in orig and "\\" not in orig) else "\\"
            else:
                sep = "/"
            to_norm = _norm(to)
            rest = (m.group("rest") or "").replace("\\", "/")
            return (to_norm + rest).replace("/", sep)

        return self._regex.sub(repl, s)

    def remap_json(self, obj):
        """Copie de `obj` (JSON) dont chaque VALEUR chaîne est remappée ; les
        clés sont laissées telles quelles. Retourne (copie, nombre de valeurs
        modifiées)."""
        count = 0

        def walk(o):
            nonlocal count
            if isinstance(o, str):
                n = self.remap_text(o)
                if n != o:
                    count += 1
                return n
            if isinstance(o, list):
                return [walk(x) for x in o]
            if isinstance(o, dict):
                return {k: walk(v) for k, v in o.items()}
            return o

        return walk(obj), count

    def remap_project_dir_name(self, name: str) -> str:
        """Nom de dossier de sessions après remappage (espace encodé)."""
        low = name.lower()
        for r in self.rules:
            enc = encode_project_name(r.source.rstrip("\\/"))
            if not enc:
                continue
            if low == enc.lower() or low.startswith(enc.lower() + "-"):
                return encode_project_name(r.target.rstrip("\\/")) + name[len(enc):]
        return name


def valid_component(name: str) -> bool:
    """Composant d'archive importable : pas de `..`, séparateur, lecteur (`:`),
    flux de données NTFS ni caractère de contrôle."""
    if not name or name in (".", ".."):
        return False
    if any(c in name for c in ("/", "\\", ":", "\0")):
        return False
    return not any(ord(c) < 32 for c in name)


def split_member_name(name: str) -> list[str] | None:
    """Composants validés d'un nom de membre d'archive, ou None si le nom est
    dangereux (absolu, traversant, ambigu)."""
    if not name or name.startswith("/") or "\\" in name or "\0" in name:
        return None
    parts = name.split("/")
    if parts and parts[-1] == "":
        parts = parts[:-1]          # dossier : « a/b/ »
    if not parts or not all(valid_component(p) for p in parts):
        return None
    return parts
