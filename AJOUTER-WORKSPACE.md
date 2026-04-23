# Ajouter un nouveau workspace

## Méthode rapide (recommandée)

Via le **dashboard** : bouton "+ Nouveau" → choisir un template → remplir
label/description.

Via la ligne de commande :

    scripts\new-workspace.bat

Le script crée le dossier, le CLAUDE.md et le script de lancement
automatiquement.

## Méthode manuelle (3 étapes)

### 1. Créer le dossier

    mkdir workspaces\mon-projet

### 2. Créer le CLAUDE.md

Copier depuis un template comme base :

    copy templates\blank\CLAUDE.md workspaces\mon-projet\CLAUDE.md

Sections utiles :

    ## Contexte          → ce que fait ce workspace
    ## Outils            → stack technique utilisée ici
    ## Tâches fréquentes → les 3-5 choses que tu fais souvent
    ## Conventions       → préférences de réponse pour ce contexte

### 3. Créer le script de lancement (optionnel)

Duplique un script `launch-*.bat` et édite la ligne `cd /d` :

    @echo off
    echo.
    echo  +======================================+
    echo  ^|   Claude Code -- Mon Projet          ^|
    echo  +======================================+
    echo.
    cd /d C:\claude-workspace\workspaces\mon-projet
    claude

## Lancement

    cd workspaces\mon-projet
    claude

Claude Code lit le `CLAUDE.md` du dossier automatiquement.

## Ajouter au dashboard

Si tu l'as créé manuellement, ajoute-le dans `dashboard\data\workspaces.json` :

    {
      "id": "mon-projet",
      "label": "Mon Projet",
      "emoji": "🔧",
      "description": "Description courte",
      "path": "C:\\claude-workspace\\workspaces\\mon-projet"
    }
