# Workspace — {{label}}

## Contexte
{{description}}

## Structure
- `src/`         — code source
- `package.json` — scripts + deps
- `README.md`    — usage

## Tâches fréquentes
1. Ajouter une dépendance (`npm install X`)
2. Écrire un script npm
3. Intégrer une API externe (fetch natif Node 18+)
4. Tester : `node --test` ou `vitest`
5. Packager / publier

## Conventions
- ESM (`"type": "module"` dans package.json)
- Node 20+
- `async/await`, pas de `.then()` à la chaîne
- Pas de dépendance inutile — préférer la stdlib quand c'est possible
- Commit du `package-lock.json`
