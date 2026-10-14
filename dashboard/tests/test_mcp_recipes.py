"""Recettes MCP : catalogue livré cohérent, recettes locales (CRUD + validation)."""
from __future__ import annotations

import json
import re
import unittest

from _support import DASHBOARD_DIR, read_json_file, reset_sandbox, write_json_file
from dashcore import api_mcps
from dashcore.config import ALLOWED_TRANSPORTS, MCP_RECIPES_FILE, MCP_RECIPES_LOCAL_FILE
from dashcore.helpers import CorruptJsonError, safe_id

SHIPPED_RECIPES = DASHBOARD_DIR / "data" / "mcp_recipes.json"
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def _placeholders(recipe: dict) -> set[str]:
    blob = json.dumps([recipe.get("command"), recipe.get("url"), recipe.get("args"),
                       recipe.get("env"), recipe.get("headers")])
    return set(_PLACEHOLDER.findall(blob))


def _check_recipe(tc: unittest.TestCase, r: dict) -> None:
    rid = r.get("id")
    tc.assertTrue(safe_id(rid or ""), f"id invalide : {rid!r}")
    tc.assertTrue(r.get("name"), rid)
    transport = r.get("transport", "stdio")
    tc.assertIn(transport, ALLOWED_TRANSPORTS, rid)
    if transport == "stdio":
        tc.assertTrue((r.get("command") or "").strip(), f"{rid} : command requis")
        tc.assertIsInstance(r.get("args", []), list, rid)
    else:
        tc.assertTrue((r.get("url") or "").strip(), f"{rid} : url requis")
    tc.assertIsInstance(r.get("env", {}), dict, rid)
    params = r.get("params", [])
    tc.assertIsInstance(params, list, rid)
    keys = [p.get("key") for p in params]
    for p in params:
        tc.assertTrue(p.get("key") and p.get("label"), f"{rid} : param sans key/label")
    tc.assertEqual(len(keys), len(set(keys)), f"{rid} : clé de param en double")
    # Tout ${KEY} utilisé doit être déclaré en param (sinon substitution impossible
    # côté formulaire) ; un param déclaré non utilisé est un oubli.
    used = _placeholders(r)
    tc.assertEqual(used - set(keys), set(), f"{rid} : placeholders non déclarés")
    tc.assertEqual(set(keys) - used, set(), f"{rid} : params jamais utilisés")


@unittest.skipUnless(SHIPPED_RECIPES.is_file(), "catalogue livré absent")
class ShippedCatalogTests(unittest.TestCase):
    """Le catalogue versionné (`dashboard/data/mcp_recipes.json`), lu tel quel."""

    def setUp(self):
        self.data = json.loads(SHIPPED_RECIPES.read_text(encoding="utf-8"))

    def test_structure(self):
        self.assertIsInstance(self.data.get("recipes"), list)
        self.assertTrue(self.data["recipes"])
        ids = [r.get("id") for r in self.data["recipes"]]
        self.assertEqual(len(ids), len(set(ids)), "ids en double")

    def test_chaque_recette(self):
        for r in self.data["recipes"]:
            with self.subTest(recette=r.get("id")):
                _check_recipe(self, r)

    def test_modele_local_coherent(self):
        for r in api_mcps._LOCAL_RECIPES_TEMPLATE["recipes"]:
            with self.subTest(recette=r.get("id")):
                _check_recipe(self, r)


class LocalRecipesTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        write_json_file(MCP_RECIPES_FILE, {"version": 1, "recipes": [
            {"id": "pub", "name": "Pub", "transport": "stdio", "command": "npx"}]})

    def _recipe(self, **kw):
        r = {"id": "perso", "name": "Perso", "transport": "stdio", "command": "uvx",
             "args": ["srv", "${URL}"], "params": [{"key": "URL", "label": "URL"}]}
        r.update(kw)
        return r

    def test_liste_public_et_local_marques(self):
        status, p = api_mcps.list_mcp_recipes()
        self.assertEqual(status, 200)
        self.assertEqual([(r["id"], r["source"]) for r in p["recipes"]], [("pub", "public")])
        self.assertFalse(p["local_file_exists"])
        # Le 1er ajout crée le fichier local à partir du modèle (exemple opnsense).
        api_mcps.add_or_update_local_recipe(self._recipe())
        status, p = api_mcps.list_mcp_recipes()
        self.assertEqual([(r["id"], r["source"]) for r in p["recipes"]],
                         [("pub", "public"), ("opnsense", "local"), ("perso", "local")])
        self.assertTrue(p["local_file_exists"])

    def test_ensure_cree_le_modele_une_seule_fois(self):
        path = api_mcps.ensure_local_recipes_file()
        self.assertEqual(path, MCP_RECIPES_LOCAL_FILE)
        self.assertEqual(read_json_file(path)["recipes"][0]["id"], "opnsense")
        write_json_file(path, {"version": 1, "recipes": []})
        api_mcps.ensure_local_recipes_file()
        self.assertEqual(read_json_file(path)["recipes"], [])  # pas écrasé

    def test_creation_mise_a_jour_suppression(self):
        status, p = api_mcps.add_or_update_local_recipe(self._recipe(source="local"))
        self.assertEqual((status, p["action"]), (200, "created"))
        status, p = api_mcps.add_or_update_local_recipe(self._recipe(name="Renommée"))
        self.assertEqual((status, p["action"]), (200, "updated"))
        stored = [r for r in read_json_file(MCP_RECIPES_LOCAL_FILE)["recipes"] if r["id"] == "perso"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["name"], "Renommée")
        self.assertNotIn("source", stored[0])  # champ d'affichage jamais persisté
        self.assertEqual(api_mcps.delete_local_recipe("perso")[0], 200)
        self.assertEqual(api_mcps.delete_local_recipe("perso")[0], 404)
        self.assertEqual(api_mcps.delete_local_recipe("../x")[0], 400)

    def test_validation(self):
        cases = [
            self._recipe(id="../x"),
            self._recipe(transport="ftp"),
            self._recipe(command="  "),
            self._recipe(transport="http", url=""),
            self._recipe(params="URL"),
            self._recipe(params=[{"key": "URL"}]),
        ]
        for r in cases:
            with self.subTest(recette=r):
                status, _ = api_mcps.add_or_update_local_recipe(r)
                self.assertEqual(status, 400)
        self.assertFalse(MCP_RECIPES_LOCAL_FILE.exists())
        status, _ = api_mcps.add_or_update_local_recipe(
            self._recipe(transport="http", url="https://x.lan/${URL}", command=None))
        self.assertEqual(status, 200)

    def test_fichier_local_corrompu_jamais_ecrase(self):
        MCP_RECIPES_LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        MCP_RECIPES_LOCAL_FILE.write_text("{cassé", encoding="utf-8")
        with self.assertRaises(CorruptJsonError):
            api_mcps.add_or_update_local_recipe(self._recipe())
        with self.assertRaises(CorruptJsonError):
            api_mcps.delete_local_recipe("perso")
        self.assertEqual(MCP_RECIPES_LOCAL_FILE.read_text(encoding="utf-8"), "{cassé")


if __name__ == "__main__":
    unittest.main()
