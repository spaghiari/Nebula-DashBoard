"""Échappement HTML de l'interface (analyse statique, sans navigateur).

Pour les fonctions sensibles de `app.js` et `js/pages/team-config.js`
(modale de retrait d'un module et ses écrans, mise à jour après retrait,
modale d'activation, ligne « Modèle et effort » du module claude-team et
sa table, avertissements), chaque
interpolation `${...}` d'un template littéral injecté en HTML doit passer
par `escapeHtml(...)` ou être une valeur sûre explicitement listée (icône
`I.xxx`, nombre calculé, fragment HTML déjà construit dans la fonction,
chaîne fixe, helper qui échappe lui-même). Test de mutation : retirer
n'importe quel `escapeHtml(...)` de ces fonctions fait échouer le contrôle.
"""
from __future__ import annotations

import re
import unittest

from _support import DASHBOARD_DIR

APP_JS = DASHBOARD_DIR / "app.js"
IMPR_JS = DASHBOARD_DIR / "js" / "pages" / "team-config.js"
TOOLS_JS = DASHBOARD_DIR / "js" / "pages" / "tools.js"

# Fonctions contrôlées -> valeurs sûres propres à chacune : identifiants
# (nombres calculés, fragments HTML construits dans la fonction à partir de
# templates eux-mêmes contrôlés), helpers d'HTML dont le corps (contrôlé
# aussi) échappe ce qu'il interpole, et `text_calls` : appels dont l'argument
# template n'est pas injecté tel quel (échappé ou texte seul).
FUNCTIONS = {
    APP_JS: {
        "ovKeepReasonText": {"vars": set(), "helpers": set()},
        "ovPathListHtml": {"vars": set(), "helpers": {"fmt"}},
        "afterOverlayRemoval": {"vars": set(), "helpers": set()},
        "modalRemoveOverlay": {
            "vars": {"nArch", "n", "settingsHtml", "localHtml", "mdHtml", "names", "html"},
            "helpers": {"code", "ovPathListHtml"},
            # `code(p)` échappe son argument (template compris).
            "text_calls": {"code"},
        },
        # `parts` : morceaux du message d'un toast (échappé par toast).
        # `nu`, `nb` : compteurs (longueurs de listes) du message du toast.
        "modalApplyOverlay": {"vars": {"nu", "nb"}, "helpers": {"optList"}, "text_calls": {"parts.push"}},
        "teamSubWarnHtml": {"vars": set(), "helpers": set()},
    },
    TOOLS_JS: {
        "renderClaudePlanCard": {"vars": set(), "helpers": set()},
    },
    IMPR_JS: {
        "teamConfigCard": {"vars": {"basisPill", "rows", "prop", "warnHtml", "pendHtml"},
                           "helpers": {"opt"}},
        "mountTeamConfigRow": {"vars": set(), "helpers": set()},
        "imprWarningsHtml": {"vars": set(), "helpers": set()},
    },
}

# Contexte qui précède un template littéral de premier niveau dont le texte
# n'est PAS injecté en HTML (ou l'est après échappement par le helper).
_NON_HTML_PREFIX = re.compile(
    r"(?:\.title\s*=|\btitle:|\btarget:|\bconst url\s*=|\.textContent\s*=)\s*$")
# Appels dont un argument template n'est pas injecté tel quel en HTML :
# `btn` et `toast*` échappent leur libellé (js/utils.js, js/toast.js), les
# URL d'API ne sont pas du HTML, `escapeHtml` échappe. Les helpers listés par
# fonction (`code`...) s'ajoutent à cette liste.
_NON_HTML_CALLS = {"btn", "toast", "toastErr", "toastOk", "escapeHtml",
                   "API.get", "API.post", "API.postStatus", "API.del"}
_IDENT = r"[A-Za-z_$][\w$]*"


# --- Analyse lexicale minimale (chaînes, templates, commentaires, regex) -----

def _skip_string(src: str, i: int) -> int:
    q = src[i]
    i += 1
    while i < len(src):
        if src[i] == "\\":
            i += 2
            continue
        if src[i] == q:
            return i + 1
        i += 1
    raise ValueError("chaîne non terminée")


def _regex_allowed(src: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    return j < 0 or src[j] in "(,=:[!&|?{};+-*%<>~^" or src[max(0, j - 5):j + 1] == "return"


def _skip_regex(src: str, i: int) -> int:
    i += 1
    in_class = False
    while i < len(src):
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            i += 1
            while i < len(src) and src[i].isalpha():
                i += 1
            return i
        i += 1
    raise ValueError("regex non terminée")


def _parse_template(src: str, i: int, out: list, parent, calls=()) -> int:
    """Template littéral à `src[i] == '`'` : ajoute à `out` un dict
    {start, end, interps: [(debut, fin)], parent, calls} et ses templates
    imbriqués (`calls` = appels ouverts autour du template, même segment)."""
    tpl = {"start": i, "end": None, "interps": [], "parent": parent, "calls": tuple(calls)}
    out.append(tpl)
    j = i + 1
    while j < len(src):
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            tpl["end"] = j + 1
            return j + 1
        if c == "$" and src[j + 1:j + 2] == "{":
            k = j + 2
            end = _skip_code(src, k, "}", out, (tpl, len(tpl["interps"])))
            tpl["interps"].append((k, end))
            j = end + 1
            continue
        j += 1
    raise ValueError("template non terminé")


def _skip_code(src: str, i: int, closer: str | None, out: list, parent=None) -> int:
    """Avance jusqu'au `closer` de même niveau (ou la fin) ; collecte les
    templates rencontrés dans `out`. Retourne l'index du `closer`."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    calls: list[str | None] = []
    while i < len(src):
        c = src[i]
        if c in "'\"":
            i = _skip_string(src, i)
            continue
        if c == "`":
            i = _parse_template(src, i, out, parent, [n for n in calls if n])
            continue
        if c == "/" and src[i + 1:i + 2] == "/":
            nl = src.find("\n", i)
            i = len(src) if nl < 0 else nl
            continue
        if c == "/" and src[i + 1:i + 2] == "*":
            i = src.index("*/", i) + 2
            continue
        if c == "/" and _regex_allowed(src, i):
            i = _skip_regex(src, i)
            continue
        if c in pairs:
            stack.append(pairs[c])
            m = re.search(r"([\w$][\w$.]*)\s*$", src[max(0, i - 80):i]) if c == "(" else None
            calls.append(m.group(1) if m else None)
        elif c in ")]}":
            if not stack:
                if c == closer:
                    return i
                raise ValueError(f"fermeture inattendue {c!r} à {i}")
            calls.pop()
            if stack.pop() != c:
                raise ValueError(f"fermeture mal appariée {c!r} à {i}")
        i += 1
    if closer is None:
        return i
    raise ValueError(f"{closer!r} introuvable")


def function_source(src: str, name: str) -> str:
    """Source complète de `function name(...) {...}` (async compris)."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        raise AssertionError(f"fonction {name} introuvable")
    close_paren = _skip_code(src, m.end(), ")", [])
    brace = src.index("{", close_paren)
    end = _skip_code(src, brace + 1, "}", [])
    return src[m.start():end + 1]


# --- Règles de sûreté d'une interpolation -------------------------------------

def _reduce(expr: str) -> str:
    """Expression avec templates imbriqués -> `T` et chaînes -> `S`
    (les templates imbriqués sont contrôlés pour eux-mêmes)."""
    out, i = [], 0
    while i < len(expr):
        c = expr[i]
        if c in "'\"":
            i = _skip_string(expr, i)
            out.append("S")
        elif c == "`":
            i = _parse_template(expr, i, [], None)
            out.append("T")
        else:
            out.append(c)
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _top_level(expr: str, chars: str) -> list[int]:
    depth, idx = 0, []
    for i, c in enumerate(expr):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c in chars:
            idx.append(i)
    return idx


def _strip_parens(e: str) -> str:
    while e.startswith("(") and e.endswith(")") and _skip_code(e, 1, ")", []) == len(e) - 1:
        e = e[1:-1].strip()
    return e


def _single_call(e: str, names) -> bool:
    m = re.match(r"(" + "|".join(re.escape(n) for n in names) + r")\(", e) if names else None
    return bool(m) and _skip_code(e, m.end(), ")", []) == len(e) - 1


def is_safe(expr: str, cfg: dict) -> bool:
    e = _strip_parens(_reduce(expr) if ("`" in expr or "'" in expr or '"' in expr) else
                      re.sub(r"\s+", " ", expr).strip())
    if e in ("T", "S"):
        return True
    if _single_call(e, ["escapeHtml"]) or _single_call(e, sorted(cfg["helpers"])):
        return True
    if re.fullmatch(r"I\." + _IDENT, e) or e in cfg["vars"]:
        return True
    # Nombre calculé : longueur d'une liste.
    if re.fullmatch(r"(?:" + _IDENT + r"(?:\." + _IDENT + r")*|\(" + _IDENT
                    + r"(?:\." + _IDENT + r")* \|\| \[\]\))\.length", e):
        return True
    # Ternaire : seules les branches sont rendues.
    q = _top_level(e, "?")
    if q:
        rest = e[q[0] + 1:]
        depth_q, split = 0, None
        for i in _top_level(rest, "?:"):
            if rest[i] == "?":
                depth_q += 1
            elif depth_q == 0:
                split = i
                break
            else:
                depth_q -= 1
        if split is not None:
            return is_safe(rest[:split], cfg) and is_safe(rest[split + 1:], cfg)
    # `liste.map(x => <sûr>).join(S)`.
    m = re.fullmatch(r".*\.map\((.*)\)\.join\(S?\)", e)
    if m:
        arrows = [i for i in _top_level(m.group(1), "=") if m.group(1)[i:i + 2] == "=>"]
        if arrows:
            return is_safe(m.group(1)[arrows[-1] + 2:], cfg)
    return False


def violations(fn_src: str, cfg: dict) -> list[str]:
    """Interpolations non sûres des templates HTML de `fn_src`."""
    tpls: list = []
    _skip_code(fn_src, 0, None, tpls)

    non_html = _NON_HTML_CALLS | set(cfg.get("text_calls", ()))

    def html_context(t) -> bool:
        while True:
            if non_html & set(t["calls"]):
                return False
            if t["parent"] is None:
                return not _NON_HTML_PREFIX.search(fn_src[:t["start"]])
            t = t["parent"][0]

    bad = []
    for t in tpls:
        if not html_context(t):
            continue
        for a, b in t["interps"]:
            expr = fn_src[a:b]
            if not is_safe(expr, cfg):
                line = fn_src.count("\n", 0, a) + 1
                bad.append(f"ligne +{line} : ${{{expr.strip()}}}")
    return bad


def _escape_calls(fn_src: str) -> list[tuple[int, int]]:
    """(début, fin) de chaque appel `escapeHtml(...)` de la fonction."""
    out = []
    for m in re.finditer(r"\bescapeHtml\(", fn_src):
        out.append((m.start(), _skip_code(fn_src, m.end(), ")", []) + 1))
    return out


class FrontEscapingTests(unittest.TestCase):
    def _sources(self):
        for path, fns in FUNCTIONS.items():
            src = path.read_text(encoding="utf-8")
            for name, cfg in fns.items():
                yield path.name, name, function_source(src, name), cfg

    def test_interpolations_echappees(self):
        for fname, name, fn_src, cfg in self._sources():
            with self.subTest(fichier=fname, fonction=name):
                self.assertEqual(violations(fn_src, cfg), [])

    def test_mutation_escape_retire_detecte(self):
        """Retirer un seul escapeHtml(...) d'une fonction contrôlée fait
        apparaître au moins une violation."""
        total = 0
        for fname, name, fn_src, cfg in self._sources():
            for a, b in _escape_calls(fn_src):
                inner = fn_src[a + len("escapeHtml("):b - 1]
                mutated = fn_src[:a] + "(" + inner + ")" + fn_src[b:]
                total += 1
                with self.subTest(fichier=fname, fonction=name, appel=fn_src[a:b][:60]):
                    self.assertTrue(violations(mutated, cfg),
                                    "escapeHtml retiré sans être détecté")
        self.assertGreater(total, 30)

    def test_detecte_interpolation_brute(self):
        cfg = {"vars": set(), "helpers": set()}
        self.assertTrue(violations("function f(x) { el.innerHTML = `<b>${x.label}</b>`; }", cfg))
        self.assertTrue(violations("function f(x) { el.innerHTML = `${x ? `<i>${x.id}</i>` : ''}`; }", cfg))
        self.assertEqual(violations(
            "function f(x) { el.innerHTML = `${I.alert}${x ? `<i>${escapeHtml(x.id)}</i>` : ''}`;"
            " toast(`ok ${x.id}`); }", cfg), [])


class ActivationModalPendingTests(unittest.TestCase):
    """Modale d'activation pendant une itération /improve en attente :
    sélecteurs modèle et effort désactivés, bandeau, rien envoyé."""

    def test_modale_activation_verrouillee_si_attente(self):
        fn = function_source(APP_JS.read_text(encoding="utf-8"), "modalApplyOverlay")
        m = re.search(r"const pend = hasTeam && ov\.active \? \(wsTeam\.pending \|\| null\) : null;", fn)
        self.assertTrue(m, "état d'attente lu depuis GET /team")
        self.assertEqual(fn.count("${pend ? ' disabled' : ''}"), 2)  # modèle ET effort
        self.assertIn("${pend ? `<p class=\"impr-team-msg warn\"", fn)
        # Modèles envoyés seulement hors attente, efforts non lus en attente.
        self.assertRegex(fn, r"if \(!pend\) \{\s*payload\.models = \{\};")
        self.assertEqual(fn.count("payload.models = {}"), 1)
        self.assertIn("for (const sel of pend ? [] : body.querySelectorAll('select[data-effort]'))", fn)


if __name__ == "__main__":
    unittest.main()
