/* ================================================================
   Nebula - Page Help (aide contextuelle + tutoriels)
   ----------------------------------------------------------------
   renderHelp : dispatcher entre Hub et Topic selon le hash.
   renderHelpHub : grille des topics + sections.
   renderHelpTopic : detail d'un topic avec nav prev/next.
   _helpSections : data des sections (long, structure HTML).
   HELP_TOPICS : liste des topics et leur structure.

   Dependances foundations : escapeHtml, el, btn, I.*, setBreadcrumbs,
   setTopbarActions, $.

   Ref : CM-2 batch 11, refactor 2026-05-13.
   ================================================================ */
'use strict';

function _helpSections() {
  return {
'overview': `
      <h2>${I.home}<span>Vue d'ensemble du dashboard</span></h2>
      <p>Nebula est un <strong>tableau de bord local</strong> qui pilote ton écosystème Claude Code : workspaces (projets), MCPs (serveurs Model Context Protocol), skills, plugins, templates et hooks. Tout est servi par un petit serveur Python sur <code class="mono">127.0.0.1:4777</code> — aucune donnée ne sort de ta machine.</p>
      <div class="help-grid help-grid-3">
        <div class="help-tile">
          <div class="help-tile-icon">${I.box}</div>
          <h4>Workspaces</h4>
          <p>Tes projets Claude Code. Chaque workspace = un dossier disque + un id technique. Tu peux les créer depuis un template, les importer depuis un dossier existant, ou les récupérer du registre Claude.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.cpu}</div>
          <h4>MCPs</h4>
          <p>Serveurs externes qui enrichissent Claude (Filesystem, GitHub, base de données…). Configurés dans le registre central <code class="mono">mcp/registry.json</code> puis distribués vers les workspaces ciblés.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.sparkle}</div>
          <h4>Skills</h4>
          <p>Modules de compétences invocables par Claude. Globaux (pour tous les projets) ou copiés localement dans un workspace.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.plug}</div>
          <h4>Plugins</h4>
          <p>Extensions Claude Code installées via la CLI. Tu peux les <strong>overrider</strong> par workspace (forcer actif/inactif, ou hériter du global).</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.layers}</div>
          <h4>Templates</h4>
          <p>Modèles de structure pour créer rapidement des workspaces. Supportent les placeholders <code class="mono">{{label}}</code>, <code class="mono">{{description}}</code>, etc.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.tools}</div>
          <h4>Outils</h4>
          <p>Variables d'env, hooks globaux, sauvegardes, accès rapide aux fichiers de config. Tout ce qui est transverse au système.</p>
        </div>
      </div>

`,
'onboarding': `
      <h2>${I.download}<span>Premier lancement & import depuis Claude</span></h2>
      <p>Si tu utilises déjà Claude Code, Nebula peut <strong>récupérer ta config existante</strong> en un clic. Trois portes d'entrée :</p>
      <div class="help-step">
        <div class="help-step-num">1</div>
        <div>
          <h4>Wizard "Importer config"</h4>
          <p>Sur la page <strong>Accueil</strong> ou <strong>Outils → Onboarding</strong>, clique sur <em>Importer ma config Claude</em>. Le scanner lit <code class="mono">~/.claude/settings.json</code> et <code class="mono">~/.claude/projects/</code>, te liste les MCPs et workspaces trouvés, et tu coches ceux que tu veux importer. Les éléments déjà connus sont grisés.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">2</div>
        <div>
          <h4>Enregistrer un dossier existant</h4>
          <p>Pour pointer Nebula vers un projet déjà sur disque (sans le déplacer), utilise <em>Enregistrer un dossier</em>. Tu donnes l'ID, le label et le chemin absolu — aucun fichier n'est touché, juste un enregistrement dans <code class="mono">data/workspaces.json</code>.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">3</div>
        <div>
          <h4>Coller du JSON MCP</h4>
          <p>Si tu as un bloc <code class="mono">{"mcpServers": {...}}</code> ou un objet MCP brut, colle-le via <strong>MCPs → Importer</strong>. Nebula détecte automatiquement le format.</p>
        </div>
      </div>
      <div class="callout callout-info">
        <strong>Bon à savoir :</strong> l'import ne touche jamais à <code class="mono">~/.claude/settings.json</code>. Nebula maintient son propre registre dans <code class="mono">mcp/registry.json</code> et distribue ensuite vers les <code class="mono">.mcp.json</code> de chaque workspace via <em>Sync</em>.
      </div>

`,
'workspaces': `
      <h2>${I.box}<span>Workspaces</span></h2>
      <h3>Créer un nouveau workspace</h3>
      <p>Bouton <em>Nouveau workspace</em> sur la Home (ou raccourci <kbd>n</kbd>). Tu fournis :</p>
      <ul class="help-list">
        <li><strong>ID</strong> — identifiant technique (a-z, 0-9, _, -). Sert de nom de dossier et de clé interne.</li>
        <li><strong>Label</strong> — libellé lisible affiché dans l'UI.</li>
        <li><strong>Emoji</strong> — pictogramme pour repérer visuellement le projet.</li>
        <li><strong>Description</strong> et <strong>Outils / contexte</strong> — utilisés comme placeholders dans le template.</li>
        <li><strong>Template</strong> — sélectionne un modèle parmi ceux de la page Templates.</li>
      </ul>
      <p>Nebula crée le dossier <code class="mono">workspaces/&lt;id&gt;/</code>, copie le template en remplaçant les placeholders, génère un <code class="mono">launch-&lt;id&gt;.bat</code> dans <code class="mono">scripts/</code>, et enregistre l'entrée.</p>

      <h3>Importer un dossier existant</h3>
      <p>Si ton projet est déjà ailleurs sur le disque (ex. <code class="mono">D:\\projets\\monapp</code>), utilise <em>+ Dossier</em> sur la Home. Aucun fichier n'est créé ni copié, juste un enregistrement.</p>

      <h3>Lancer Claude Code dans un workspace</h3>
      <p>Bouton <strong>Lancer</strong> ouvre une nouvelle console et exécute <code class="mono">claude</code> dans le dossier. <strong>Reprendre</strong> fait <code class="mono">claude -c</code> pour continuer la dernière session.</p>

      <h3>Page détail d'un workspace</h3>
      <p>Clique sur une carte workspace pour voir : statistiques (sessions, tokens consommés), MCPs scopés, skills locaux, plugins overridés, agents/commandes, et accès rapide aux fichiers de config (<code class="mono">CLAUDE.md</code>, <code class="mono">settings.json</code>, permissions, hooks).</p>

      <div class="callout callout-warn">
        <strong>Suppression :</strong> par défaut, supprimer un workspace ne retire que l'enregistrement (le dossier reste sur disque). Coche <em>Supprimer aussi le dossier</em> pour purger physiquement — irréversible.
      </div>

`,
'mcps': `
      <h2>${I.cpu}<span>MCPs (Model Context Protocol)</span></h2>
      <p>Les MCPs sont des serveurs externes que Claude peut interroger pour accéder à des données ou fonctionnalités. Nebula centralise leur config dans un registre, puis les distribue aux workspaces.</p>

      <h3>Ajouter un MCP</h3>
      <p>Page <strong>MCPs → Nouveau MCP</strong>. Le formulaire change selon le transport choisi.</p>

      <h4>Transport <code class="mono">stdio</code> (le plus courant)</h4>
      <p>Le MCP est un programme local lancé par Claude. Tu fournis :</p>
      <ul class="help-list">
        <li><strong>Command</strong> — exécutable (ex. <code class="mono">npx</code>, <code class="mono">uvx</code>, <code class="mono">python</code>).</li>
        <li><strong>Args</strong> — un argument par ligne (ex. <code class="mono">-y</code>, <code class="mono">@modelcontextprotocol/server-filesystem</code>, <code class="mono">/path/to/dir</code>).</li>
        <li><strong>CWD</strong> (optionnel) — répertoire de travail du process. Utile si le MCP a besoin de fichiers relatifs à un dossier précis.</li>
        <li><strong>Env</strong> — variables d'env, format <code class="mono">KEY=VALUE</code> ou <code class="mono">KEY=\${VAR}</code> pour interpoler depuis <code class="mono">.env.local</code>.</li>
      </ul>

      <h4>Transport <code class="mono">http</code> ou <code class="mono">sse</code></h4>
      <ul class="help-list">
        <li><strong>URL</strong> — endpoint du serveur MCP.</li>
        <li><strong>Headers</strong> — auth & headers custom, format <code class="mono">KEY=VALUE</code> par ligne. Ex. <code class="mono">Authorization=Bearer \${API_TOKEN}</code>.</li>
      </ul>

      <h3>Statut calculé automatiquement</h3>
      <p>Le statut affiché sur la card est dérivé de l'état réel à chaque rafraîchissement (toutes les 30s sur la page MCPs) :</p>
      <ul class="help-list">
        <li><strong>désactivé</strong> — choix manuel (case "Désactiver" dans Modifier).</li>
        <li><strong>à configurer</strong> — config incomplète (pas de command pour stdio, pas d'url pour http/sse).</li>
        <li><strong>disponible</strong> — config OK, prêt à fonctionner.</li>
      </ul>
      <p class="dim" style="font-size:12px">Le statut "connecté" demanderait un test live à chaque check (lourd). Utilise <em>Tester</em> ou <em>Diag</em> pour vérifier en réel.</p>

      <h3>Sauver une config MCP comme recette</h3>
      <p>Tu as configuré un MCP qui marche (HomeAssistant avec ton token, OPNsense avec creds firewall…) ? Tu peux le transformer en <strong>recette locale réutilisable</strong> :</p>
      <ol class="help-list">
        <li>Card MCP → <em>Modifier</em></li>
        <li>Footer du modal → bouton <strong>✨ Sauver comme recette</strong></li>
        <li>Conversion intelligente : chaque var d'env devient un param <code class="mono">\${KEY}</code>. Les noms suggérant un secret (TOKEN, KEY, SECRET, PASSWORD…) sont marqués <code class="mono">secret: true</code> automatiquement.</li>
        <li>Tu ajustes labels/placeholders → <em>Créer la recette</em></li>
      </ol>
      <p>Tu peux ensuite installer cette recette plusieurs fois avec d'autres credentials (cf section <a href="#h-recipes">Recettes</a>).</p>

      <h3>Vue JSON brut</h3>
      <p>L'onglet <em>JSON brut</em> de la modale te permet d'éditer toute la config en un coup, utile pour copier-coller depuis un README de MCP.</p>

      <h3>Workspaces ciblés (checkboxes)</h3>
      <p>Dans le formulaire MCP, le champ <em>Workspaces ciblés</em> liste tes workspaces existants en cases à cocher. Coche ceux qui doivent recevoir ce MCP. Case "★ Tous les workspaces" pour activer partout. <strong>Auto-sync</strong> : le <code class="mono">.mcp.json</code> de chaque workspace ciblé est régénéré immédiatement après le save (toast "MCP créé et synchronisé vers N workspace(s)").</p>

      <div class="callout callout-info">
        <strong>Le registre vs Claude :</strong> le fichier <code class="mono">mcp/registry.json</code> est la source de vérité d'Nebula. À chaque modif, Nebula régénère automatiquement les <code class="mono">.mcp.json</code> dans les workspaces concernés en interpolant les <code class="mono">\${VAR}</code>. Le bouton <em>Sync MCPs</em> sur un workspace n'est plus nécessaire dans le flow normal — utile uniquement pour forcer un re-sync (ex: après changement de <code class="mono">.env.local</code>).
      </div>

`,
'recipes': `
      <h2>${I.sparkle}<span>Recettes MCP — installation 1-clic</span></h2>
      <p>Les <strong>recettes</strong> sont des templates pré-configurés pour les MCPs courants. Plus besoin de chercher la commande, les args, la doc — tu cliques, tu remplis 2 champs, c'est installé.</p>

      <h3>Accès</h3>
      <p>Page <strong>MCPs → Recettes</strong> (bouton dans le topbar). Modale avec deux sections :</p>
      <ul class="help-list">
        <li><strong>📦 Recettes Nebula (catalogue public)</strong> — 8 recettes embarquées : Filesystem, GitHub, Brave Search, Fetch HTTP, Memory, Puppeteer, PostgreSQL, Slack. Mises à jour via auto-update du dashboard.</li>
        <li><strong>🔒 Recettes locales (perso, non partagées)</strong> — Tes recettes propres, stockées dans <code class="mono">dashboard/data/mcp_recipes.local.json</code> (gitignored). Parfait pour les MCPs privés ou propriétaires (OPNsense interne, BDD perso, etc.).</li>
      </ul>

      <h3>Installer une recette</h3>
      <p>Clic sur une carte → modale d'install avec :</p>
      <ul class="help-list">
        <li>ID auto-suggéré (auto-suffixé si déjà pris : <code class="mono">opnsense-2</code>, <code class="mono">opnsense-prod</code>…)</li>
        <li>Champs typés pour chaque param (text ou password selon <code class="mono">secret</code>)</li>
        <li><strong>Aperçu live</strong> de la commande générée — les secrets sont masqués <code class="mono">••••••••</code> à l'écran (sécurité capture)</li>
        <li>Aide contextuelle sous chaque champ + lien doc ↗</li>
      </ul>

      <h3>Recettes = templates réutilisables</h3>
      <p>Une recette n'est pas "à usage unique" — tu peux l'<strong>installer N fois</strong> avec des configs différentes. Ex : 2 firewalls OPNsense, 2 instances GitHub avec des tokens différents (perso/pro), 3 BDD PostgreSQL pour staging/prod/local. La carte affiche un badge <em>"Nx installées"</em>.</p>

      <h3>Créer une recette locale</h3>
      <p>Modale Recettes → bouton <strong>+ Nouvelle recette</strong> → éditeur GUI complet :</p>
      <ul class="help-list">
        <li>Métadonnées : id, nom, emoji, description, URL doc</li>
        <li>Transport (stdio/http/sse) avec champs adaptés</li>
        <li><strong>Liste dynamique de paramètres</strong> : chaque <code class="mono">\${KEY}</code> dans command/args/env doit avoir un param. Bouton <em>+ Ajouter un paramètre</em>, ✗ pour retirer. Cases <code class="mono">secret</code> et <code class="mono">required</code>.</li>
      </ul>

      <h3>Modifier / supprimer une recette locale</h3>
      <p>Sur la carte d'une recette locale → ✎ en haut à droite → ouvre l'éditeur. Bouton 🗑 dans le footer pour supprimer.</p>

      <h3>Workflow MCP existant → recette</h3>
      <p>Tu as déjà un MCP configuré qui marche ? Convertis-le en recette en 1 clic : <em>Modifier</em> sur la card MCP → bouton <strong>✨ Sauver comme recette</strong>. Conversion auto avec détection des secrets. Cf <a href="#h-mcps">section MCPs</a>.</p>

      <div class="callout callout-info">
        <strong>Avantage du modèle recette :</strong> tes recettes locales survivent aux <code class="mono">git pull</code> du dashboard (gitignored) et restent strictement sur ta machine. Le catalogue public, lui, est versionné et reçoit les updates Anthropic / nouveaux MCPs populaires automatiquement via auto-update.
      </div>

`,
'skills': `
      <h2>${I.sparkle}<span>Skills — modèle "magasin"</span></h2>
      <p>Un skill = un dossier contenant <code class="mono">SKILL.md</code> (frontmatter + instructions Markdown). Optionnellement des fichiers de référence (<code class="mono">references/</code>, <code class="mono">examples/</code>).</p>

      <h3>Bibliothèque centralisée (le magasin)</h3>
      <p>Nebula maintient une <strong>bibliothèque</strong> dans <code class="mono">dashboard/data/skills-library/</code> : c'est ta source de vérité, le magasin où tu pioches. La page Skills affiche cette bibliothèque, pas <code class="mono">~/.claude/skills/</code> directement.</p>
      <p>Pourquoi cette indirection : tu peux installer le même skill dans plusieurs workspaces (ex. <code class="mono">n8n-prod</code> + <code class="mono">n8n-dev</code>) avec une seule édition, sans copier-coller manuel.</p>

      <h3>Créer un skill</h3>
      <p>Bouton <strong>Nouveau skill</strong> en haut de la page Skills. Le skill est créé dans la bibliothèque uniquement — non distribué tant que tu n'utilises pas <em>Distribuer</em>.</p>

      <h3>Distribuer un skill</h3>
      <p>Bouton <strong>📤 Distribuer</strong> sur une carte → modal avec checkboxes :</p>
      <ul class="help-list">
        <li><strong>Global</strong> (<code class="mono">~/.claude/skills/&lt;name&gt;/</code>) — actif dans tous les projets</li>
        <li>Une ligne par <strong>workspace</strong> (<code class="mono">&lt;workspace&gt;/.claude/skills/&lt;name&gt;/</code>) — actif uniquement dans ce projet</li>
      </ul>
      <p>Coche pour installer/écraser, décoche pour retirer. C'est un <em>set complet</em> : tu modélises l'état désiré, Nebula ajoute/met à jour/retire en conséquence.</p>

      <h3>Importer depuis GitHub</h3>
      <p>Bouton <strong>📥 Importer GitHub</strong> → colle <code class="mono">user/repo</code> ou une URL complète, choisis la branche (optionnel) → Analyser. Nebula clone en shallow, détecte tous les <code class="mono">SKILL.md</code> du repo, et te laisse choisir lesquels importer dans la bibliothèque + les distribuer immédiatement (Global / workspaces) si tu veux.</p>
      <p>Chaque skill importé reçoit un <code class="mono">.nebula-origin.json</code> qui trace <code class="mono">repo</code>, <code class="mono">branch</code>, <code class="mono">commit</code>, <code class="mono">imported_at</code> — utile pour de futurs checks de mise à jour.</p>

      <h3>Édition centralisée + désync</h3>
      <p>Le bouton <em>Éditer</em> ouvre la version <strong>bibliothèque</strong> du skill. Les copies déjà distribuées <strong>ne sont pas écrasées en silence</strong> — un badge <em>« N désync. »</em> apparaît sur la carte si certaines copies ont divergé. Pour propager les changements : re-clique <em>Distribuer</em>.</p>

      <h3>Ajouter depuis le magasin sur un workspace</h3>
      <p>Sur la page d'un workspace, section <strong>Skills</strong> → bouton <strong>+ Ajouter depuis le magasin</strong>. Modale qui liste les skills de la bibliothèque non encore présents dans ce workspace, avec checkboxes multi-sélection.</p>

      <h3>Migration depuis l'existant</h3>
      <p>Si ta bibliothèque est vide mais qu'Nebula détecte des skills dans <code class="mono">~/.claude/skills/</code> ou dans des workspaces, un bandeau te propose <strong>Importer dans la bibliothèque</strong> en 1 clic. Migration purement additive, aucune copie écrasée.</p>

      <div class="callout callout-info">
        <strong>Activation par Claude :</strong> les skills sont auto-découverts par Claude Code au démarrage de la session — tu n'as rien à enregistrer manuellement. Vérifie qu'ils apparaissent avec <code class="mono">/help</code> ou via le menu skills de Claude.
      </div>

`,
'plugins': `
      <h2>${I.plug}<span>Plugins</span></h2>
      <p>Les plugins Claude Code sont gérés par la CLI <code class="mono">claude plugin</code>. Nebula propose un browser et la gestion du scope par workspace.</p>

      <h3>Installer un plugin</h3>
      <p><strong>Plugins → Installer</strong> ouvre le browser :</p>
      <ul class="help-list">
        <li>Sélecteur de marketplace (auto-détection depuis <code class="mono">~/.claude/plugins/marketplaces/</code>)</li>
        <li>Onglets : <em>Tous</em>, <em>Officiels</em>, <em>Externes</em>, <em>Spec manuel</em></li>
        <li>Filtre de recherche par nom/description</li>
        <li>Bouton <strong>README</strong> pour lire la doc avant install</li>
        <li>Bouton <strong>Installer</strong> qui appelle <code class="mono">claude plugin install &lt;plugin&gt;@&lt;mkt&gt;</code></li>
      </ul>

      <h3>Activer / désactiver / désinstaller</h3>
      <p>Dans la table <em>Installés</em>, le toggle ON/OFF appelle <code class="mono">claude plugin enable/disable</code>. La poubelle désinstalle (avec confirmation).</p>

      <h3>Scope par workspace</h3>
      <p>Section <strong>B. Scope par workspace</strong> : sélectionne un plugin, vois la liste de tous les workspaces. Pour chacun, 3 états :</p>
      <ul class="help-list">
        <li><strong class="text-ok">Actif</strong> — override local : forcer activé pour ce workspace même si désactivé globalement</li>
        <li><strong class="text-err">Inactif</strong> — override local : forcer désactivé pour ce workspace</li>
        <li><strong>Hériter</strong> — pas d'override : suit l'état global du plugin</li>
      </ul>
      <p>Actions de masse (Activer / Désactiver / Réinitialiser pour tous les workspaces filtrés) en haut de la section.</p>

`,
'templates': `
      <h2>${I.layers}<span>Templates</span></h2>
      <p>Un template = un dossier dans <code class="mono">templates/&lt;id&gt;/</code> qui sera copié à chaque création de workspace, en remplaçant les placeholders par les valeurs saisies dans le formulaire "Nouveau workspace".</p>

      <h3>Créer un template — bouton "+ Nouveau template"</h3>
      <p>Choix d'un <strong>starter</strong> pré-rempli :</p>
      <ul class="help-list">
        <li>⭐ <strong>Standard</strong> (recommandé) — CLAUDE.md + .gitignore + README.md déjà câblés avec tous les placeholders.</li>
        <li>📭 <strong>Vide</strong> — juste le <code class="mono">.template.json</code>, à toi de tout construire.</li>
        <li>🐍 <strong>Python</strong>, 🟢 <strong>Node.js</strong>, 🐳 <strong>Docker</strong> — starters spécialisés stack.</li>
      </ul>
      <p>Après création, l'éditeur s'ouvre directement sur le nouveau template — tu peux modifier le contenu, ajouter des fichiers, etc.</p>

      <h3>Les 6 placeholders</h3>
      <ul class="help-list">
        <li><code class="mono">{{name}}</code> → champ <strong>ID</strong> du workspace</li>
        <li><code class="mono">{{label}}</code> → champ <strong>Label</strong></li>
        <li><code class="mono">{{description}}</code> → champ <strong>Description</strong></li>
        <li><code class="mono">{{tools}}</code> → champ <strong>Outils / contexte</strong></li>
        <li><code class="mono">{{emoji}}</code> → champ <strong>Emoji</strong></li>
        <li><code class="mono">{{date}}</code> → date du jour à la création (ISO)</li>
      </ul>

      <h3>Panneau "Conseils & qualité"</h3>
      <p>L'éditeur scanne automatiquement le template et propose des suggestions :</p>
      <ul class="help-list">
        <li>⚠️ Pas de <code class="mono">CLAUDE.md</code> — Claude n'aura pas de contexte projet</li>
        <li>⚠️ Pas de <code class="mono">.gitignore</code> — risque de committer des secrets</li>
        <li>❌ Dossiers interdits détectés (<code class="mono">.git</code>, <code class="mono">node_modules</code>, <code class="mono">__pycache__</code>…)</li>
        <li>ℹ️ Placeholders critiques (<code class="mono">{{name}}</code>, <code class="mono">{{label}}</code>) jamais utilisés</li>
      </ul>
      <p>Score de qualité affiché en badge sur chaque card de la grid Templates.</p>

      <h3>Bouton "👁 Aperçu"</h3>
      <p>Dans l'éditeur, sur la barre d'un fichier ouvert, le bouton <strong>👁 Aperçu</strong> ouvre un modal en lecture seule qui montre le contenu après substitution avec des valeurs de test (<code class="mono">name=mon-projet</code>, <code class="mono">label=Mon Projet</code>, etc.). Pratique pour vérifier que les placeholders sont bien câblés.</p>

      <h3>Édition complète depuis le GUI</h3>
      <p>Bouton <em>Éditer</em> sur une carte template ouvre la modale avec arborescence + éditeur. Ctrl+S pour sauvegarder le fichier ouvert. Le panneau qualité se rafraîchit automatiquement après chaque enregistrement.</p>

      <div class="callout callout-warn">
        <strong>Pièges à éviter :</strong> ne jamais inclure <code class="mono">.git/</code>, <code class="mono">node_modules/</code>, <code class="mono">__pycache__/</code>, ni de fichiers binaires &gt; 512 Kio (non éditables ensuite). Pas de secrets en dur — utilise <code class="mono">\${VAR}</code> + <code class="mono">.env.local</code>.
      </div>

`,
'env': `
      <h2>${I.key}<span>Variables d'environnement (.env.local)</span></h2>
      <p>Tes tokens, clés d'API et mots de passe ne doivent jamais se retrouver écrits en dur dans tes fichiers de config. Nebula te propose un emplacement unique pour les stocker : le fichier <code class="mono">.env.local</code>, qui reste local à ta machine et n'est jamais partagé.</p>

      <h3>À quoi ça sert</h3>
      <p>Tu mets une fois tes secrets dans Nebula, et tu les réutilises dans n'importe quel MCP en écrivant <code class="mono">\${NOM_DE_LA_CLE}</code>. Au moment où Nebula configure le MCP pour ton workspace, il remplace automatiquement par la vraie valeur. Avantages :</p>
      <ul class="help-list">
        <li>Tu peux partager ou versionner tes configs MCP sans risque de fuite</li>
        <li>Quand un token expire, tu le mets à jour une fois et tous tes MCPs sont à jour</li>
        <li>Plus de copier-coller à l'aveugle dans des champs de saisie</li>
      </ul>

      <h3>Gérer tes variables</h3>
      <p>Rendez-vous dans <strong>Outils → Variables d'environnement</strong>. Tu y trouves :</p>
      <ul class="help-list">
        <li>Un formulaire pour ajouter une nouvelle clé et sa valeur</li>
        <li>La liste de tes variables, regroupées par préfixe (toutes les <code class="mono">GITHUB_*</code> ensemble, etc.)</li>
        <li>Un champ de recherche pour filtrer rapidement</li>
        <li>Pour chaque variable : un bouton œil pour révéler la valeur, un crayon pour la modifier, une corbeille pour la supprimer</li>
      </ul>

      <h3>Sécuriser le fichier (Windows)</h3>
      <p>Par défaut, <code class="mono">.env.local</code> est un simple fichier texte sur ton disque. Sur Windows, Nebula peut le chiffrer automatiquement pour qu'il devienne illisible en dehors de ta session.</p>
      <p>Sur la page <strong>Outils → Variables d'environnement</strong>, clique sur <em>Activer le chiffrement</em>. C'est tout — l'édition continue de marcher exactement comme avant, mais le fichier sur disque devient illisible si quelqu'un essaie de l'ouvrir sans passer par Nebula.</p>

      <div class="callout callout-info">
        <strong>Ce que le chiffrement protège</strong>
        <ul class="help-list" style="margin-top:6px">
          <li>Une copie du fichier sur clé USB, disque externe ou sauvegarde cloud reste illisible</li>
          <li>Un autre compte utilisateur sur la même machine n'y a pas accès</li>
          <li>Un coup d'œil par-dessus l'épaule ou un partage d'écran ne révèle rien</li>
        </ul>
      </div>

      <div class="callout callout-warn">
        <strong>À garder en tête avant de chiffrer</strong>
        <ul class="help-list" style="margin-top:6px">
          <li>Le chiffrement est lié à ton compte Windows actuel. Si tu changes de machine, réinstalles Windows, ou utilises un autre compte, tu ne pourras plus déchiffrer le fichier.</li>
          <li>Avant un changement de poste ou une réinstallation, pense à utiliser le bouton <em>Désactiver / Exporter clair</em> pour récupérer tes valeurs et les sauvegarder ailleurs (gestionnaire de mots de passe par exemple).</li>
          <li>Le chiffrement ne protège pas contre un logiciel malveillant qui tournerait déjà sur ta session. La meilleure défense reste un antivirus à jour et la prudence avec les exécutables téléchargés.</li>
        </ul>
      </div>

      <h3>Désactiver le chiffrement</h3>
      <p>Le bouton <em>Désactiver / Exporter clair</em> remet le fichier en clair sur ton disque. Pratique pour faire un backup hors-poste, ou pour migrer vers un autre ordinateur. Tu peux réactiver le chiffrement quand tu veux ensuite.</p>

`,
'scope': `
      <h2>${I.activity}<span>Lier MCPs / skills / plugins à un workspace</span></h2>
      <p>Trois mécaniques différentes selon le type :</p>

      <h3>MCP → workspace</h3>
      <p>Dans la modale d'édition d'un MCP, champ <strong>Workspaces ciblés</strong> :</p>
      <ul class="help-list">
        <li>Liste séparée par virgules : <code class="mono">dev,homeassistant,audit</code></li>
        <li>Wildcard : <code class="mono">*</code> ou <code class="mono">all</code> pour tous les workspaces</li>
        <li>Vide : MCP enregistré mais inactif partout</li>
      </ul>
      <p>Après modification, clique <em>Sync</em> sur la Home (ou <em>Sync MCPs</em> sur la page workspace) pour régénérer les <code class="mono">.mcp.json</code>.</p>

      <h3>Skill → workspace</h3>
      <p>Skills globaux : disponibles partout par défaut. Pour avoir une variante locale spécifique, utilise <em>Copier dans…</em> sur la carte du skill global ou <em>+ ici</em> dans la section Skills d'un workspace.</p>

      <h3>Plugin → workspace</h3>
      <p>Soit depuis la <strong>page Plugins → Scope par workspace</strong> (vue par plugin), soit depuis la <strong>page workspace → Plugins</strong> (vue par workspace). Les deux contrôlent le même fichier <code class="mono">.claude/settings.json</code> du workspace.</p>

`,
'tools': `
      <h2>${I.tools}<span>Outils & maintenance</span></h2>
      <ul class="help-list">
        <li><strong>Apparence</strong> — choix du thème (Nebula sombre/clair, Marine, Forêt, Brique). Persisté côté serveur (<code class="mono">data/ui_state.json</code>) avec cache localStorage pour éviter le flash au chargement.</li>
        <li><strong>Onboarding</strong> — checklist de découverte + bouton <em>Conflits Claude global</em> (détecte les MCPs en doublon entre Nebula et <code class="mono">~/.claude.json</code> ou <code class="mono">settings.json</code>, avec backup auto avant nettoyage).</li>
        <li><strong>Accès rapide</strong> — boutons pour ouvrir directement les fichiers de config dans l'explorateur ou le bloc-notes.</li>
        <li><strong>Hooks globaux</strong> — édition des hooks Claude Code de <code class="mono">~/.claude/settings.json</code>.</li>
        <li><strong>Sauvegardes</strong> — copie horodatée de <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code>.</li>
        <li><strong>Variables d'environnement</strong> — éditeur GUI pour <code class="mono">.env.local</code> (cf section 9).</li>
        <li><strong>Maintenance</strong> — nettoyage des <code class="mono">.bat</code> orphelins (workspaces supprimés mais script de lancement encore présent).</li>
      </ul>
      <div class="callout callout-info">
        <strong>Note :</strong> l'import de MCPs depuis du JSON brut se fait directement sur la page MCPs (bouton <em>Importer</em>) — pas de doublon dans Outils.
      </div>

`,
'reflexive': `
      <h2>${I.brain}<span>Reflexive — boucle d'amélioration</span></h2>
      <p>Reflexive observe les sessions Claude Code et mesure leur qualité sur 4 dimensions, pour faire émerger des propositions d'amélioration concrètes. <strong>Optionnel</strong> et <strong>opt-in par workspace</strong> : aucun workspace n'est observé tant que tu n'as pas activé le toggle.</p>
      <h3>À quoi ça sert</h3>
      <p>Au fil des sessions, le score moyen et les <em>flags</em> récurrents (ex. <code class="mono">missing-claude-md-read</code>, <code class="mono">redundant-grep</code>) révèlent des patterns que tu peux corriger via un skill, une convention dans <code class="mono">CLAUDE.md</code> ou un hook. Chaque correctif vient avec un <em>plan de mesure</em> qui vérifie si l'amélioration tient sur N interactions suivantes.</p>
      <h3>Activer Reflexive sur un workspace</h3>
      <ol class="help-list">
        <li>Page <strong>Accueil</strong> → menu d'une card workspace → <em>Modifier</em>.</li>
        <li>Active le switch <strong>Observer cet espace</strong>.</li>
        <li>Les hooks (<code class="mono">SessionStart</code>, <code class="mono">PostToolUse</code>, <code class="mono">Stop</code>) sont ajoutés au <code class="mono">.claude/settings.json</code> du workspace (avec backup <code class="mono">.bak</code>, sans toucher aux hooks tiers).</li>
      </ol>
      <h3>Lire les stats</h3>
      <ul class="help-list">
        <li><strong>Vue d'ensemble</strong> (<kbd>g</kbd> <kbd>r</kbd>) : score moyen + tendance, courbe 30 jours, barres par dimension (la plus basse est le meilleur axe d'attaque).</li>
        <li><strong>Interactions</strong> : table cliquable → modale avec full transcript / tools / files / éval.</li>
        <li><strong>Propositions</strong> : cards Apply / Reject. Le rejet capture une raison pour ajuster le diagnostician.</li>
        <li><strong>Mesures en cours</strong> : les plans déclenchés par les propositions appliquées.</li>
      </ul>
      <h3>Dépannage</h3>
      <ul class="help-list">
        <li><strong>Un hook plante</strong> : l'erreur est loggée dans <code class="mono">dashboard/data/reflexive_hook_errors.log</code>. Les hooks Reflexive ne font <em>jamais</em> échouer une session Claude Code (toute exception est ravalée).</li>
        <li><strong>Désactiver proprement</strong> : repasser le toggle en off retire les hooks Reflexive du <code class="mono">settings.json</code> sans toucher aux autres entrées.</li>
        <li><strong>Réinitialiser la DB</strong> : arrêter le dashboard puis supprimer <code class="mono">dashboard/data/reflexive.db*</code>. La DB sera recréée vide au prochain démarrage.</li>
      </ul>
      <div class="callout callout-info">
        <strong>Sobriété :</strong> Reflexive ne signale rien tant qu'un pattern n'a pas été observé sur ≥5 interactions cohérentes. Mieux vaut zéro proposition qu'une proposition faible.
      </div>

`,
'shortcuts': `
      <h2>${I.zap}<span>Raccourcis clavier</span></h2>
      <table class="help-shortcuts">
        <tr><td><kbd>/</kbd> ou <kbd>Ctrl</kbd>+<kbd>K</kbd></td><td>Ouvrir la palette de recherche globale</td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>h</kbd></td><td>Aller à l'<strong>Accueil</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>m</kbd></td><td>Aller aux <strong>MCPs</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>p</kbd></td><td>Aller aux <strong>Plugins</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>k</kbd></td><td>Aller aux <strong>Skills</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>t</kbd></td><td>Aller aux <strong>Templates</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>o</kbd></td><td>Aller aux <strong>Outils</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>a</kbd></td><td>Aller à l'<strong>Aide</strong> (cette page)</td></tr>
        <tr><td><kbd>n</kbd></td><td>Nouveau workspace</td></tr>
        <tr><td><kbd>m</kbd></td><td>Nouveau MCP</td></tr>
        <tr><td><kbd>s</kbd></td><td>Sync tous les workspaces</td></tr>
        <tr><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Sauvegarder le fichier en cours d'édition (modales template/skill)</td></tr>
        <tr><td><kbd>Esc</kbd></td><td>Fermer une modale ou la palette</td></tr>
      </table>
      <div class="callout callout-info">
        Les raccourcis clavier <strong>ignorent</strong> les zones de saisie : tu peux taper sans déclencher les chords.
      </div>

`,
'update': `
      <h2>${I.refresh}<span>Auto-update bulletproof</span></h2>
      <p>Le dashboard se met à jour <strong>via git</strong>. Tant que ton install est un clone du repo public, tu reçois les nouvelles fonctionnalités automatiquement.</p>

      <h3>Vérification automatique</h3>
      <ul class="help-list">
        <li><strong>1ʳᵉ vérif de session</strong> — un fermer/rouvrir d'onglet (ou un nouveau navigateur) déclenche systématiquement un <code class="mono">git fetch</code> frais, peu importe quand le dernier check a eu lieu. Garantit qu'un refresh montre toujours les MAJ disponibles.</li>
        <li><strong>Anti-spam</strong> — au sein d'une même session, l'intervalle entre 2 fetchs distants est de <strong>1h</strong> (pour ne pas marteler le remote).</li>
        <li><strong>Re-check périodique</strong> — toutes les 30 min en arrière-plan tant que l'onglet reste ouvert.</li>
        <li>Si des commits sont en attente : <strong>badge gradient pulsant "X MAJ"</strong> apparaît dans le topbar à droite (visible sur toutes les pages), plus un badge descriptif dans la sidebar footer.</li>
      </ul>

      <h3>Appliquer une mise à jour</h3>
      <p>Clic sur le badge → modale avec : version locale (sha), tracking branch, liste des commits à venir (sha + message + auteur + date relative).</p>
      <p>Bouton <em>Appliquer</em> → exécute <code class="mono">git pull --ff-only</code>. Détection auto :</p>
      <ul class="help-list">
        <li>Si seuls JS/CSS/HTML ont changé → bouton <em>Recharger la page</em> (F5 suffit).</li>
        <li>Si du Python a changé → bandeau <em>Redémarrage requis</em>, ferme la console et relance <code class="mono">start-dashboard.bat</code>.</li>
      </ul>

      <h3>Zéro blocage : auto-stash systématique</h3>
      <p>Si tu as des modifs locales (fichiers édités, supprimés, ou untracked) au moment de l'update, Nebula fait un <code class="mono">git stash --include-untracked</code> automatique avec un label horodaté <strong>avant</strong> le pull, puis <code class="mono">git stash pop</code> pour restaurer après. Aucune intervention manuelle requise.</p>
      <p>Si le pop échoue (vraie collision avec les changements distants), tes modifs sont <strong>préservées dans la pile stash</strong> (visibles via <code class="mono">git stash list</code>) — aucune perte de données possible. Un warning explicite te donne le label de stash pour récupération CLI.</p>

      <h3>Escape hatch : Réinitialiser à la version distante</h3>
      <p>Si le pull échoue malgré l'auto-stash (cas exceptionnel : branche divergée, état corrompu…), un panneau <strong>"Forcer l'alignement"</strong> apparaît avec un bouton <em>Réinitialiser à la version distante</em> :</p>
      <ul class="help-list">
        <li>Pré-stash systématique avant le reset</li>
        <li>Exécute <code class="mono">git fetch + git reset --hard origin/main</code></li>
        <li>Tes données utilisateur (registry, workspaces.json, .env.local, mémoire perso) sont préservées via <code class="mono">.gitignore</code> et <code class="mono">--skip-worktree</code></li>
      </ul>

      <h3>Modes de panne couverts</h3>
      <ul class="help-list">
        <li>Modifs locales sur fichiers trackés → auto-stash</li>
        <li>Fichiers supprimés localement (<code class="mono">D ...</code>) → auto-stash</li>
        <li>Fichiers untracked qui collisionnent → auto-stash</li>
        <li>Lock orphelin <code class="mono">.git/index.lock</code> > 60s → retiré automatiquement</li>
        <li>Branches divergées → hint + bouton reset</li>
        <li>Réseau / auth / disque plein → hint humain explicite</li>
      </ul>

      <div class="callout callout-info">
        <strong>Aucun mode de panne n'est silencieux.</strong> Chaque erreur git remonte avec un hint humain et le stderr brut accessible (collapsable) pour debug.
      </div>

`,
'troubleshoot': `
      <h2>${I.alert}<span>Dépannage</span></h2>

      <h3>"Serveur hors ligne" en bas de page</h3>
      <p>Le serveur Python n'a pas démarré ou a crashé. Relance <code class="mono">scripts\\start-dashboard.bat</code> et vérifie les logs dans <code class="mono">logs\\dashboard.log</code>.</p>

      <h3>Sanity check signale "désync"</h3>
      <p>Le registre MCP a changé mais les workspaces n'ont pas été re-synchronisés. Clique <em>Sync tous</em> sur la Home, ou <em>Sync MCPs</em> sur le workspace concerné.</p>

      <h3>Sanity check signale "env manquant"</h3>
      <p>Un <code class="mono">\${VAR}</code> dans une config MCP n'est pas défini dans <code class="mono">.env.local</code>. Va dans <strong>Outils → Variables d'environnement</strong> et ajoute la valeur.</p>

      <h3>Plugin présent dans le matrix mais "absent du disque"</h3>
      <p>Le plugin est listé dans <code class="mono">~/.claude/settings.json</code> mais son dossier a été supprimé. Désinstalle-le proprement via le bouton poubelle pour nettoyer la config.</p>

      <h3>Test MCP échoue avec "Commande introuvable"</h3>
      <p>L'exécutable de la commande n'est pas dans le PATH. Vérifie que <code class="mono">node</code> / <code class="mono">python</code> / <code class="mono">uvx</code> sont accessibles depuis un terminal système. Sur Windows, <code class="mono">npx</code> s'appelle parfois <code class="mono">npx.cmd</code>.</p>

      <h3>MCPs en doublon entre Nebula et la config Claude globale</h3>
      <p>Si tu avais des MCPs dans <code class="mono">~/.claude.json</code> ou <code class="mono">~/.claude/settings.json</code> avant d'utiliser Nebula, ils peuvent maintenant exister à deux endroits. Ouvre <strong>Outils → Onboarding → Conflits Claude global</strong> pour les détecter et les nettoyer (avec backup automatique). Une bannière jaune apparaît aussi sur la page MCPs si des conflits sont présents.</p>

      <h3>Réinitialiser un workspace cassé</h3>
      <p>Supprime via le GUI <strong>sans</strong> cocher la purge — ça retire seulement l'entrée du registre, le dossier reste intact. Tu peux ensuite réimporter avec <em>+ Dossier</em>.</p>

      <h3>Backup avant manipulation risquée</h3>
      <p><strong>Outils → Sauvegardes → Sauvegarder maintenant</strong> copie <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code> avec timestamp. À faire avant tout import massif ou bidouille manuelle.</p>
`,
  };
}

// ── Aide : topics (groupements de sections) ────────────────────────────────
const HELP_TOPICS = [
  { id: 'premiers-pas',   emoji: '🚀', title: 'Premiers pas',         summary: 'Découvre Nebula et importe ta config Claude existante.',          sections: ['overview', 'onboarding'] },
  { id: 'workspaces',     emoji: '🗂️', title: 'Workspaces',            summary: 'Créer, importer, lancer et gérer tes projets Claude Code.',       sections: ['workspaces', 'scope'] },
  { id: 'mcps',           emoji: '🔌', title: 'MCPs',                  summary: 'Configurer les serveurs Model Context Protocol et leurs recettes.', sections: ['mcps', 'recipes'] },
  { id: 'skills-plugins', emoji: '✨', title: 'Skills & Plugins',      summary: 'Bibliothèque de compétences et extensions Claude Code.',          sections: ['skills', 'plugins'] },
  { id: 'templates',      emoji: '📋', title: 'Templates',             summary: 'Modèles réutilisables pour démarrer un workspace rapidement.',    sections: ['templates'] },
  { id: 'secrets',        emoji: '🔐', title: 'Secrets & sécurité',    summary: 'Stockage centralisé de tes tokens et clés d\'API, chiffrement.',  sections: ['env'] },
  { id: 'outils',         emoji: '🛠️', title: 'Outils & maintenance',  summary: 'Hooks, sauvegardes, mises à jour automatiques.',                  sections: ['tools', 'update'] },
  { id: 'reflexive',      emoji: '🧠', title: 'Reflexive',              summary: 'Boucle d\'observation et d\'amélioration mesurable de Claude.',    sections: ['reflexive'] },
  { id: 'reference',      emoji: '⌨️', title: 'Référence & dépannage', summary: 'Raccourcis clavier et solutions aux problèmes courants.',         sections: ['shortcuts', 'troubleshoot'] },
];

/* ================================================================
   PAGE AIDE (hub + topics)
   ================================================================ */
async function renderHelp() {
  setBreadcrumbs([{ label: 'Aide' }]);
  const tourBtn = btn('🎯 Visite guidée', 'btn-primary', null);
  tourBtn.title = 'Lance un tour interactif en 8 étapes (~2 min)';
  tourBtn.addEventListener('click', () => startTour('main'));
  setTopbarActions([tourBtn]);

  const hash = location.hash;
  const m = hash.match(/^#\/aide\/([a-z0-9-]+)$/);
  if (m) {
    const topic = HELP_TOPICS.find(t => t.id === m[1]);
    if (topic) return renderHelpTopic(topic);
  }
  return renderHelpHub();
}

function renderHelpHub() {
  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">05.</span><span>Documentation</span></div>
      <h1 class="page-title">Aide & guide d'utilisation</h1>
      <p class="page-subtitle">Choisis un sujet pour en savoir plus. Chaque page est courte et autonome.</p>
    </div>
  `));

  // Promo visite guidée si jamais lancée
  let tourCompleted = false;
  try { tourCompleted = localStorage.getItem('nebula-tour-completed') === '1'; } catch {}
  if (!tourCompleted) {
    const promo = el('div', 'callout callout-info');
    promo.style.marginBottom = 'var(--sp-4)';
    promo['innerHTML'] = `
      <div>
        <strong>🎯 Première fois ici ?</strong>
        <p style="margin:4px 0 0;font-size:12.5px">Lance la <strong>visite guidée interactive</strong> (~2 min) — elle te montre les fonctions essentielles avec spotlight sur l'UI réelle.</p>
      </div>
    `;
    const launchBtn = btn('Démarrer la visite', 'btn-primary', null);
    launchBtn.style.marginTop = '8px';
    launchBtn.addEventListener('click', () => startTour('main'));
    promo.querySelector('div').appendChild(launchBtn);
    page.appendChild(promo);
  }

  // Grille de cartes
  const grid = el('div', 'help-hub-grid');
  for (const t of HELP_TOPICS) {
    const card = el('a', 'help-hub-card');
    card.href = `#/aide/${t.id}`;
    card['innerHTML'] = `
      <div class="help-hub-emoji">${t.emoji}</div>
      <div class="help-hub-title">${escapeHtml(t.title)}</div>
      <div class="help-hub-summary">${escapeHtml(t.summary)}</div>
    `;
    grid.appendChild(card);
  }
  page.appendChild(grid);

  c.appendChild(page);
}

function renderHelpTopic(topic) {
  setBreadcrumbs([
    { label: 'Aide', href: '#/aide' },
    { label: topic.title },
  ]);
  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');

  // Header avec bouton retour
  const header = el('div', 'page-header');
  header['innerHTML'] = `
    <div class="page-header-text">
      <div class="page-eyebrow"><a href="#/aide" style="color:inherit;text-decoration:none">← Toutes les aides</a></div>
      <h1 class="page-title">${topic.emoji} ${escapeHtml(topic.title)}</h1>
      <p class="page-subtitle">${escapeHtml(topic.summary)}</p>
    </div>
  `;
  page.appendChild(header);

  // Contenu : concatène les sections de ce topic
  const sections = _helpSections();
  const content = el('div', 'help-content help-content-single');
  let html = '';
  for (const secId of topic.sections) {
    html += `<section>${sections[secId] || ''}</section>`;
  }
  content['innerHTML'] = html;
  page.appendChild(content);

  // Navigation entre topics (précédent / suivant)
  const idx = HELP_TOPICS.findIndex(t => t.id === topic.id);
  const prev = idx > 0 ? HELP_TOPICS[idx - 1] : null;
  const next = idx < HELP_TOPICS.length - 1 ? HELP_TOPICS[idx + 1] : null;
  const nav = el('div', 'help-topic-nav');
  nav['innerHTML'] = `
    ${prev ? `<a href="#/aide/${prev.id}" class="help-nav-link"><span class="dim">← Précédent</span><strong>${prev.emoji} ${escapeHtml(prev.title)}</strong></a>` : '<span></span>'}
    ${next ? `<a href="#/aide/${next.id}" class="help-nav-link" style="text-align:right"><span class="dim">Suivant →</span><strong>${next.emoji} ${escapeHtml(next.title)}</strong></a>` : '<span></span>'}
  `;
  page.appendChild(nav);

  c.appendChild(page);
  window.scrollTo({ top: 0, behavior: 'instant' });
}
