/* ================================================================
   Nebula - Page Help (aide contextuelle + tutoriels)
   ----------------------------------------------------------------
   renderHelp : dispatcher entre Hub et Topic selon le hash.
   renderHelpHub : cartes des topics (+ titres de sections) et recherche.
   renderHelpTopic : contenu en carte + colonne (sommaire, CTA), nav
   prev/next, liens internes #h-<section> interceptes.
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
          <p>Sur la page <strong>Accueil</strong> ou <strong>Outils → Onboarding</strong>, clique sur <em>Importer ma config Claude</em>. Le scanner lit <code class="mono">~/.claude/settings.json</code> et <code class="mono">~/.claude/projects/</code>, te liste les MCPs et workspaces trouvés, et tu coches ceux que tu veux importer. Les éléments déjà connus sont grisés, tout comme les projets dont le dossier n'existe plus (badge <em>dossier introuvable</em>). Un projet marqué <em>sessions expirées</em> est bien là : Claude Code efface les anciennes conversations au bout de 30 jours (réglage <code class="mono">cleanupPeriodDays</code>), mais le dossier existe toujours et s'importe normalement.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">2</div>
        <div>
          <h4>Enregistrer un dossier existant</h4>
          <p>Pour pointer Nebula vers un projet déjà sur disque (sans le déplacer), utilise <em>Enregistrer un dossier</em>. Tu donnes l'ID, le label et le chemin absolu : aucun fichier n'est touché, juste un enregistrement dans <code class="mono">data/workspaces.json</code>. Le bouton <em>Parcourir…</em> ouvre le sélecteur de dossier de ton système pour éviter de taper le chemin.</p>
          <p>Tous tes projets sont rangés dans un même dossier (ex. <code class="mono">C:\\dev</code>) ? Bascule sur <em>Plusieurs projets d'un dossier</em> : Nebula liste les sous-dossiers qui ressemblent à des projets (CLAUDE.md, .claude, .git, package.json, pyproject.toml…), tu décoches ceux qui ne t'intéressent pas, tu ajustes les IDs si besoin, puis <em>Adopter la sélection</em>. Les projets déjà adoptés sont grisés ; un échec sur un projet n'empêche pas les autres. Aussi accessible depuis la palette (<kbd>Ctrl</kbd>+<kbd>K</kbd>) : <em>Adopter plusieurs projets d'un dossier</em>.</p>
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
      <p class="dim" style="font-size:12px">Le statut n'inclut volontairement pas de "connecté" : ce serait un test live à chaque rafraîchissement (lourd). Pour vérifier qu'un MCP marche vraiment, utilise le bouton <strong>Diagnostiquer</strong> à la demande (ci-dessous).</p>

      <h3>Bouton « Diagnostiquer »</h3>
      <p>Sur chaque card MCP, à côté de <em>Modifier</em>, le bouton <strong>Diagnostiquer</strong> ouvre une analyse à la demande. Il passe une série de vérifications et te donne, pour chacune, un <strong>POURQUOI</strong> (le symptôme) et un <strong>COMMENT réparer</strong> (le correctif) :</p>
      <ul class="help-list">
        <li><strong>Résolution des <code class="mono">\${VAR}</code></strong> — chaque variable référencée (command, args, env, headers, url, cwd) est-elle bien définie dans <code class="mono">.env.local</code> ? Sinon : <span class="badge badge-err">erreur</span> avec la liste des variables à définir.</li>
        <li><strong>Lint statique</strong> — un caractère parasite collé juste après un <code class="mono">\${VAR}</code> (le piège classique : un char en trop dans un token copié) ? <span class="badge badge-warn">attention</span>.</li>
        <li><strong>Commande exécutable</strong> (transport stdio) — l'exécutable (<code class="mono">npx</code>, <code class="mono">uvx</code>, <code class="mono">node</code>…) est-il dans le PATH ? Sinon : <span class="badge badge-err">erreur</span> « commande introuvable ».</li>
        <li><strong>Sonde HTTP</strong> (transport http/sse) — une requête légère est envoyée à l'URL avec les headers résolus. <strong>401/403</strong> = token/header d'auth probablement invalide (JWT tronqué ou char en trop) ; <strong>injoignable/timeout</strong> = serveur down ou URL/port faux ; <strong>2xx</strong> = OK. <em>Les valeurs de secrets ne sont jamais affichées ni renvoyées.</em></li>
        <li><strong>Synchronisation workspaces</strong> — le MCP est-il bien propagé dans le <code class="mono">.mcp.json</code> de chaque workspace ciblé ? Sinon : <span class="badge badge-warn">attention</span> « lance Sync ».</li>
      </ul>
      <p>En tête de la modale, une <strong>pastille de verdict global</strong> résume l'ensemble : vert (tout bon), orange (points à vérifier), rouge (problème bloquant). Le verdict prend le pire statut parmi les checks. Les vérifications purement locales (variables, char parasite) s'affichent instantanément ; la sonde réseau peut prendre quelques secondes.</p>

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
      <p>Sur chaque carte de la section <em>Installés</em>, l'interrupteur <em>Activé globalement</em> appelle <code class="mono">claude plugin enable/disable</code>. La poubelle désinstalle (avec confirmation).</p>

      <h3>Scope par workspace</h3>
      <p>Section <strong>Scope par workspace</strong> : sélectionne un plugin, vois la liste de tous les workspaces. Pour chacun, 3 états :</p>
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
'modules': `
      <h2>${I.zap}<span>Modules (overlays)</span></h2>
      <p>Un module se pose <strong>par-dessus</strong> un workspace existant, sans jamais écraser un fichier déjà présent (le <code class="mono">CLAUDE.md</code> reçoit juste un bloc délimité). On l'active depuis l'onglet <strong>Configuration</strong> du workspace, ou depuis la section <strong>Modules</strong> de la page Templates (« Activer sur un workspace… »). Sur un workspace où il est déjà actif, <strong>Ré-appliquer</strong> met le module à jour : les fichiers manquants sont copiés, les fichiers <em>gérés</em> par le module (ses hooks, et pour l'équipe d'agents ses quatre commandes et son bloc de règles du <code class="mono">CLAUDE.md</code>) sont remplacés par la version courante s'ils en diffèrent, l'ancienne version étant sauvegardée en <code class="mono">.bak</code>. Ton contenu (registres, mémoire de projet, manifeste, bloc « Auto-amélioration » du <code class="mono">CLAUDE.md</code> que tu as complété, texte hors des blocs) n'est jamais touché. Relance Claude Code ensuite pour charger les changements.</p>
      <p>Le bouton <strong>Retirer</strong> de la ligne d'un module montre d'abord un aperçu de ce qui part et de ce qui reste. Rien n'est supprimé : les fichiers du module partent dans une archive du projet (<code class="mono">.claude/.nebula-removed/</code>, avec un <code class="mono">removal.json</code> pour tout remettre en place) ; un <code class="mono">settings.json</code> resté identique à celui livré par le module part entier dans l'archive, sinon seuls les hooks du module y sont retirés (tes permissions restent), et dans <code class="mono">CLAUDE.md</code> seul son bloc part. L'équipe d'agents se retire avant l'auto-amélioration, et une case garde ta mémoire et tes registres en place.</p>

      <div class="help-grid help-grid-3">
        <div class="help-tile">
          <div class="help-tile-icon">${I.sparkle}</div>
          <h4>Auto-amélioration de Claude</h4>
          <p>Mémoire structurée dans <code class="mono">.claude/memory/</code>, registres d'idées et d'améliorations, agents, slash commands et hooks pré-commit. Tu choisis le mode (solo, équipe…) et la profondeur (minimale ou complète).</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.activity}</div>
          <h4>Équipe d'agents</h4>
          <p>Requiert le module précédent. Génère 7 agents (orchestrateur, chercheur, architecte, exécutant, relecteur, évaluateur, critique) avec un modèle et un effort par rôle, et un routage des demandes. L'équipe s'améliore au fil des conversations ; <code class="mono">/eval</code> et <code class="mono">/improve</code> restent là pour mesurer à la main.</p>
        </div>
      </div>

      <h3>L'équipe au quotidien</h3>
      <ul class="help-list">
        <li><code class="mono">/team &lt;objectif&gt;</code> : Claude joue l'orchestrateur, découpe le travail et le délègue aux agents.</li>
        <li><code class="mono">/eval</code> : mesure l'équipe contre le jeu d'évals figé de <code class="mono">.claude/evals/</code>.</li>
        <li><code class="mono">/improve</code> : une itération d'amélioration en deux phases ; la seconde se lance dans une <strong>nouvelle session</strong> Claude Code.</li>
        <li><code class="mono">/eval-add</code> : transforme un échec observé en nouveau cas d'éval.</li>
        <li>Sur la <strong>ligne du module « Équipe d'agents »</strong> (onglet Configuration) : le <strong>routage</strong>, la <strong>relecture</strong>, puis le dépliable <strong>Régler</strong> pour le <strong>modèle</strong> (<code class="mono">inherit</code> = celui de la session) et l'<strong>effort</strong> de chaque agent. Quand un corps d'agent a changé, un badge « N agent(s) à régénérer » apparaît avec un bouton <strong>Régénérer</strong> ; relance ensuite Claude Code, un agent régénéré n'est relu qu'au démarrage d'une session.</li>
        <li><strong>Amélioration au fil des conversations</strong> : quand un agent bute, Claude le note dans <code class="mono">.claude/improvements.md</code> et te propose le correctif du corps de l'agent. Une fois validé, clique sur Régénérer puis relance la session. Pas de boucle automatique, donc pas de coût caché ; <code class="mono">/eval</code> reste possible pour vérifier.</li>
      </ul>

      <h3>Abonnement et consommation</h3>
      <p>Nebula détecte ton abonnement Claude (Pro, Max ou API) d'après la configuration locale de Claude Code, sans lire tes jetons. Tu peux le corriger dans <strong>Outils</strong> (carte « Mon abonnement Claude ») si la détection se trompe. À l'activation de l'équipe et dans la carte modèle et effort, des avertissements signalent les réglages gourmands pour ton abonnement (opus partout, effort élevé).</p>

      <h3>Routage et coût</h3>
      <p>Le routage est livré en mode <strong>assisté</strong> (suggestions) et le code livré est relu par le relecteur (modèle opus) <strong>dès 3 fichiers</strong>, pour ménager le quota. Sur la ligne du module (onglet Configuration), passe le routage en <strong>auto</strong> (le plus complet, mais le plus gourmand en tokens) ou <strong>manuel</strong>, et la relecture en <strong>toujours</strong> ou <strong>jamais</strong>.</p>

      <div class="callout callout-warn">
        <strong>Évals verrouillées :</strong> un hook refuse toute écriture sous <code class="mono">.claude/evals/</code>, pour que la boucle ne puisse pas tricher sur sa propre mesure. Pour les modifier toi-même, pose <code class="mono">"evals_unlocked": true</code> dans <code class="mono">.claude/settings.local.json</code>. Les corps des agents s'éditent dans <code class="mono">.claude/team/agents/</code>, jamais dans les agents générés.
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
        <li><strong>À chaque chargement de la page</strong> : un <code class="mono">git fetch</code> frais est lancé. Seul un anti-rebond de <strong>2 min</strong> évite de relancer pour des F5 en rafale.</li>
        <li><strong>Retour sur l'onglet</strong> : nouvelle vérification si la dernière date de plus de 10 min.</li>
        <li><strong>Re-check périodique</strong> : toutes les 30 min en arrière-plan tant que l'onglet reste ouvert.</li>
        <li><strong>Échec de vérification</strong> (réseau, dépôt privé sans identifiants) : aucune alerte intrusive, la cause est affichée dans <em>Outils &gt; Mises à jour</em> (« Impossible de vérifier : ... »). La vérification automatique n'ouvre jamais de fenêtre de connexion Git.</li>
        <li>Si des commits sont en attente : <strong>badge gradient pulsant "X MAJ"</strong> apparaît dans le topbar à droite (visible sur toutes les pages), plus un badge descriptif dans la sidebar footer.</li>
      </ul>

      <h3>La section Outils &gt; Mises à jour</h3>
      <p>Version installée, état (« À jour », « N mises à jour disponibles », « Impossible de vérifier »), date de la dernière vérification, boutons <em>Mettre à jour</em> et <em>Vérifier maintenant</em>. Les changements à venir sont listés lisiblement : message sans le préfixe technique, badge Nouveauté / Correctif / Amélioration / Doc, date relative et lien <em>voir le détail</em> vers le commit. Liens <em>Voir le projet</em>, <em>Lire le README</em> et <em>Signaler un problème</em> (masqués si le dépôt n'est pas une URL web). Réinitialisation, sauvegardes (stash) et état git sont dans <em>Options avancées</em>.</p>

      <h3>Appliquer une mise à jour</h3>
      <p>Clic sur le badge (ou <em>Voir le détail</em>) → modale avec le même en-tête et la même liste lisible.</p>
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

      <h3>Le diagnostic MCP signale "Commande introuvable"</h3>
      <p>Le bouton <strong>Diagnostiquer</strong> d'une card MCP (transport stdio) indique que l'exécutable n'est pas dans le PATH. Vérifie que <code class="mono">node</code> / <code class="mono">python</code> / <code class="mono">uvx</code> sont accessibles depuis un terminal système. Sur Windows, <code class="mono">npx</code> s'appelle parfois <code class="mono">npx.cmd</code>.</p>

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
// Le champ `keywords` (lot F item 2) alimente la recherche dans la palette
// Ctrl+K : termes que l'utilisateur taperait sans connaître le titre exact du
// topic (« chiffrement », « sanity », « stash »…). Pas affiché dans l'UI.
const HELP_TOPICS = [
  { id: 'premiers-pas',   emoji: '🚀', title: 'Premiers pas',         summary: 'Découvre Nebula et importe ta config Claude existante.',          sections: ['overview', 'onboarding'], keywords: 'démarrer import onboarding première fois config claude scan wizard récupérer adopter dossier parent plusieurs projets parcourir sessions expirées introuvable' },
  { id: 'workspaces',     emoji: '🗂️', title: 'Workspaces',            summary: 'Créer, importer, lancer et gérer tes projets Claude Code.',       sections: ['workspaces', 'scope'], keywords: 'projet créer importer dossier lancer reprendre supprimer purge scope lier' },
  { id: 'mcps',           emoji: '🔌', title: 'MCPs',                  summary: 'Configurer les serveurs Model Context Protocol et leurs recettes.', sections: ['mcps', 'recipes'], keywords: 'model context protocol serveur transport stdio http sse diagnostiquer recette registry sync statut' },
  { id: 'skills-plugins', emoji: '✨', title: 'Skills & Plugins',      summary: 'Bibliothèque de compétences et extensions Claude Code.',          sections: ['skills', 'plugins'], keywords: 'skill plugin bibliothèque magasin distribuer marketplace installer github désync scope' },
  { id: 'templates',      emoji: '📋', title: 'Templates',             summary: 'Modèles réutilisables pour démarrer un workspace rapidement.',    sections: ['templates'], keywords: 'modèle starter placeholder qualité aperçu standard python node docker' },
  { id: 'modules',        emoji: '🧠', title: 'Modules',               summary: 'Auto-amélioration de Claude et équipe de 7 agents.',             sections: ['modules'], keywords: 'module overlay équipe agents team eval improve amélioration mémoire routage orchestrateur reviewer self-improving abonnement pro max quota budget' },
  { id: 'secrets',        emoji: '🔐', title: 'Secrets & sécurité',    summary: 'Stockage centralisé de tes tokens et clés d\'API, chiffrement.',  sections: ['env'], keywords: 'secret token clé api mot de passe env.local chiffrement chiffrer variable environnement dpapi' },
  { id: 'outils',         emoji: '🛠️', title: 'Outils & maintenance',  summary: 'Hooks, sauvegardes, mises à jour automatiques.',                  sections: ['tools', 'update'], keywords: 'hook sauvegarde backup mise à jour update git pull stash restore apparence thème conflits orphelins' },
  { id: 'reference',      emoji: '⌨️', title: 'Référence & dépannage', summary: 'Raccourcis clavier et solutions aux problèmes courants.',         sections: ['shortcuts', 'troubleshoot'], keywords: 'raccourci clavier shortcut dépannage troubleshoot sanity check serveur hors ligne erreur problème' },
];

// helpPaletteEntries (lot F item 2) : renvoie les topics d'aide matchant une
// requête, formatés pour la palette Ctrl+K (kind « Aide », label préfixé
// « Aide › <titre> », navigation vers #/aide/<topic>). Recherche locale,
// insensible à la casse et aux accents, sur titre + summary + keywords. Sans
// requête : renvoie [] (l'aide n'encombre pas la liste par défaut de la palette).
function _helpNormalize(s) {
  return String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}
function helpPaletteEntries(query) {
  const q = _helpNormalize(query).trim();
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  return HELP_TOPICS
    .filter(t => {
      const hay = _helpNormalize(`${t.title} ${t.summary} ${t.keywords || ''}`);
      return terms.every(term => hay.includes(term));
    })
    .map(t => ({ kind: 'Aide', label: `Aide › ${t.title}`, route: `#/aide/${t.id}` }));
}
window.helpPaletteEntries = helpPaletteEntries;

// HELP_TOPIC_CTAS (lot F item 3) : pour chaque topic, le ou les boutons
// « → Ouvrir la feature » affichés en fin de page. Les topics purement
// informatifs (reference = raccourcis + dépannage) n'ont pas de CTA.
const HELP_TOPIC_CTAS = {
  'premiers-pas':   [{ label: 'Ouvrir l\'accueil', route: '#/' }],
  'workspaces':     [{ label: 'Ouvrir l\'accueil', route: '#/' }],
  'mcps':           [{ label: 'Ouvrir les MCPs', route: '#/mcps' }],
  'skills-plugins': [{ label: 'Ouvrir les Skills', route: '#/skills' }, { label: 'Ouvrir les Plugins', route: '#/plugins' }],
  'templates':      [{ label: 'Ouvrir les Templates', route: '#/templates' }],
  'modules':        [{ label: 'Ouvrir les Modules (Templates)', route: '#/templates' }],
  'secrets':        [{ label: 'Ouvrir les Outils', route: '#/tools' }],
  'outils':         [{ label: 'Ouvrir les Outils', route: '#/tools' }],
};

/* ================================================================
   PAGE AIDE (hub + topics)
   ================================================================ */
async function renderHelp() {
  setBreadcrumbs([{ label: 'Aide' }]);
  const tourBtn = btn('Visite guidée', 'btn-primary', I.play);
  tourBtn.title = 'Lance un tour interactif en 13 étapes (~3 min)';
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

// Titres des sections d'un topic (texte du <h2>), pour les cartes du hub.
function _helpSectionTitles(topic, sections) {
  return topic.sections.map(id => {
    const m = /<h2>[\s\S]*?<span>([\s\S]*?)<\/span><\/h2>/.exec(sections[id] || '');
    return m ? m[1].replace(/<[^>]+>/g, '').trim() : id;
  });
}

function renderHelpHub() {
  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header rise', `
    <div class="page-header-text">
      <h1 class="page-title">Aide & guide d'utilisation</h1>
      <p class="page-subtitle">${HELP_TOPICS.length} sujets courts et autonomes. Choisis-en un, ou cherche un mot-clé.</p>
    </div>
  `));

  // Promo visite guidée si jamais lancée
  let tourCompleted = false;
  try { tourCompleted = localStorage.getItem('nebula-tour-completed') === '1'; } catch {}
  if (!tourCompleted) {
    const promo = el('div', 'card help-promo rise');
    promo.style.setProperty('--i', 1);
    promo['innerHTML'] = `
      <span class="help-promo-ic" aria-hidden="true">🎯</span>
      <div class="help-promo-t">
        <b>Première fois ici ?</b>
        <p>Lance la <strong>visite guidée interactive</strong> (13 étapes, ~3 min) : elle te montre les fonctions essentielles avec spotlight sur l'UI réelle.</p>
      </div>
    `;
    const launchBtn = btn('Démarrer la visite', 'btn-primary', I.play);
    launchBtn.addEventListener('click', () => startTour('main'));
    promo.appendChild(launchBtn);
    page.appendChild(promo);
  }

  // Recherche locale (meme logique que la palette Ctrl+K : titre, résumé, mots-clés).
  const toolbar = el('div', 'pg-filters rise');
  toolbar.style.setProperty('--i', 2);
  toolbar['innerHTML'] = `<span class="search-field">${I.search}<input class="input" type="search" placeholder="Chiffrement, stash, recette…" aria-label="Chercher un sujet d'aide"></span><span class="sp"></span><span class="pg-count tab-num" aria-live="polite"></span>`;
  const searchInput = toolbar.querySelector('input');
  const countEl = toolbar.querySelector('.pg-count');
  page.appendChild(toolbar);

  // Grille de cartes
  const sections = _helpSections();
  const grid = el('div', 'xgrid help-hub-grid rise');
  grid.style.setProperty('--i', 3);
  const cards = HELP_TOPICS.map(t => {
    const card = el('a', 'xcard help-hub-card');
    card.href = `#/aide/${t.id}`;
    const titles = _helpSectionTitles(t, sections);
    card['innerHTML'] = `
      <div class="top">
        <span class="xi help-hub-emoji" aria-hidden="true">${t.emoji}</span>
        <div class="xt">
          <h3 class="help-hub-title">${escapeHtml(t.title)}</h3>
          <div class="help-hub-summary">${escapeHtml(t.summary)}</div>
        </div>
      </div>
      <ul class="help-hub-secs">${titles.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
      <span class="help-hub-go">Lire ${I.right}</span>
    `;
    grid.appendChild(card);
    return [t, card];
  });
  const emptyEl = el('div', 'empty');
  emptyEl.hidden = true;
  emptyEl['innerHTML'] = '<div class="empty-title">Aucun sujet ne correspond</div><p class="muted">Essaie un autre mot-clé, ou la palette <kbd>Ctrl</kbd>+<kbd>K</kbd>.</p> <button class="btn btn-sm" type="button" data-reset-filters>Tout afficher</button>';
  emptyEl.querySelector('[data-reset-filters]').addEventListener('click', () => { searchInput.value = ''; apply(); searchInput.focus(); });
  grid.appendChild(emptyEl);
  page.appendChild(grid);

  const apply = () => {
    const q = _helpNormalize(searchInput.value).trim();
    const terms = q.split(/\s+/).filter(Boolean);
    let n = 0;
    for (const [t, card] of cards) {
      const hay = _helpNormalize(`${t.title} ${t.summary} ${t.keywords || ''}`);
      card.hidden = !terms.every(term => hay.includes(term));
      if (!card.hidden) n++;
    }
    emptyEl.hidden = n > 0;
    countEl.textContent = `${n} / ${HELP_TOPICS.length}`;
  };
  searchInput.addEventListener('input', debounce(apply, 80));
  apply();

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

  // En-tête : lien retour + titre
  const header = el('div', 'page-header rise');
  header['innerHTML'] = `
    <div class="page-header-text">
      <div class="page-eyebrow"><a href="#/aide" class="help-back">${I.right}<span>Toutes les aides</span></a></div>
      <h1 class="page-title"><span class="help-title-ic" aria-hidden="true">${topic.emoji}</span>${escapeHtml(topic.title)}</h1>
      <p class="page-subtitle">${escapeHtml(topic.summary)}</p>
    </div>
  `;
  page.appendChild(header);

  const layout = el('div', 'help-layout rise');
  layout.style.setProperty('--i', 1);

  // Contenu : concatène les sections de ce topic. Chaque section porte un id
  // `h-<section>` : cible des liens internes (`#h-recipes`) et du sommaire.
  const sections = _helpSections();
  const main = el('div', 'help-main');
  const content = el('div', 'card help-content help-content-single');
  let html = '';
  for (const secId of topic.sections) {
    html += `<section id="h-${secId}">${sections[secId] || ''}</section>`;
  }
  content['innerHTML'] = html;
  main.appendChild(content);

  // Navigation entre topics (précédent / suivant)
  const idx = HELP_TOPICS.findIndex(t => t.id === topic.id);
  const prev = idx > 0 ? HELP_TOPICS[idx - 1] : null;
  const next = idx < HELP_TOPICS.length - 1 ? HELP_TOPICS[idx + 1] : null;
  const nav = el('div', 'help-topic-nav');
  nav['innerHTML'] = `
    ${prev ? `<a href="#/aide/${prev.id}" class="help-nav-link"><span class="dim">← Précédent</span><strong>${prev.emoji} ${escapeHtml(prev.title)}</strong></a>` : '<span></span>'}
    ${next ? `<a href="#/aide/${next.id}" class="help-nav-link help-nav-next"><span class="dim">Suivant →</span><strong>${next.emoji} ${escapeHtml(next.title)}</strong></a>` : '<span></span>'}
  `;
  main.appendChild(nav);
  layout.appendChild(main);

  // Colonne : sommaire (h2 + h3 du topic) puis CTA « Ouvrir la feature ».
  const rail = el('aside', 'help-rail');
  rail.setAttribute('aria-label', 'Sur cette page');
  const heads = Array.from(content.querySelectorAll('h2, h3'));
  heads.forEach((h, i) => { if (!h.id) h.id = `h-${topic.id}-${i}`; });
  const toc = el('div', 'card help-toc-card');
  toc['innerHTML'] = `<div class="help-rail-h">Sur cette page</div><ul class="help-toc-list">${heads.map(h => `<li class="${h.tagName === 'H2' ? 'l2' : 'l3'}"><button type="button" data-target="${escapeHtml(h.id)}">${escapeHtml(h.textContent.trim())}</button></li>`).join('')}</ul>`;
  toc.addEventListener('click', (e) => {
    const b = e.target.closest('[data-target]');
    if (!b) return;
    const target = document.getElementById(b.dataset.target);
    if (target) target.scrollIntoView({ behavior: motionOK() ? 'smooth' : 'auto', block: 'start' });
  });
  rail.appendChild(toc);

  // CTA « → Ouvrir la feature » (lot F item 3) : passerelle directe du texte
  // vers l'action concernée. Réutilise btn() + I.right, tokenisé via .help-cta.
  const ctas = HELP_TOPIC_CTAS[topic.id];
  if (ctas && ctas.length) {
    const ctaBar = el('div', 'card help-cta');
    ctaBar['innerHTML'] = '<div class="help-rail-h">Passer à l\'action</div>';
    for (const cta of ctas) {
      const b = btn(cta.label, 'btn-primary', I.right);
      b.addEventListener('click', () => { location.hash = cta.route; });
      ctaBar.appendChild(b);
    }
    rail.appendChild(ctaBar);
  }
  layout.appendChild(rail);
  page.appendChild(layout);

  // Liens internes `#h-<section>` : le routeur par hash les prendrait pour une
  // route. On défile vers la section si elle est dans ce topic, sinon on ouvre
  // le topic qui la contient.
  content.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#h-"]');
    if (!a) return;
    e.preventDefault();
    const secId = a.getAttribute('href').slice(3);
    const here = document.getElementById(`h-${secId}`);
    if (here) { here.scrollIntoView({ behavior: motionOK() ? 'smooth' : 'auto', block: 'start' }); return; }
    const owner = HELP_TOPICS.find(t => t.sections.includes(secId));
    if (owner) location.hash = `#/aide/${owner.id}`;
  });

  c.appendChild(page);
  window.scrollTo({ top: 0, behavior: 'instant' });
}
