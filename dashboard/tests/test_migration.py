"""Migration d'environnement : chiffrement, remappage, export -> import.

Couvre : schéma de chiffrement (aller-retour, mauvaise phrase de passe, octet
altéré, troncature, en-tête hostile, étiquette vérifiée AVANT tout
déchiffrement), remappage de chemins (Windows -> Windows, -> POSIX, noms de
dossiers de sessions), aller-retour complet export -> import sur un arbre
temporaire, aperçu sans écriture, conflits jamais écrasés en silence (sauvegarde
horodatée), plan périmé, archive piégée (zip-slip, liens, entrées inconnues),
secrets absents du clair, de l'aperçu, des journaux et des erreurs.
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import os
import re
import tarfile
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    ROOT, SANDBOX, ServerProcess, make_workspace, read_json_file, reset_sandbox, rmtree,
    write_json_file,
)
from dashcore import api_migration, migration, migration_crypto as mc
from dashcore import migration_import as mi
from dashcore.config import (
    BACKUPS_DIR, CLAUDE_HOME, CLAUDE_JSON, CLAUDE_PROJECTS, ENV_FILE, MCP_REGISTRY,
    SCRIPTS_DIR, WORKSPACES_JSON,
)
from dashcore.migration_paths import (
    PathRemapper, Rule, encode_project_name, split_member_name,
)

PASS = "correct horse battery staple"
SECRET = "sup3r-secret-value-xyz-9137"
FAST = 100_000          # itérations PBKDF2 minimales acceptées : tests rapides


def _tree(root: Path) -> dict[str, bytes]:
    """Contenu d'une arborescence : {chemin relatif: octets} (dossiers vides inclus)."""
    out = {}
    if not root.exists():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root).as_posix()
        out[rel + "/"] = b""
        for fn in filenames:
            p = Path(dirpath) / fn
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def _make_dir_link(link: Path, target: Path) -> bool:
    """Lien de dossier : symlink, sinon jonction NTFS (sans privilège sous Windows)."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if sys_platform() == "win32":
        import subprocess
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, text=True)
        return r.returncode == 0
    return False


# ---------------------------------------------------------------------------
# Chiffrement
# ---------------------------------------------------------------------------

def _write_tar_archive(path: Path, passphrase: str, members: list[tuple[str, bytes]],
                       iterations: int = FAST) -> None:
    w = mc.EncryptingWriter(open(path, "wb"), passphrase, iterations)
    gz = gzip.GzipFile(fileobj=w, mode="wb", compresslevel=1, mtime=0)
    tf = tarfile.open(fileobj=gz, mode="w|")
    for name, data in members:
        ti = tarfile.TarInfo(name)
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    tf.close()
    gz.close()
    w.close()


def _read_all(path: Path, passphrase: str) -> list[tuple[str, bytes]]:
    out = []
    with mc.open_archive(path, passphrase) as oa:
        gz = gzip.GzipFile(fileobj=oa.reader, mode="rb")
        tf = tarfile.open(fileobj=gz, mode="r|")
        for m in tf:
            if m.isreg():
                out.append((m.name, tf.extractfile(m).read()))
        oa.finish()
    return out


class CryptoTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.dir = SANDBOX / "crypto"
        rmtree(self.dir)
        self.dir.mkdir()
        self.path = self.dir / "a.nebmig"
        self.members = [("a.bin", os.urandom(2_500_000) + b"Z" * 1_000_000), ("b.txt", b"bonjour")]
        _write_tar_archive(self.path, PASS, self.members)

    def tearDown(self):
        rmtree(self.dir)

    def test_aller_retour_en_flux(self):
        self.assertEqual(_read_all(self.path, PASS), self.members)

    def test_clair_absent_du_fichier(self):
        raw = self.path.read_bytes()
        self.assertNotIn(b"bonjour", raw)
        self.assertNotIn(b"ZZZZZZZZ", raw)
        self.assertEqual(raw[:8], b"NEBULAMG")

    def test_sel_et_nonce_uniques(self):
        other = self.dir / "b.nebmig"
        _write_tar_archive(other, PASS, self.members)
        a, b = self.path.read_bytes(), other.read_bytes()
        self.assertNotEqual(a[16:72], b[16:72])           # sel + nonce
        self.assertNotEqual(a[80:200], b[80:200])         # flux chiffré

    def test_mauvaise_phrase_de_passe(self):
        with self.assertRaises(mc.MigrationAuthError):
            mc.open_archive(self.path, "mauvaise phrase de passe")

    def test_octet_altere_refuse_avant_tout_dechiffrement(self):
        raw = bytearray(self.path.read_bytes())
        raw[1000] ^= 0x01
        bad = self.dir / "bad.nebmig"
        bad.write_bytes(raw)
        with mock.patch.object(mc._DecryptRaw, "__init__", side_effect=AssertionError("déchiffrement")):
            with self.assertRaises(mc.MigrationAuthError):
                mc.open_archive(bad, PASS)

    def test_en_tete_altere_refuse(self):
        raw = bytearray(self.path.read_bytes())
        raw[17] ^= 0x01                                    # un octet du sel
        bad = self.dir / "bad.nebmig"
        bad.write_bytes(raw)
        with self.assertRaises(mc.MigrationAuthError):
            mc.open_archive(bad, PASS)

    def test_etiquette_alteree_refusee(self):
        raw = bytearray(self.path.read_bytes())
        raw[-1] ^= 0x01
        bad = self.dir / "bad.nebmig"
        bad.write_bytes(raw)
        with self.assertRaises(mc.MigrationAuthError):
            mc.open_archive(bad, PASS)

    def test_troncature_refusee(self):
        raw = self.path.read_bytes()
        for cut in (len(raw) - 1, len(raw) - 40, len(raw) // 2, 90):
            bad = self.dir / "bad.nebmig"
            bad.write_bytes(raw[:cut])
            with self.assertRaises(mc.MigrationError):
                mc.open_archive(bad, PASS)
        bad.write_bytes(raw[:50])
        with self.assertRaises(mc.MigrationFormatError):
            mc.open_archive(bad, PASS)

    def test_en_tetes_hostiles(self):
        raw = bytearray(self.path.read_bytes())
        for offset, value, exc in (
            (0, 0x00, mc.MigrationFormatError),            # magic
            (9, 99, mc.MigrationVersionError),             # version future
            (10, 7, mc.MigrationFormatError),              # KDF inconnu
            (11, 7, mc.MigrationFormatError),              # chiffrement inconnu
        ):
            bad = bytearray(raw)
            bad[offset] = value
            p = self.dir / "h.nebmig"
            p.write_bytes(bad)
            with self.assertRaises(exc):
                mc.open_archive(p, PASS)
        # itérations hors bornes (trop faibles / trop fortes) : jamais dérivé
        for iters in (1, 2**31):
            bad = bytearray(raw)
            bad[12:16] = iters.to_bytes(4, "big")
            p = self.dir / "h.nebmig"
            p.write_bytes(bad)
            with mock.patch("hashlib.pbkdf2_hmac", side_effect=AssertionError("dérivation")):
                with self.assertRaises(mc.MigrationFormatError):
                    mc.open_archive(p, PASS)

    def test_fichier_modifie_entre_les_deux_passes(self):
        """Le HMAC est recalculé pendant la lecture : un fichier changé après la
        première passe est refusé avant la fin du flux."""
        with mc.open_archive(self.path, PASS) as oa:
            gz = gzip.GzipFile(fileobj=oa.reader, mode="rb")
            tf = tarfile.open(fileobj=gz, mode="r|")
            first = next(iter(tf))
            self.assertEqual(first.name, "a.bin")
            raw = bytearray(self.path.read_bytes())
            raw[len(raw) // 2] ^= 0x01
            with open(self.path, "r+b") as f:             # même fichier, modifié sous le lecteur
                f.write(bytes(raw))
            with self.assertRaises(mc.MigrationError):
                tf.extractfile(first).read()
                for m in tf:
                    tf.extractfile(m).read()
                oa.finish()

    def test_phrase_vide_refusee(self):
        with self.assertRaises(mc.MigrationAuthError):
            mc.open_archive(self.path, "")

    def test_normalisation_unicode_de_la_phrase(self):
        p = self.dir / "u.nebmig"
        _write_tar_archive(p, "e\u0301te-secret-longue", [("x", b"1")])      # e + accent combinant
        self.assertEqual(_read_all(p, "\u00e9te-secret-longue"), [("x", b"1")])  # é précomposé


# ---------------------------------------------------------------------------
# Remappage de chemins
# ---------------------------------------------------------------------------

class PathTests(unittest.TestCase):
    def test_windows_vers_autre_lecteur(self):
        r = PathRemapper([Rule("C:\\claude-workspace", "D:\\nebula"),
                          Rule("C:\\Users\\alice", "C:\\Users\\bob")])
        self.assertEqual(r.remap_text("C:\\claude-workspace\\mcp\\x.py"), "D:\\nebula\\mcp\\x.py")
        self.assertEqual(r.remap_text("c:/claude-workspace/mcp"), "D:/nebula/mcp")
        self.assertEqual(r.remap_text("cd /d C:\\claude-workspace\\mcp\\pf && C:\\Users\\alice\\a.exe --x"),
                         "cd /d D:\\nebula\\mcp\\pf && C:\\Users\\bob\\a.exe --x")
        # frontière : un dossier voisin au même préfixe n'est pas touché
        self.assertEqual(r.remap_text("C:\\claude-workspace-extra\\a"), "C:\\claude-workspace-extra\\a")
        self.assertEqual(r.remap_text("xC:\\claude-workspace\\a"), "xC:\\claude-workspace\\a")

    def test_windows_vers_posix(self):
        r = PathRemapper([Rule("C:\\claude-workspace", "/home/u/neb")])
        self.assertEqual(r.remap_text("C:\\claude-workspace\\workspaces\\foo"), "/home/u/neb/workspaces/foo")
        self.assertEqual(r.remap_text("C:/claude-workspace/x"), "/home/u/neb/x")

    def test_regle_la_plus_specifique_et_priorite_utilisateur(self):
        r = PathRemapper([Rule("C:\\a", "D:\\a", "auto"), Rule("C:\\a\\b", "E:\\b", "user"),
                          Rule("C:\\a", "F:\\a", "user")])
        self.assertEqual(r.remap_text("C:\\a\\b\\c"), "E:\\b\\c")
        self.assertEqual(r.remap_text("C:\\a\\z"), "F:\\a\\z")      # règle utilisateur avant l'auto

    def test_json_valeurs_seulement(self):
        r = PathRemapper([Rule("C:\\x", "D:\\y")])
        out, n = r.remap_json({"a": ["C:\\x\\f", 1, None], "C:\\x": "garde"})
        self.assertEqual(out, {"a": ["D:\\y\\f", 1, None], "C:\\x": "garde"})
        self.assertEqual(n, 1)

    def test_dossiers_de_sessions_sans_decodage(self):
        r = PathRemapper([Rule("C:\\claude-workspace", "D:\\nebula"),
                          Rule("C:\\Users\\alice", "C:\\Users\\bob")])
        self.assertEqual(r.remap_project_dir_name("C--claude-workspace-workspaces-dashboard"),
                         "D--nebula-workspaces-dashboard")
        self.assertEqual(r.remap_project_dir_name("C--Users-alice-foo"), "C--Users-bob-foo")
        self.assertEqual(r.remap_project_dir_name("C--claude-workspaceX"), "C--claude-workspaceX")
        self.assertEqual(r.remap_project_dir_name("E--autre"), "E--autre")
        self.assertEqual(encode_project_name("C:\\a.b_c"), "C--a-b-c")

    def test_noms_de_membres_dangereux(self):
        for bad in ("../x", "a/../b", "/abs", "a\\b", "C:/x", "a/C:/b", "ws/a/x:stream", "", "a//b",
                    "a/\0b", "./a"):
            self.assertIsNone(split_member_name(bad), bad)
        self.assertEqual(split_member_name("ws/a/b.txt"), ["ws", "a", "b.txt"])
        self.assertEqual(split_member_name("ws/a/"), ["ws", "a"])


# ---------------------------------------------------------------------------
# Environnement source factice
# ---------------------------------------------------------------------------

def build_source() -> dict:
    """Peuple le bac à sable comme une machine réelle. Retourne les chemins utiles."""
    reset_sandbox()
    alpha = make_workspace("alpha")
    (alpha / "notes.txt").write_text("données alpha", encoding="utf-8")
    (alpha / "src").mkdir()
    (alpha / "src" / "main.py").write_text("print('a')\n", encoding="utf-8")
    (alpha / "node_modules" / "pkg").mkdir(parents=True)
    (alpha / "node_modules" / "pkg" / "index.js").write_text("// lourd", encoding="utf-8")
    (alpha / "vide").mkdir()
    write_json_file(alpha / ".mcp.json", {"mcpServers": {"s": {
        "command": "node", "args": [str(ROOT / "mcp" / "srv1" / "index.js")], "env": {"TOKEN": SECRET}}}})
    write_json_file(alpha / ".claude" / "settings.json",
                    {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                                    "command": f"python {ROOT}/tools/x.py"}]}]}})
    ext = ROOT / "ext" / "proj"
    make_workspace("proj", ext)
    (ext / "app.txt").write_text("projet adopté", encoding="utf-8")

    ENV_FILE.write_text(f"API_KEY={SECRET}\nPLAIN=bonjour\nTOOL_DIR={ROOT}/tools\n", encoding="utf-8")

    srv = ROOT / "mcp" / "srv1"
    (srv / ".venv" / "Scripts").mkdir(parents=True)
    (srv / ".venv" / "Scripts" / "python.exe").write_text("x", encoding="utf-8")
    (srv / "index.js").write_text("console.log(1)", encoding="utf-8")
    write_json_file(MCP_REGISTRY, {"version": "1.0", "mcps": [{
        "id": "srv1", "name": "srv1", "transport": "stdio", "command": "node",
        "args": [str(srv / "index.js")], "env": {"API_KEY": "${API_KEY}"},
        "workspaces": ["alpha"], "status": "disponible"}]})
    write_json_file(ROOT / "mcp" / "configs" / "filesystem.json",
                    {"args": [str(ROOT / "workspaces")]})
    (ROOT / "memory").mkdir(exist_ok=True)
    (ROOT / "memory" / "journal.md").write_text("# journal\n", encoding="utf-8")
    (ROOT / "templates" / "perso").mkdir()
    (ROOT / "templates" / "perso" / "CLAUDE.md").write_text("# perso\n", encoding="utf-8")
    write_json_file(ROOT / "dashboard" / "data" / "ui_state.json", {"theme": "sobre"})

    write_json_file(CLAUDE_HOME / "settings.json", {
        "hooks": {}, "note": f"{CLAUDE_HOME.as_posix()}/hooks/h.py", "enabledPlugins": {"p@m": True}})
    (CLAUDE_HOME / "skills" / "mon-skill").mkdir(parents=True)
    (CLAUDE_HOME / "skills" / "mon-skill" / "SKILL.md").write_text("---\nname: mon-skill\n---\n", encoding="utf-8")
    (CLAUDE_HOME / "agents").mkdir()
    (CLAUDE_HOME / "agents" / "a.md").write_text("# agent\n", encoding="utf-8")
    (CLAUDE_HOME / "history.jsonl").write_text('{"display":"hist"}\n', encoding="utf-8")

    sess_alpha = CLAUDE_PROJECTS / encode_project_name(str(alpha))
    (sess_alpha / "memory").mkdir(parents=True)
    (sess_alpha / "s1.jsonl").write_text('{"type":"user","cwd":"x"}\n', encoding="utf-8")
    (sess_alpha / "memory" / "MEMORY.md").write_text("# mémoire\n", encoding="utf-8")
    sess_ext = CLAUDE_PROJECTS / encode_project_name(str(ext))
    sess_ext.mkdir(parents=True)
    (sess_ext / "s2.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")
    (CLAUDE_HOME / "file-history" / "abc").mkdir(parents=True)
    (CLAUDE_HOME / "file-history" / "abc" / "v1").write_text("v1", encoding="utf-8")

    write_json_file(CLAUDE_JSON, {
        "userID": "ne-pas-migrer", "oauthAccount": {"emailAddress": "moi@example.invalid"},
        "mcpServers": {"racine": {"command": "r"}},
        "projects": {
            alpha.as_posix(): {"allowedTools": ["Bash"], "hasTrustDialogAccepted": True,
                               "mcpServers": {"m": {"command": "node", "args": [str(ROOT / "mcp" / "x.js")]}},
                               "history": [{"display": "prompt confidentiel"}], "lastCost": 1.5},
            "C:/inconnu/ailleurs": {"history": [{"display": "x"}]},
        }})
    return {"alpha": alpha, "ext": ext, "srv": srv, "sess_alpha": sess_alpha, "sess_ext": sess_ext}


def export_source(out: Path, **kw) -> dict:
    rmtree(out)
    out.mkdir(parents=True)
    return migration.run_export(PASS, str(out), kw.pop("selected", None), kdf_iterations=FAST, **kw)


def import_archive(path: str, options: dict | None = None, passphrase: str = PASS) -> tuple[dict, dict]:
    plan, fp = mi.preview_archive(path, passphrase, options or {})
    stored = {"archive": fp, "options": mi.normalize_options(options or {}), "digest": plan["digest"]}
    return plan, mi.run_import(stored, passphrase)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.src = build_source()
        self.out = SANDBOX / "out"

    def tearDown(self):
        rmtree(self.out)

    def test_estimation_par_groupe(self):
        est = migration.estimate(None)
        groups = {g["id"]: g for g in est["groups"]}
        self.assertGreater(groups["workspaces"]["bytes"], 0)
        self.assertGreater(groups["sessions"]["files"], 0)
        self.assertEqual({w["id"] for w in est["workspaces"]}, {"alpha", "proj"})
        self.assertEqual(est["env_keys"], 3)
        self.assertTrue(any("node_modules" in p for p in est["recreate"]))
        self.assertTrue(any(p.endswith(".venv") for p in est["recreate"]))
        # la taille de node_modules n'est pas comptée
        total = sum(w["bytes"] for w in est["workspaces"])
        self.assertLess(total, 10_000)

    def test_estimation_ne_modifie_rien(self):
        before = _tree(ROOT) | {f"home/{k}": v for k, v in _tree(CLAUDE_HOME.parent).items()}
        migration.estimate({"alpha"})
        after = _tree(ROOT) | {f"home/{k}": v for k, v in _tree(CLAUDE_HOME.parent).items()}
        self.assertEqual(before, after)

    def test_export_chiffre_et_verifie(self):
        res = export_source(self.out)
        p = Path(res["path"])
        self.assertTrue(p.is_file())
        self.assertTrue(res["verified"])
        self.assertEqual(p.suffix, ".nebmig")
        self.assertFalse(list(self.out.glob("*.part")))
        raw = p.read_bytes()
        for needle in (SECRET.encode(), "données alpha".encode(), b"alpha", b"manifest.json",
                       b"prompt confidentiel", b"ne-pas-migrer"):
            self.assertNotIn(needle, raw)
        names = {n for n, _ in _read_all(p, PASS)}
        self.assertIn("manifest.json", names)
        self.assertIn("meta/env.json", names)
        self.assertIn("ws/alpha/notes.txt", names)
        self.assertFalse(any("node_modules" in n or ".venv" in n for n in names))

    def test_listes_blanches_claude_json(self):
        res = export_source(self.out)
        members = dict(_read_all(Path(res["path"]), PASS))
        cj = json.loads(members["meta/claude_json.json"])
        blob = json.dumps(cj)
        self.assertNotIn("ne-pas-migrer", blob)
        self.assertNotIn("moi@example.invalid", blob)
        self.assertNotIn("prompt confidentiel", blob)
        self.assertNotIn("lastCost", blob)
        self.assertNotIn("C:/inconnu/ailleurs", cj["projects"])   # rien de whitelisté : omis
        self.assertEqual(cj["mcpServers"], {"racine": {"command": "r"}})
        proj = cj["projects"][self.src["alpha"].as_posix()]
        self.assertEqual(set(proj), {"allowedTools", "hasTrustDialogAccepted", "mcpServers"})

    def test_selection_de_workspaces(self):
        res = export_source(self.out, selected={"alpha"})
        names = {n for n, _ in _read_all(Path(res["path"]), PASS)}
        self.assertIn("ws/alpha/notes.txt", names)
        self.assertFalse(any(n.startswith("ws/proj") for n in names))
        manifest = json.loads(dict(_read_all(Path(res["path"]), PASS))["manifest.json"])
        self.assertEqual([w["id"] for w in manifest["workspaces"]], ["alpha"])

    def test_liens_et_jonctions_non_exportes(self):
        outside = SANDBOX / "dehors"
        outside.mkdir(exist_ok=True)
        (outside / "secret.txt").write_text("hors workspace", encoding="utf-8")
        if not _make_dir_link(self.src["alpha"] / "lien", outside):
            self.skipTest("création de lien impossible sur ce poste")
        try:
            res = export_source(self.out)
            members = dict(_read_all(Path(res["path"]), PASS))
            self.assertFalse(any("lien" in n for n in members))
            self.assertNotIn(b"hors workspace", b"".join(members.values()))
            self.assertTrue(any("lien" in w for w in res["warnings"]))
        finally:
            link = self.src["alpha"] / "lien"
            try:
                os.rmdir(link) if sys_platform() == "win32" else os.unlink(link)
            except OSError:
                pass
            rmtree(outside)

    def test_destination_dans_un_workspace_n_inclut_pas_l_archive(self):
        res = export_source(self.src["alpha"] / "sortie")
        names = {n for n, _ in _read_all(Path(res["path"]), PASS)}
        self.assertTrue(any(n.endswith("notes.txt") for n in names))
        self.assertFalse(any(n.endswith(".nebmig") or n.endswith(".part") for n in names))

    def test_phrase_trop_courte_refusee(self):
        with self.assertRaises(mc.MigrationError):
            migration.run_export("courte", str(self.out), None, kdf_iterations=FAST)
        self.assertFalse(self.out.exists() and list(self.out.iterdir()))

    def test_annulation_supprime_le_fichier_partiel(self):
        calls = {"n": 0}

        def cancel():
            calls["n"] += 1
            return calls["n"] > 12

        self.out.mkdir(exist_ok=True)
        with self.assertRaises(mc.MigrationCancelled):
            migration.run_export(PASS, str(self.out), None, cancel=cancel, kdf_iterations=FAST)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_coffre_illisible_refuse_l_export(self):
        from dashcore.env_local import EnvStoreUnreadable
        with mock.patch("dashcore.migration.load_env_local_strict",
                        side_effect=EnvStoreUnreadable("coffre illisible")):
            with self.assertRaises(EnvStoreUnreadable):
                migration.run_export(PASS, str(self.out), None, kdf_iterations=FAST)
        self.assertEqual(list(self.out.iterdir()) if self.out.exists() else [], [])


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportRoundTripTests(unittest.TestCase):
    """Source -> archive -> machine VIDE (mêmes chemins)."""

    def setUp(self):
        self.src = build_source()
        self.out = SANDBOX / "out"
        self.archive = export_source(self.out)["path"]
        self.alpha_files = _tree(self.src["alpha"])
        self.ext_files = _tree(self.src["ext"])
        reset_sandbox()                       # « nouvelle machine » : tout est vide

    def tearDown(self):
        rmtree(self.out)

    def test_apercu_sans_aucune_ecriture(self):
        before = _tree(ROOT), _tree(CLAUDE_HOME.parent), _tree(SANDBOX / "out")
        plan, _fp = mi.preview_archive(self.archive, PASS, {})
        after = _tree(ROOT), _tree(CLAUDE_HOME.parent), _tree(SANDBOX / "out")
        self.assertEqual(before, after)
        self.assertFalse(BACKUPS_DIR.exists() and list(BACKUPS_DIR.iterdir()))
        self.assertTrue(plan["ok"])
        self.assertEqual({w["id"]: w["action"] for w in plan["workspaces"]},
                         {"alpha": "import", "proj": "import"})
        self.assertEqual(plan["counts"]["workspaces_import"], 2)
        self.assertGreater(len(plan["sessions"]), 0)
        self.assertEqual(plan["workspaces"][0]["status"], "new")

    def test_apercu_ne_contient_aucune_valeur_secrete(self):
        plan, _fp = mi.preview_archive(self.archive, PASS, {})
        blob = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn(SECRET, blob)
        self.assertNotIn("sup3r", blob)
        self.assertNotIn("bonjour", blob)                 # valeur d'une variable
        self.assertIn("API_KEY", blob)                    # le nom, lui, est affiché

    def test_aller_retour_complet(self):
        plan, res = import_archive(self.archive)
        self.assertEqual(res["workspaces"]["imported"], 2)
        self.assertEqual(res["extract_errors"], [])
        # fichiers des workspaces, y compris l'adopté hors WORKSPACES_DIR
        a = ROOT / "workspaces" / "alpha"
        self.assertEqual(_tree(a).keys(), {k for k in self.alpha_files if "node_modules" not in k})
        self.assertEqual((a / "notes.txt").read_text(encoding="utf-8"), "données alpha")
        self.assertTrue((a / "vide").is_dir())                       # dossier vide conservé
        self.assertFalse((a / "node_modules").exists())              # régénérable : non exporté
        self.assertEqual((ROOT / "ext" / "proj" / "app.txt").read_text(encoding="utf-8"), "projet adopté")
        # registre
        reg = read_json_file(WORKSPACES_JSON)
        self.assertEqual({w["id"] for w in reg["workspaces"]}, {"alpha", "proj"})
        self.assertEqual(next(w for w in reg["workspaces"] if w["id"] == "proj")["path"],
                         str(ROOT / "ext" / "proj"))
        self.assertTrue((SCRIPTS_DIR / "launch-alpha.bat").is_file())
        # MCP
        mcps = read_json_file(MCP_REGISTRY)["mcps"]
        self.assertEqual([m["id"] for m in mcps], ["srv1"])
        self.assertEqual((ROOT / "mcp" / "srv1" / "index.js").read_text(encoding="utf-8"), "console.log(1)")
        self.assertFalse((ROOT / "mcp" / "srv1" / ".venv").exists())
        self.assertTrue((ROOT / "mcp" / "configs" / "filesystem.json").is_file())
        # secrets (coffre en clair sur la cible)
        env = dict(line.split("=", 1) for line in ENV_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertEqual(env["API_KEY"], SECRET)
        # claude global
        self.assertTrue((CLAUDE_HOME / "skills" / "mon-skill" / "SKILL.md").is_file())
        self.assertTrue((CLAUDE_HOME / "agents" / "a.md").is_file())
        self.assertTrue((CLAUDE_HOME / "history.jsonl").is_file())
        self.assertTrue((CLAUDE_HOME / "file-history" / "abc" / "v1").is_file())
        # ~/.claude.json : fusion de la liste blanche seulement
        cj = read_json_file(CLAUDE_JSON)
        self.assertNotIn("userID", cj)
        self.assertNotIn("oauthAccount", cj)
        self.assertEqual(cj["mcpServers"], {"racine": {"command": "r"}})
        proj = cj["projects"][self.src["alpha"].as_posix()]
        self.assertEqual(proj["allowedTools"], ["Bash"])
        self.assertNotIn("history", proj)
        # sessions (mtime conservé par tar)
        self.assertTrue((self.src["sess_alpha"] / "s1.jsonl").is_file())
        self.assertTrue((self.src["sess_ext"] / "s2.jsonl").is_file())
        self.assertTrue((self.src["sess_alpha"] / "memory" / "MEMORY.md").is_file())
        # rien de laissé dans le dossier de préparation
        self.assertFalse((BACKUPS_DIR / ".migration-staging").exists())
        # machine vide : rien n'a été remplacé (la sauvegarde ne contient que les registres d'avant)
        self.assertEqual(res["workspaces"]["replaced"], 0)
        self.assertEqual(res["items"]["replaced"], 0)

    def test_reimport_conflits_jamais_ecrases(self):
        import_archive(self.archive)
        (ROOT / "workspaces" / "alpha" / "notes.txt").write_text("modifié ici", encoding="utf-8")
        before = _tree(ROOT / "workspaces"), read_json_file(WORKSPACES_JSON), ENV_FILE.read_text(encoding="utf-8")
        plan, res = import_archive(self.archive)
        self.assertEqual({w["id"]: (w["status"], w["action"]) for w in plan["workspaces"]},
                         {"alpha": ("conflict", "skip"), "proj": ("conflict", "skip")})
        self.assertEqual(res["workspaces"]["imported"], 0)
        after = _tree(ROOT / "workspaces"), read_json_file(WORKSPACES_JSON), ENV_FILE.read_text(encoding="utf-8")
        self.assertEqual(before, after)                       # rien n'a bougé
        self.assertIsNone(res["backup_dir"])

    def test_conflit_non_resolu_est_bloque(self):
        import_archive(self.archive)
        plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {"alpha": {"action": "import"}}})
        w = next(w for w in plan["workspaces"] if w["id"] == "alpha")
        self.assertIn("conflit", w["blocked"])
        self.assertFalse(plan["ok"])
        plan2, fp = mi.preview_archive(self.archive, PASS, {"workspaces": {"alpha": {"action": "import"}}})
        with self.assertRaises(mc.MigrationError):
            mi.run_import({"archive": fp, "options": mi.normalize_options(
                {"workspaces": {"alpha": {"action": "import"}}}), "digest": plan2["digest"]}, PASS)

    def test_remplacer_range_l_ancien_dans_une_sauvegarde_horodatee(self):
        import_archive(self.archive)
        (ROOT / "workspaces" / "alpha" / "notes.txt").write_text("version locale", encoding="utf-8")
        write_json_file(ROOT / "workspaces" / "alpha" / "local-only.json", {"a": 1})
        plan, res = import_archive(self.archive, {"workspaces": {"alpha": {"action": "replace"}}})
        self.assertEqual(res["workspaces"]["replaced"], 1)
        self.assertEqual((ROOT / "workspaces" / "alpha" / "notes.txt").read_text(encoding="utf-8"), "données alpha")
        self.assertFalse((ROOT / "workspaces" / "alpha" / "local-only.json").exists())
        bdir = Path(res["backup_dir"])
        self.assertTrue(re.match(r"migration-\d{8}-\d{6}$", bdir.name))
        saved = bdir / "workspaces" / "alpha"
        self.assertEqual((saved / "notes.txt").read_text(encoding="utf-8"), "version locale")
        self.assertTrue((saved / "local-only.json").is_file())
        self.assertTrue((bdir / "workspaces.json").is_file())      # registre d'avant

    def test_renommer_un_workspace(self):
        import_archive(self.archive)
        plan, res = import_archive(self.archive, {"workspaces": {"alpha": {"action": "rename", "new_id": "alpha2"}}})
        w = next(w for w in plan["workspaces"] if w["id"] == "alpha")
        self.assertEqual((w["eff_id"], w["action"], w["blocked"]), ("alpha2", "rename", None))
        self.assertEqual(w["target_path"], str(ROOT / "workspaces" / "alpha2"))
        self.assertTrue((ROOT / "workspaces" / "alpha2" / "notes.txt").is_file())
        ids = [x["id"] for x in read_json_file(WORKSPACES_JSON)["workspaces"]]
        self.assertEqual(sorted(ids), ["alpha", "alpha2", "proj"])
        self.assertTrue((SCRIPTS_DIR / "launch-alpha2.bat").is_file())

    def test_variables_conflit_garde_local_ou_remplace(self):
        ENV_FILE.write_text("API_KEY=valeur-locale\nAUTRE=1\n", encoding="utf-8")
        plan, _res = import_archive(self.archive)
        items = {e["key"]: e for e in plan["env"]["items"]}
        self.assertEqual((items["API_KEY"]["status"], items["API_KEY"]["action"]), ("conflict", "keep"))
        text = ENV_FILE.read_text(encoding="utf-8")
        self.assertIn("API_KEY=valeur-locale", text)
        self.assertIn("PLAIN=bonjour", text)               # nouvelle clé ajoutée
        self.assertIn("AUTRE=1", text)                     # clé locale conservée
        plan, res = import_archive(self.archive, {"env": {"API_KEY": "replace"}})
        self.assertIn(f"API_KEY={SECRET}", ENV_FILE.read_text(encoding="utf-8"))
        self.assertEqual(res["env"]["replaced"], 1)
        self.assertIsNotNone(res["backup_dir"])            # ancien coffre sauvegardé
        self.assertTrue(any(p.name.startswith("env-local") for p in Path(res["backup_dir"]).iterdir()))

    def test_elements_existants_ignores_par_defaut(self):
        (CLAUDE_HOME / "agents").mkdir(parents=True, exist_ok=True)
        (CLAUDE_HOME / "agents" / "a.md").write_text("# agent local\n", encoding="utf-8")
        plan, res = import_archive(self.archive)
        it = next(i for i in plan["items"] if i["key"] == "claude/agents/a.md")
        self.assertEqual((it["status"], it["action"]), ("exists", "skip"))
        self.assertEqual((CLAUDE_HOME / "agents" / "a.md").read_text(encoding="utf-8"), "# agent local\n")
        plan, res = import_archive(self.archive, {"items": {"claude/agents/a.md": "replace"}})
        self.assertEqual((CLAUDE_HOME / "agents" / "a.md").read_text(encoding="utf-8"), "# agent\n")
        saved = Path(res["backup_dir"]) / "claude" / "agents" / "a.md"
        self.assertEqual(saved.read_text(encoding="utf-8"), "# agent local\n")

    def test_sessions_fusionnees_sans_ecrasement(self):
        sess = self.src["sess_alpha"]
        sess.mkdir(parents=True)
        (sess / "s1.jsonl").write_text("version locale\n", encoding="utf-8")
        (sess / "autre.jsonl").write_text("garde\n", encoding="utf-8")
        (sess / "memory").mkdir()
        (sess / "memory" / "MEMORY.md").write_text("# mémoire locale\n", encoding="utf-8")
        _plan, res = import_archive(self.archive)
        self.assertEqual((sess / "s1.jsonl").read_text(encoding="utf-8"), "version locale\n")
        self.assertEqual((sess / "autre.jsonl").read_text(encoding="utf-8"), "garde\n")
        self.assertEqual((sess / "memory" / "MEMORY.md").read_text(encoding="utf-8"), "# mémoire locale\n")
        sides = list((sess / "memory").glob("MEMORY.md.migration-*"))
        self.assertEqual(len(sides), 1)                                      # version importée rangée à côté
        self.assertEqual(sides[0].read_text(encoding="utf-8"), "# mémoire\n")
        self.assertFalse(list(sess.glob("s1.jsonl.migration-*")))            # transcripts : pas de doublon
        self.assertEqual(res["sessions"]["kept_local"], 2)

    def test_claude_json_fusion_non_destructive(self):
        write_json_file(CLAUDE_JSON, {"userID": "local", "projects": {
            self.src["alpha"].as_posix(): {"allowedTools": ["Read"], "lastCost": 9,
                                           "mcpServers": {"m": {"command": "autre"}}}}})
        plan, _res = import_archive(self.archive)
        self.assertEqual(plan["claude_json"]["mcp_conflicts"], 1)
        cj = read_json_file(CLAUDE_JSON)
        self.assertEqual(cj["userID"], "local")
        proj = cj["projects"][self.src["alpha"].as_posix()]
        self.assertEqual(proj["allowedTools"], ["Read", "Bash"])             # union
        self.assertEqual(proj["mcpServers"]["m"], {"command": "autre"})      # local gardé
        self.assertEqual(proj["lastCost"], 9)
        self.assertTrue((BACKUPS_DIR.glob("migration-*/claude.json")).__next__().is_file())

    def test_remappage_de_bout_en_bout(self):
        """Autre emplacement : workspace adopté, sessions, .mcp.json, registre MCP,
        variables, settings.json, ~/.claude.json."""
        new_ext = SANDBOX / "nouvel-endroit"
        old_ext = ROOT / "ext"
        rules = [{"from": str(old_ext), "to": str(new_ext)},
                 {"from": str(ROOT / "mcp"), "to": str(ROOT / "mcp-neuf")},
                 {"from": str(ROOT / "tools"), "to": str(ROOT / "outils")}]
        plan, res = import_archive(self.archive, {"rules": rules})
        proj = next(w for w in plan["workspaces"] if w["id"] == "proj")
        self.assertEqual((proj["target_path"], proj["path_origin"]), (str(new_ext / "proj"), "rule"))
        self.assertEqual((new_ext / "proj" / "app.txt").read_text(encoding="utf-8"), "projet adopté")
        self.assertFalse((old_ext / "proj").exists())
        reg = read_json_file(WORKSPACES_JSON)
        self.assertEqual(next(w for w in reg["workspaces"] if w["id"] == "proj")["path"], str(new_ext / "proj"))
        # dossier de sessions renommé (espace encodé, sans décodage)
        self.assertTrue((CLAUDE_PROJECTS / encode_project_name(str(new_ext / "proj")) / "s2.jsonl").is_file())
        self.assertFalse((CLAUDE_PROJECTS / encode_project_name(str(old_ext / "proj"))).exists())
        # .mcp.json du workspace, registre MCP, variable, settings.json global
        mcp_json = read_json_file(ROOT / "workspaces" / "alpha" / ".mcp.json")
        self.assertEqual(mcp_json["mcpServers"]["s"]["args"], [str(ROOT / "mcp-neuf" / "srv1" / "index.js")])
        self.assertEqual(mcp_json["mcpServers"]["s"]["env"]["TOKEN"], SECRET)
        alpha_settings = read_json_file(ROOT / "workspaces" / "alpha" / ".claude" / "settings.json")
        self.assertIn(f"{ROOT.as_posix()}/outils/x.py".replace("/", os.sep) if os.sep == "\\" else
                      f"{ROOT}/outils/x.py", json.dumps(alpha_settings).replace("\\\\", "\\")
                      if os.sep == "\\" else json.dumps(alpha_settings))
        self.assertEqual(read_json_file(MCP_REGISTRY)["mcps"][0]["args"],
                         [str(ROOT / "mcp-neuf" / "srv1" / "index.js")])
        self.assertIn(str(ROOT / "outils"), ENV_FILE.read_text(encoding="utf-8").replace("/", os.sep))
        cj = read_json_file(CLAUDE_JSON)
        self.assertEqual(cj["projects"][self.src["alpha"].as_posix()]["mcpServers"]["m"]["args"],
                         [str(ROOT / "mcp-neuf" / "x.js")])
        self.assertGreaterEqual(res["json_remapped"], 2)

    def test_chemin_cible_inexistant_ou_interdit_signale(self):
        under_claude = str(CLAUDE_HOME / "ws")
        plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {
            "alpha": {"target_path": under_claude}, "proj": {"target_path": "relatif/chemin"}}})
        by = {w["id"]: w for w in plan["workspaces"]}
        self.assertIn("~/.claude", by["alpha"]["blocked"])
        self.assertIn("invalide", by["proj"]["blocked"])
        self.assertFalse(plan["ok"])
        # doublon de chemin cible dans le même plan
        same = str(SANDBOX / "meme-endroit")
        plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {
            "alpha": {"target_path": same}, "proj": {"target_path": same}}})
        self.assertTrue(any(w["blocked"] and "déjà visé" in w["blocked"] for w in plan["workspaces"]))
        # dossier parent absent : signalé, pas bloquant
        plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {
            "alpha": {"target_path": str(SANDBOX / "n" / "existe" / "pas")}}})
        w = next(w for w in plan["workspaces"] if w["id"] == "alpha")
        self.assertFalse(w["parent_exists"])
        self.assertIsNone(w["blocked"])

    def test_cibles_protegees_refusees(self):
        from dashcore.config import DASHBOARD_DIR, DATA_DIR, WORKSPACES_DIR
        for target in (ROOT, DASHBOARD_DIR, DATA_DIR, BACKUPS_DIR, CLAUDE_HOME, CLAUDE_HOME.parent,
                       ROOT / "mcp", WORKSPACES_DIR, ROOT.parent, DASHBOARD_DIR / "js"):
            plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {
                "alpha": {"action": "import", "target_path": str(target)}}})
            w = next(w for w in plan["workspaces"] if w["id"] == "alpha")
            self.assertTrue(w["blocked"], target)
        plan, _fp = mi.preview_archive(self.archive, PASS, {"workspaces": {
            "alpha": {"action": "import", "target_path": str(WORKSPACES_DIR / "libre")}}})
        self.assertIsNone(next(w for w in plan["workspaces"] if w["id"] == "alpha")["blocked"])

    def test_phase_en_echec_n_empeche_pas_le_bilan(self):
        with mock.patch("dashcore.migration_import.set_env_var", side_effect=RuntimeError("boum")):
            _plan, res = import_archive(self.archive)
        self.assertEqual(res["workspaces"]["imported"], 2)
        self.assertTrue(any(e["area"] == "env" for e in res["errors"]))
        self.assertTrue((ROOT / "workspaces" / "alpha" / "notes.txt").is_file())
        self.assertTrue((CLAUDE_HOME / "skills" / "mon-skill" / "SKILL.md").is_file())    # phases suivantes faites

    def test_plan_perime_si_l_etat_change(self):
        plan, fp = mi.preview_archive(self.archive, PASS, {})
        stored = {"archive": fp, "options": mi.normalize_options({}), "digest": plan["digest"]}
        make_workspace("alpha", ROOT / "workspaces" / "alpha")        # apparaît entre l'aperçu et l'import
        with self.assertRaises(mi.PlanStale) as cm:
            mi.run_import(stored, PASS)
        self.assertNotEqual(cm.exception.plan["digest"], plan["digest"])
        self.assertEqual(next(w for w in cm.exception.plan["workspaces"] if w["id"] == "alpha")["status"],
                         "conflict")
        self.assertFalse((ROOT / "workspaces" / "alpha" / "notes.txt").exists())

    def test_mauvaise_phrase_de_passe_aucune_ecriture(self):
        before = _tree(ROOT), _tree(CLAUDE_HOME.parent)
        with self.assertRaises(mc.MigrationAuthError):
            mi.preview_archive(self.archive, "mauvaise phrase de passe", {})
        after = _tree(ROOT), _tree(CLAUDE_HOME.parent)
        self.assertEqual(before, after)

    def test_archive_alteree_refusee_aucune_ecriture(self):
        plan, fp = mi.preview_archive(self.archive, PASS, {})
        raw = bytearray(Path(self.archive).read_bytes())
        raw[len(raw) // 2] ^= 0x01
        Path(self.archive).write_bytes(raw)
        before = _tree(ROOT), _tree(CLAUDE_HOME.parent)
        stored = {"archive": fp, "options": mi.normalize_options({}), "digest": plan["digest"]}
        with self.assertRaises(mc.MigrationError):
            mi.run_import(stored, PASS)
        self.assertEqual(before, (_tree(ROOT), _tree(CLAUDE_HOME.parent)))

    def test_archive_remplacee_apres_l_apercu_refusee(self):
        plan, fp = mi.preview_archive(self.archive, PASS, {})
        other = SANDBOX / "autre.nebmig"
        migration_second = Path(self.archive).read_bytes()
        Path(self.archive).write_bytes(migration_second + b"x")
        stored = {"archive": fp, "options": mi.normalize_options({}), "digest": plan["digest"]}
        with self.assertRaises(mc.MigrationError):
            mi.run_import(stored, PASS)
        self.assertFalse(other.exists())

    def test_coffre_chiffre_cible_respecte(self):
        """Le coffre local (clair ici) reste géré par set_env_var : pas d'écriture
        directe dans le fichier."""
        with mock.patch("dashcore.migration_import.set_env_var", return_value=(200, {"ok": True})) as m:
            import_archive(self.archive)
        self.assertEqual({c.args[0] for c in m.call_args_list}, {"API_KEY", "PLAIN", "TOOL_DIR"})


# ---------------------------------------------------------------------------
# Plan sur une archive d'une autre machine (manifeste doctoré)
# ---------------------------------------------------------------------------

class CrossMachinePlanTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def _manifest(self, **over):
        m = {
            "format": "nebula-migration", "format_version": 1, "created": "2026-11-11T00:00:00",
            "nebula_version": "2.7.2",
            "source": {"os": "win32", "sep": "\\", "host": "OLD-PC", "root": "C:\\claude-workspace",
                       "user_home": "C:\\Users\\alice", "claude_home": "C:\\Users\\alice\\.claude",
                       "data_dir": "C:\\claude-workspace\\dashboard\\data",
                       "workspaces_dir": "C:\\claude-workspace\\workspaces"},
            "workspaces": [
                {"id": "dash", "label": "Dash", "emoji": "", "in_workspaces_dir": True,
                 "source_path": "C:\\claude-workspace\\workspaces\\dash", "entry": {"id": "dash"}},
                {"id": "proj", "label": "Proj", "emoji": "", "in_workspaces_dir": False,
                 "source_path": "D:\\Projets\\proj", "entry": {"id": "proj", "path": "D:\\Projets\\proj"}},
            ],
            "units": [
                {"key": "ws/dash", "kind": "workspace", "group": "workspaces", "label": "Dash",
                 "is_dir": True, "files": 1, "bytes": 10},
                {"key": "ws/proj", "kind": "workspace", "group": "workspaces", "label": "Proj",
                 "is_dir": True, "files": 1, "bytes": 10},
                {"key": "claude/projects/C--claude-workspace-workspaces-dash", "kind": "merge",
                 "group": "sessions", "label": "s", "is_dir": True, "files": 1, "bytes": 5},
                {"key": "claude/projects/C--Users-alice-Desktop-x", "kind": "merge",
                 "group": "sessions", "label": "s", "is_dir": True, "files": 1, "bytes": 5},
            ],
            "env_keys": [], "mcp_ids": [], "claude_json": {}, "plugins_installed": [],
            "recreate": [], "totals": {"files": 4, "bytes": 30}, "warnings": [],
        }
        m.update(over)
        return mi.validate_manifest(m)

    def _plan(self, manifest, options=None):
        info = {"path": "x", "name": "x", "size": 1, "mtime": "", "format_version": 1, "tag": "t"}
        return mi.build_plan(manifest, {}, options or {}, info)

    def test_regles_automatiques_et_chemins_par_defaut(self):
        plan = self._plan(self._manifest())
        autos = {r["from"]: r["to"] for r in plan["rules"]["auto"]}
        self.assertEqual(autos["C:\\claude-workspace"], str(ROOT))
        by = {w["id"]: w for w in plan["workspaces"]}
        self.assertEqual(by["dash"]["target_path"], str(ROOT / "workspaces" / "dash"))
        # chemin adopté sans règle : D:\Projets\proj n'existe pas ici (autre OS / lecteur absent)
        # -> repli sous workspaces/, jamais un chemin inutilisable
        if not mi._anchor_ok("D:\\Projets\\proj"):
            self.assertEqual((by["proj"]["target_path"], by["proj"]["path_origin"]),
                             (str(ROOT / "workspaces" / "proj"), "fallback"))
        # dossiers de sessions : préfixe remappé dans l'espace encodé
        names = {s["name"]: s["target_name"] for s in plan["sessions"]}
        self.assertEqual(names["C--claude-workspace-workspaces-dash"],
                         encode_project_name(str(ROOT / "workspaces" / "dash")))
        self.assertEqual(names["C--Users-alice-Desktop-x"],
                         encode_project_name(str(Path.home() / "Desktop" / "x")))

    def test_regle_utilisateur_pour_un_projet_adopte(self):
        target = str(SANDBOX / "projets")
        plan = self._plan(self._manifest(), {"rules": [{"from": "D:\\Projets", "to": target}]})
        proj = next(w for w in plan["workspaces"] if w["id"] == "proj")
        self.assertEqual((proj["target_path"], proj["path_origin"]), (str(Path(target) / "proj"), "rule"))
        self.assertIsNone(proj["blocked"])

    def test_manifeste_hostile_refuse(self):
        base = self._manifest()
        raw = {"format": "nebula-migration", "format_version": 1, "source": base["source"],
               "workspaces": [], "units": [{"key": "ws/../../x", "kind": "workspace",
                                            "group": "workspaces", "label": "x", "files": 0, "bytes": 0}]}
        for key in ("ws/../../x", "../etc", "claude/projects/../x", "claude/inconnu/x", "nebula/data/evil.json",
                    "nebula/mcp-servers/configs", "ws/a/b", "C:/x"):
            raw["units"][0]["key"] = key
            with self.assertRaises(mc.MigrationFormatError, msg=key):
                mi.validate_manifest(raw)
        raw["units"][0].update(key="claude/skills/ok", kind="item", group="claude_global", bytes=-1)
        with self.assertRaises(mc.MigrationFormatError):
            mi.validate_manifest(raw)
        raw["units"][0].update(bytes=1, group="inconnu")
        with self.assertRaises(mc.MigrationFormatError):
            mi.validate_manifest(raw)


# ---------------------------------------------------------------------------
# Archives piégées
# ---------------------------------------------------------------------------

class MaliciousArchiveTests(unittest.TestCase):
    """Archive correctement chiffrée (le pirate connaît la phrase de passe) mais
    piégée : rien ne doit sortir du dossier de préparation, rien n'est appliqué."""

    def setUp(self):
        reset_sandbox()
        self.dir = SANDBOX / "evil"
        rmtree(self.dir)
        self.dir.mkdir()
        self.manifest = {
            "format": "nebula-migration", "format_version": 1, "created": "2026-11-11T00:00:00",
            "nebula_version": "2.7.2",
            "source": {"os": sys_platform(), "sep": os.sep, "host": "h", "root": str(ROOT),
                       "user_home": str(Path.home()), "claude_home": str(CLAUDE_HOME),
                       "data_dir": str(ROOT / "dashboard" / "data"),
                       "workspaces_dir": str(ROOT / "workspaces")},
            "workspaces": [{"id": "ws", "label": "ws", "emoji": "", "in_workspaces_dir": True,
                            "source_path": str(ROOT / "workspaces" / "ws"), "entry": {"id": "ws"}}],
            "units": [{"key": "ws/ws", "kind": "workspace", "group": "workspaces", "label": "ws",
                       "is_dir": True, "files": 1, "bytes": 10}],
            "env_keys": [], "mcp_ids": [], "claude_json": {}, "plugins_installed": [], "recreate": [],
            "totals": {"files": 1, "bytes": 10}, "warnings": [],
        }

    def tearDown(self):
        rmtree(self.dir)
        rmtree(SANDBOX / "evil-out")

    def _archive(self, members: list[tuple[str, bytes]], **tarinfo_kw) -> Path:
        path = self.dir / "e.nebmig"
        w = mc.EncryptingWriter(open(path, "wb"), PASS, FAST)
        gz = gzip.GzipFile(fileobj=w, mode="wb", compresslevel=1, mtime=0)
        tf = tarfile.open(fileobj=gz, mode="w|", format=tarfile.GNU_FORMAT)

        def add(name, data, typ=tarfile.REGTYPE, link=""):
            ti = tarfile.TarInfo(name)
            ti.size = len(data) if typ == tarfile.REGTYPE else 0
            ti.type = typ
            ti.linkname = link
            tf.addfile(ti, io.BytesIO(data) if typ == tarfile.REGTYPE else None)

        add("manifest.json", json.dumps(self.manifest).encode())
        for name, data in members:
            if isinstance(data, tuple):                       # (type, linkname)
                add(name, b"", data[0], data[1])
            else:
                add(name, data)
        tf.close()
        gz.close()
        w.close()
        return path

    def _run(self, path: Path):
        plan, fp = mi.preview_archive(str(path), PASS, {})
        return mi.run_import({"archive": fp, "options": mi.normalize_options({}),
                              "digest": plan["digest"]}, PASS)

    def _assert_refused(self, members):
        evil = SANDBOX / "evil-out"
        before = _tree(ROOT), _tree(CLAUDE_HOME.parent)
        with self.assertRaises(mc.MigrationFormatError):
            self._run(self._archive(members))
        self.assertEqual(before, (_tree(ROOT), _tree(CLAUDE_HOME.parent)))
        self.assertFalse(evil.exists())
        self.assertFalse((BACKUPS_DIR / ".migration-staging").exists())
        self.assertFalse((SANDBOX / "pwned.txt").exists())
        self.assertFalse((ROOT / "pwned.txt").exists())

    def test_archive_saine_de_reference(self):
        res = self._run(self._archive([("ws/ws/a.txt", b"0123456789")]))
        self.assertEqual(res["workspaces"]["imported"], 1)
        self.assertEqual((ROOT / "workspaces" / "ws" / "a.txt").read_bytes(), b"0123456789")

    def test_label_et_cles_du_registre_assainis(self):
        self.manifest["workspaces"][0]["entry"] = {"id": "ws", "label": "a & calc | %PATH%",
                                                    "evil": {"nested": 1}, "ok": True, "bad key!": "x"}
        self._run(self._archive([("ws/ws/a.txt", b"0123456789")]))
        entry = read_json_file(WORKSPACES_JSON)["workspaces"][0]
        self.assertEqual(entry["id"], "ws")
        for ch in "&|%":
            self.assertNotIn(ch, entry["label"])
        self.assertNotIn("evil", entry)
        self.assertNotIn("bad key!", entry)
        self.assertNotIn("& calc", (SCRIPTS_DIR / "launch-ws.bat").read_text(encoding="utf-8"))

    def test_date_aberrante_sans_effet(self):
        path = self.dir / "t.nebmig"
        w = mc.EncryptingWriter(open(path, "wb"), PASS, FAST)
        gz = gzip.GzipFile(fileobj=w, mode="wb", compresslevel=1, mtime=0)
        tf = tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT)
        for name, data in (("manifest.json", json.dumps(self.manifest).encode()), ("ws/ws/a.txt", b"0123456789")):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mtime = 1e300 if name.endswith("a.txt") else 0
            tf.addfile(ti, io.BytesIO(data))
        tf.close()
        gz.close()
        w.close()
        res = self._run(path)
        self.assertEqual(res["workspaces"]["imported"], 1)

    def test_traversee_par_points_points(self):
        self._assert_refused([("ws/ws/../../../pwned.txt", b"x")])

    def test_chemin_absolu(self):
        self._assert_refused([("/pwned.txt", b"x")])
        self._assert_refused([(str(SANDBOX / "pwned.txt").replace("\\", "/"), b"x")])

    def test_antislash_et_lecteur(self):
        self._assert_refused([("ws/ws/..\\..\\pwned.txt", b"x")])
        self._assert_refused([("ws/ws/C:/pwned.txt", b"x")])
        self._assert_refused([("ws/ws/a.txt:flux", b"x")])

    def test_lien_symbolique_et_lien_dur(self):
        self._assert_refused([("ws/ws/lien", (tarfile.SYMTYPE, str(SANDBOX / "evil-out")))])
        self._assert_refused([("ws/ws/dur", (tarfile.LNKTYPE, "ws/ws/a.txt"))])

    def test_fichier_special(self):
        self._assert_refused([("ws/ws/fifo", (tarfile.FIFOTYPE, ""))])

    def test_unite_inconnue_ou_hors_liste(self):
        self._assert_refused([("autre/chose.txt", b"x")])
        self._assert_refused([("claude/settings.json.evil", b"x")])
        self._assert_refused([("nebula/data/evil.json", b"x")])
        self._assert_refused([("ws/inconnu/x.txt", b"x")])

    def test_volume_superieur_au_declare(self):
        self.manifest["units"][0]["bytes"] = 1
        self.manifest["totals"]["bytes"] = 1
        with mock.patch("dashcore.migration_import.MIGRATION_MAX_MEMBERS", 5):
            self._assert_refused([(f"ws/ws/f{i}", b"x") for i in range(10)])

    def test_manifeste_absent(self):
        path = self.dir / "n.nebmig"
        _write_tar_archive(path, PASS, [("ws/ws/a.txt", b"x")])
        with self.assertRaises(mc.MigrationFormatError):
            mi.preview_archive(str(path), PASS, {})

    def test_version_de_format_future(self):
        self.manifest["format_version"] = 99
        with self.assertRaises(mc.MigrationFormatError):
            mi.preview_archive(str(self._archive([])), PASS, {})

    def test_pas_une_archive(self):
        junk = self.dir / "j.nebmig"
        junk.write_bytes(b"pas une archive" * 20)
        with self.assertRaises(mc.MigrationFormatError):
            mi.preview_archive(str(junk), PASS, {})


def sys_platform() -> str:
    import sys
    return sys.platform


# ---------------------------------------------------------------------------
# Jobs, routes HTTP et secrets
# ---------------------------------------------------------------------------

def _wait(job_id: str, timeout: float = 60.0) -> dict:
    import time
    end = time.time() + timeout
    while time.time() < end:
        status, snap = api_migration.get_job(job_id)
        assert status == 200, snap
        if snap["status"] != "running":
            return snap
        time.sleep(0.05)
    raise AssertionError("job non terminé")


class JobTests(unittest.TestCase):
    def setUp(self):
        self.src = build_source()
        self.out = SANDBOX / "out"
        rmtree(self.out)
        self.out.mkdir()
        self.records: list[str] = []
        self.handler = logging.Handler()
        self.handler.emit = lambda r: self.records.append(r.getMessage())
        self.handler.setLevel(logging.DEBUG)
        logging.getLogger("dashboard").addHandler(self.handler)
        logging.getLogger("dashboard").setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger("dashboard").removeHandler(self.handler)
        rmtree(self.out)

    def _start(self, body):
        status, payload = api_migration.start_job(body)
        return status, payload

    def test_parcours_complet_par_les_jobs(self):
        status, p = self._start({"kind": "estimate"})
        self.assertEqual(status, 202)
        snap = _wait(p["job_id"])
        self.assertEqual(snap["status"], "done")
        self.assertGreater(snap["result"]["total_bytes"], 0)

        with mock.patch("dashcore.migration._default_iterations", return_value=FAST):
            status, p = self._start({"kind": "export", "passphrase": PASS, "passphrase_confirm": PASS,
                                     "dest_dir": str(self.out)})
            self.assertEqual(status, 202)
            snap = _wait(p["job_id"])
        self.assertEqual(snap["status"], "done", snap)
        archive = snap["result"]["path"]
        reset_sandbox()

        status, p = self._start({"kind": "preview", "archive_path": archive, "passphrase": PASS,
                                 "options": {}})
        self.assertEqual(status, 202)
        snap = _wait(p["job_id"])
        self.assertEqual(snap["status"], "done", snap)
        plan_id = snap["result"]["plan_id"]
        self.assertTrue(snap["result"]["plan"]["ok"])

        status, p = self._start({"kind": "import", "plan_id": plan_id, "passphrase": PASS})
        self.assertEqual(status, 202)
        snap = _wait(p["job_id"])
        self.assertEqual(snap["status"], "done", snap)
        self.assertEqual(snap["result"]["workspaces"]["imported"], 2)
        # le plan est consommé : un rejeu est refusé
        status, p = self._start({"kind": "import", "plan_id": plan_id, "passphrase": PASS})
        self.assertEqual((status, p["error_code"]), (409, "plan_expired"))
        # secrets et phrase de passe : ni dans les journaux, ni dans les jobs
        log_text = "\n".join(self.records)
        for needle in (PASS, SECRET):
            self.assertNotIn(needle, log_text)
            self.assertNotIn(needle, json.dumps(snap))

    def test_mauvaise_phrase_de_passe_message_sans_secret(self):
        export_source(self.out)
        archive = str(next(self.out.glob("*.nebmig")))
        status, p = self._start({"kind": "preview", "archive_path": archive,
                                 "passphrase": "phrase erronee tres longue", "options": {}})
        snap = _wait(p["job_id"])
        self.assertEqual((snap["status"], snap["error_code"]), ("error", "bad_passphrase_or_corrupt"))
        self.assertNotIn("phrase erronee", json.dumps(snap))
        self.assertNotIn("phrase erronee", "\n".join(self.records))

    def test_validations(self):
        self.assertEqual(self._start({"kind": "x"})[0], 400)
        self.assertEqual(self._start({"kind": "export", "passphrase": "court", "passphrase_confirm": "court"})[0], 400)
        self.assertEqual(self._start({"kind": "export", "passphrase": PASS, "passphrase_confirm": PASS + "x"})[0], 400)
        self.assertEqual(self._start({"kind": "export", "passphrase": PASS, "passphrase_confirm": PASS,
                                      "workspaces": ["../x"]})[0], 400)
        self.assertEqual(self._start({"kind": "preview", "passphrase": PASS})[0], 400)
        self.assertEqual(self._start({"kind": "import", "plan_id": "inconnu", "passphrase": PASS})[0], 409)
        self.assertEqual(api_migration.get_job("n-existe-pas-1")[0], 404)
        self.assertEqual(api_migration.inspect_archive({"path": "relatif.nebmig"})[0], 400)

    def test_un_seul_job_a_la_fois(self):
        import threading
        gate = threading.Event()
        started = threading.Event()

        def slow(selected, progress, cancel):
            started.set()
            gate.wait(10)
            return {}

        with mock.patch("dashcore.api_migration.run_export", side_effect=lambda *a, **k: (started.set(), gate.wait(10), {})[2]):
            status, p = self._start({"kind": "export", "passphrase": PASS, "passphrase_confirm": PASS,
                                     "dest_dir": str(self.out)})
            self.assertEqual(status, 202)
            started.wait(5)
            status2, p2 = self._start({"kind": "estimate"})
            self.assertEqual((status2, p2["error_code"]), (409, "busy"))
            api_migration.cancel_job(p["job_id"])
            gate.set()
            _wait(p["job_id"])

    def test_estimation_cede_la_place(self):
        import threading
        release = threading.Event()

        def long_estimate(selected, progress, cancel):
            while not cancel():
                if release.wait(0.01):
                    break
            raise mc.MigrationCancelled()

        with mock.patch("dashcore.api_migration.estimate", side_effect=long_estimate):
            status, p = self._start({"kind": "estimate"})
            self.assertEqual(status, 202)
            status2, p2 = self._start({"kind": "estimate"})      # annule la précédente
            self.assertEqual(status2, 202)
            release.set()
            _wait(p2["job_id"])
            self.assertEqual(api_migration.get_job(p["job_id"])[1]["status"], "cancelled")


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import http.client
        cls.http = http.client
        cls.base = SANDBOX / "http-migration"
        rmtree(cls.base)
        cls.base.mkdir()
        cls.server = ServerProcess(cls.base)
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        rmtree(cls.base)

    def _req(self, method, path, body=None, xhr=True):
        conn = self.http.HTTPConnection("127.0.0.1", self.server.port, timeout=30)
        headers = {}
        if xhr:
            headers["X-Nebula-XHR"] = "1"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=data, headers=headers)
            r = conn.getresponse()
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def test_header_anti_csrf_exige_meme_en_get(self):
        for method, path, body in (("GET", "/api/migration/info", None),
                                   ("GET", "/api/migration/jobs/abcdefgh1234", None),
                                   ("POST", "/api/migration/jobs", {"kind": "estimate"}),
                                   ("POST", "/api/migration/inspect-archive", {"path": "/x"}),
                                   ("POST", "/api/migration/find-archives", {"folder": "/x"})):
            status, _ = self._req(method, path, body, xhr=False)
            self.assertEqual(status, 403, (method, path))

    def test_info_et_estimation_http(self):
        status, info = self._req("GET", "/api/migration/info")
        self.assertEqual(status, 200)
        self.assertEqual([w["id"] for w in info["workspaces"]], ["ws1"])
        self.assertGreaterEqual(info["min_passphrase"], 12)
        status, p = self._req("POST", "/api/migration/jobs", {"kind": "estimate"})
        self.assertEqual(status, 202)
        import time
        for _ in range(200):
            status, snap = self._req("GET", f"/api/migration/jobs/{p['job_id']}")
            if snap["status"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(snap["status"], "done")
        status, bad = self._req("POST", "/api/migration/jobs", {"kind": "export", "passphrase": "x"})
        self.assertEqual(status, 400)
        self.assertIn("12 caractères", bad["error"])

    def test_recherche_d_archives_dans_un_dossier(self):
        d = self.base / "recherche"
        rmtree(d)
        status, r = self._req("POST", "/api/migration/find-archives", {"folder": str(d)})
        self.assertEqual((status, r["archives"]), (200, []))          # dossier absent : liste vide
        d.mkdir()
        (d / "autre.txt").write_text("x", encoding="utf-8")
        _write_tar_archive(d / "a.nebmig", PASS, [("x", b"1")])
        (d / "faux.nebmig").write_bytes(b"x" * 300)
        status, r = self._req("POST", "/api/migration/find-archives", {"folder": str(d)})
        self.assertEqual([a["name"] for a in r["archives"]], ["a.nebmig"])
        self.assertNotIn("tag", r["archives"][0])
        status, r = self._req("POST", "/api/migration/find-archives", {"folder": "relatif"})
        self.assertEqual(status, 400)
        status, r = self._req("POST", "/api/migration/inspect-archive", {"path": str(d / "a.nebmig")})
        self.assertEqual((status, r["format_version"]), (200, 1))

    def test_inspection_d_archive(self):
        status, r = self._req("POST", "/api/migration/inspect-archive", {"path": str(self.base / "absent.nebmig")})
        self.assertEqual(status, 400)
        junk = self.base / "junk.nebmig"
        junk.write_bytes(b"x" * 200)
        status, r = self._req("POST", "/api/migration/inspect-archive", {"path": str(junk)})
        self.assertEqual((status, r["error_code"]), (400, "bad_format"))


if __name__ == "__main__":
    unittest.main()
