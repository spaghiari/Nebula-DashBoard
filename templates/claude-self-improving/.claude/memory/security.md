# security

Hub des conventions de sécurité pour `{{label}}`. À rédiger lors du
bootstrap et enrichir avec des spokes dans `security/` quand le
contenu grossit.

## Sous-thématiques

(À créer selon la stack et les besoins du projet)

| Spoke (à créer) | Sujet typique |
|---|---|
| `security/auth.md` | Authentification, sessions, tokens |
| `security/rbac.md` | Permissions, restrictions, contrôle d'accès |
| `security/csrf.md` | Protection CSRF (si applicable) |
| `security/validation.md` | Validation des inputs aux frontières |
| `security/exceptions.md` | Gestion des exceptions, propagation des erreurs |

## Règles ALWAYS-ON sécurité

(À rédiger au bootstrap. Par exemple : deny-by-default, jamais de
secrets en clair dans le code, validation systématique aux frontières,
CSRF sur toute mutation, etc.)
