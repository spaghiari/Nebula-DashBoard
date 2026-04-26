# Checklist de validation — avant push

Workflow recommandé :

```bash
cd C:\claude-workspace\dashboard
python tools/preflight.py    # automatique, ~5s
# Si PASS, faire les vérifs UI ci-dessous puis push
```

---

## 1. Preflight automatique (`tools/preflight.py`)

Couvre :
- Imports de tous les modules `dashcore/*`
- Démarrage serveur sur port libre
- Tous les endpoints GET globaux (HTTP 200 attendu)
- Round-trip POST/GET sur `/api/ui-state`
- GET workspace-scoped sur le 1er workspace du registre

**À faire si rouge** : corriger avant tout push.

---

## 2. Vérifs manuelles UI (non automatisables)

Ouvrir http://127.0.0.1:4777/ et vérifier :

### Navigation & rendu
- [ ] La page se charge sans erreur console (F12)
- [ ] Le thème en cours s'applique sans flash blanc au reload
- [ ] La sidebar liste tous les workspaces
- [ ] Cliquer sur un workspace charge sa page sans 404

### Workspace
- [ ] Bouton "Reprendre" → ouvre un terminal dans le bon répertoire avec `claude -c` (pas d'erreur "syntaxe... incorrecte")
- [ ] Onglet Sessions : la liste s'affiche, cliquer ouvre une session
- [ ] Onglet MCPs : statut affiché par MCP
- [ ] Onglet Skills/Agents/Commands : liste correcte
- [ ] Édition CLAUDE.md → save → reload → contenu persisté

### MCPs
- [ ] Onglet MCPs global : liste du registre
- [ ] Bouton "Tester" sur un MCP renvoie un résultat
- [ ] "Sync all" termine sans erreur

### Wizard d'import (si premier lancement ou reset)
- [ ] Le scan détecte les MCPs de `~/.claude.json` (sous `projects.*.mcpServers`)
- [ ] Le scan détecte les MCPs de `~/.claude/settings.json` et `settings.local.json`
- [ ] Le scan détecte les projets dans `~/.claude/projects/`
- [ ] Cocher + importer crée bien les workspaces

### Thème & onboarding (persistance serveur)
- [ ] Changer de thème → recharger la page → thème conservé
- [ ] Changer de thème → vider le `localStorage` du navigateur → recharger → thème conservé (vient de `data/ui_state.json`)
- [ ] Wizard ne se relance pas après un complete (sauf si on clique "Rejouer le tutoriel")

### Auto-update
- [ ] Onglet Mises à jour → "Vérifier" → status correct (ne doit PAS dire "Mise à jour bloquée" si on n'a rien modifié localement)
- [ ] Si commits en attente : "Appliquer" pull bien, indique si redémarrage nécessaire

---

## 3. Vérif git AVANT push (côté repo public)

```bash
cd C:\claude-workspace-export
git status --porcelain
```

Doit afficher **uniquement** des fichiers listés dans `USER_DATA_FILES` (`dashcore/system_update.py`) :
- `mcp/registry.json{,.bak}`
- `dashboard/data/workspaces.json`
- `dashboard/data/ui_state.json`
- `memory/journal.md`
- `.gitlab-ci.yml`
- `.gitignore`

Si autre chose apparaît : ajouter à `USER_DATA_FILES` ou au `.gitignore` (et committer le `.gitignore`).

---

## 4. Process complet

```bash
# 1. Coder dans C:\claude-workspace\
# 2. Tester
cd C:\claude-workspace\dashboard
python tools/preflight.py
# (vérifs UI manuelles)

# 3. Synchroniser vers l'export
cp <fichiers modifiés> C:\claude-workspace-export\<chemin équivalent>

# 4. Vérifier
cd C:\claude-workspace-export
git status --porcelain  # doit être propre (hors USER_DATA_FILES)

# 5. Commit + push
git add <fichiers>
git commit -m "..."
git push
```
