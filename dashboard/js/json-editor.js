/* ================================================================
   Nebula - Editeur JSON (composant reutilisable)
   ----------------------------------------------------------------
   createJsonEditor({ value, onChange, onSave, onValidChange, rows,
                      ariaLabel, id, allowEmpty, fill, blocking })
     -> { el, getValue, setValue, validate, isValid, focus, destroy, ta }

   Principe : une <textarea> TRANSPARENTE (source de verite, focusable,
   lue par les lecteurs d'ecran) posee au-dessus d'un <pre> colore. Meme
   police, meme interligne, meme padding des deux cotes : le curseur et la
   selection natifs tombent exactement sur le texte colore.

   Performance (JSON de plusieurs milliers de lignes) : seule la fenetre
   visible (+ marge) est coloree et numerotee. Le <pre> et la goutiere sont
   decales par transform selon le scroll. Un JSON.parse par frappe (anti-
   rebond au-dela de ~200 Ko). Aucun rendu proportionnel au nombre de lignes.

   Clavier : Tab / Maj+Tab (indente / desindente la selection), fermeture
   automatique des paires { [ ", Entree = indentation conservee (+1 niveau
   apres { ou [), Backspace sur paire vide, Ctrl+S (onSave), Ctrl+M (Tab
   quitte le champ au lieu d'indenter). Echap : dans une modale, le piege
   (phase de capture) le traite d'abord : fermeture, avec confirmation si
   modifie. Hors modale, Echap arme « Tab quitte le champ » pendant 1,5 s.

   PIEGE DE FOCUS DES MODALES : createFocusTrap (utils.js) intercepte Tab en
   phase de capture sur document, AVANT la textarea. La textarea porte donc
   data-no-trap tant que Tab sert a indenter ; l'attribut est retire quand
   l'utilisateur choisit de laisser Tab quitter le champ.

   Accessibilite : textarea aria-label + aria-invalid + aria-describedby ;
   message visuel immediat, annonce lecteur d'ecran (role="status") calmee
   par un anti-rebond ; focus visible ; mode contraste forcé gere en CSS.

   Styles : css/editor-matrix.css (variables du design system uniquement).
   Charge APRES utils.js (escapeHtml). Aucune autre dependance.
   ================================================================ */
'use strict';

const JSE_LINE_H = 20;      // px, doit rester egal a --jse-lh (CSS)
const JSE_PAD_Y = 10;       // px, padding vertical de la textarea et du <pre>
const JSE_PAD_X = 12;       // px, padding horizontal
const JSE_OVERSCAN = 40;    // lignes rendues au-dela de la zone visible
const JSE_MAX_COLOR_LINE = 4000;   // au-dela : ligne non coloree (JSON minifie)
const JSE_BIG_TEXT = 200000;       // au-dela : validation anti-rebondie
const JSE_NATIVE_EDIT_MAX = 6000;     // au-dela : setRangeText (execCommand trop lent)
let _jseCounter = 0;

const _jseEsc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// Jetons : chaine (cle si suivie de « : »), mots-cles, nombres, ponctuation.
// La chaine accepte l'absence de guillemet fermant pour colorer une saisie en cours.
const _JSE_TOKEN = /("(?:\\.|[^"\\])*"?)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}\[\],:])/g;

// Colorise UNE ligne (une chaine JSON ne peut pas contenir de saut de ligne :
// le decoupage ligne a ligne est donc exact pour du JSON valide).
function jseColorLine(line) {
  if (line.length > JSE_MAX_COLOR_LINE) return _jseEsc(line);
  let out = '';
  let last = 0;
  _JSE_TOKEN.lastIndex = 0;
  let m;
  while ((m = _JSE_TOKEN.exec(line)) !== null) {
    if (m[0] === '') { _JSE_TOKEN.lastIndex++; continue; }
    out += _jseEsc(line.slice(last, m.index));
    last = m.index + m[0].length;
    if (m[1] !== undefined) {
      out += m[2] !== undefined
        ? `<span class="jse-k">${_jseEsc(m[1])}</span><span class="jse-p">${_jseEsc(m[2])}</span>`
        : `<span class="jse-s">${_jseEsc(m[1])}</span>`;
    } else if (m[3] !== undefined) out += `<span class="jse-b">${m[3]}</span>`;
    else if (m[4] !== undefined) out += `<span class="jse-n">${m[4]}</span>`;
    else out += `<span class="jse-p">${m[5]}</span>`;
  }
  return out + _jseEsc(line.slice(last));
}

// Caracteres invisibles / bidi / espace insecable. Construit a l'EXECUTION (aucun
// caractere invisible litteral dans le source : cf. pitfall U+202A).
const _JSE_INVISIBLE = new RegExp('[' + ['200B-200F', '202A-202E', '2060', '2066-2069', 'FEFF', '00A0']
  .map(r => r.split('-').map(h => String.fromCharCode(parseInt(h, 16))).join('-')).join('') + ']');

// Numero de ligne (1-based) du caractere a l'index pos.
function _jseLineOf(t, pos) {
  let n = 1;
  for (let i = t.indexOf('\n'); i !== -1 && i < pos; i = t.indexOf('\n', i + 1)) n++;
  return n;
}

// Localise l'erreur par un petit analyseur descendant propre a l'editeur.
// On ne depend PAS du texte des messages de JSON.parse : ils different selon
// le navigateur/la version (position absente, formulation differente) et ne
// permettent pas de distinguer « virgule manquante » de « jeton inattendu ».
// Appele uniquement quand JSON.parse a deja echoue. Retourne
// { kind, pos, anchor } ou null (analyseur d'accord avec JSON.parse : cas
// theoriquement impossible, on retombe sur un message generique).
//   pos    : index du jeton fautif ; anchor : index sur lequel caler la ligne.
function _jseLocate(t) {
  const n = t.length;
  let i = 0;
  const ws = () => { while (i < n && (t[i] === ' ' || t[i] === '\n' || t[i] === '\r' || t[i] === '\t')) i++; };
  const lastNonWs = (from) => { let k = from - 1; while (k > 0 && /\s/.test(t[k])) k--; return Math.max(k, 0); };
  const fail = (kind, pos, anchor) => { const e = new Error(kind); e.jse = { kind, pos, anchor: anchor === undefined ? pos : anchor }; throw e; };
  const NUM = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;

  const str = () => {
    const start = i;
    i++;
    while (i < n) {
      const c = t[i];
      if (c === '"') { i++; return; }
      if (c === '\\') {
        const nx = t[i + 1];
        if (nx === undefined) fail('unterminated', start);
        if (nx === 'u') { if (!/^[0-9a-fA-F]{4}$/.test(t.slice(i + 2, i + 6))) fail('escape', i); i += 6; continue; }
        if (!'"\\/bfnrt'.includes(nx)) fail('escape', i);
        i += 2; continue;
      }
      if (c < ' ') fail('control', i, start);
      i++;
    }
    fail('unterminated', start);
  };

  const value = () => {
    ws();
    if (i >= n) fail('end', n, lastNonWs(n));
    const c = t[i];
    if (c === '{') return obj();
    if (c === '[') return arr();
    if (c === '"') return str();
    if (c === '-' || (c >= '0' && c <= '9')) {
      NUM.lastIndex = i;
      const m = NUM.exec(t);
      if (!m) fail('unexpected', i);
      i += m[0].length;
      return;
    }
    for (const kw of ['true', 'false', 'null']) {
      if (t.startsWith(kw, i) && !/[\w$]/.test(t[i + kw.length] || '')) { i += kw.length; return; }
    }
    fail('unexpected', i);
  };

  const obj = () => {
    i++; ws();
    if (t[i] === '}') { i++; return; }
    for (;;) {
      ws();
      if (i >= n) fail('end', n, lastNonWs(n));
      if (t[i] !== '"') {
        if (t[i] === '}' && /,\s*$/.test(t.slice(0, i))) fail('trailing', i, lastNonWs(i));
        fail('propname', i);
      }
      str(); ws();
      if (i >= n) fail('end', n, lastNonWs(n));
      if (t[i] !== ':') fail('colon', i, lastNonWs(i));
      i++;
      value(); ws();
      if (i >= n) fail('end', n, lastNonWs(n));
      if (t[i] === ',') { i++; continue; }
      if (t[i] === '}') { i++; return; }
      fail('comma', i, lastNonWs(i));
    }
  };

  const arr = () => {
    i++; ws();
    if (t[i] === ']') { i++; return; }
    for (;;) {
      ws();
      if (i >= n) fail('end', n, lastNonWs(n));
      if (t[i] === ']' && /,\s*$/.test(t.slice(0, i))) fail('trailing', i, lastNonWs(i));
      value(); ws();
      if (i >= n) fail('end', n, lastNonWs(n));
      if (t[i] === ',') { i++; continue; }
      if (t[i] === ']') { i++; return; }
      fail('comma', i, lastNonWs(i));
    }
  };

  try {
    value(); ws();
    if (i < n) fail('extra', i);
    return null;
  } catch (e) {
    return e && e.jse ? e.jse : null;
  }
}

// Diagnostic d'un texte JSON. Retourne { ok:true, value } ou
// { ok:false, line, col, msg } avec msg en francais. Pour une erreur de
// type « virgule attendue », la ligne signalee est la DERNIERE ligne non
// vide AVANT le jeton fautif (c'est la qu'il manque la virgule), pas celle
// du jeton suivant que le moteur designe.
function jsonErrInfo(text) {
  const t = String(text ?? '');
  if (!t.trim()) return { ok: false, line: 1, col: 1, msg: 'le champ est vide' };
  try { return { ok: true, value: JSON.parse(t) }; }
  catch (e) {
    const loc = _jseLocate(t);
    if (!loc) {
      return { ok: false, line: 1, col: 1, msg: 'JSON invalide (' + String((e && e.message) || e).slice(0, 80) + ')' };
    }
    const ch = t[loc.pos];
    const same = _jseLineOf(t, loc.anchor) === _jseLineOf(t, loc.pos);
    let msg;
    switch (loc.kind) {
      case 'end':
        msg = 'le JSON se termine trop tôt : il manque une accolade, un crochet ou une valeur'; break;
      case 'unterminated':
        msg = 'guillemet fermant manquant sur cette ligne'; break;
      case 'control':
        msg = 'saut de ligne ou caractère de contrôle dans une chaîne (écris \\n pour un retour à la ligne)'; break;
      case 'escape':
        msg = 'séquence d\'échappement invalide dans une chaîne (écris \\\\ pour une barre oblique inverse)'; break;
      case 'trailing':
        msg = 'virgule en trop à la fin de cette ligne (JSON n\'accepte pas de virgule avant « ' + ch + ' »)'; break;
      case 'comma':
        msg = same && ch ? 'virgule manquante avant « ' + (ch === '\n' ? '\\n' : ch) + ' »' : 'virgule manquante à la fin de cette ligne'; break;
      case 'colon':
        msg = 'deux-points « : » manquant après le nom de la propriété'; break;
      case 'extra':
        msg = 'contenu en trop après la fin du JSON'; break;
      default: {   // 'propname' | 'unexpected'
        if (ch && _JSE_INVISIBLE.test(ch)) {
          msg = 'caractère invisible (U+' + ch.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')
            + ') à cet endroit : supprime-le (souvent collé depuis l\'Explorateur ou un site web)';
        } else if (ch === '\'') {
          msg = 'les guillemets simples ne sont pas valides en JSON : utilise des guillemets doubles';
        } else if (ch === '/') {
          msg = 'les commentaires ne sont pas autorisés en JSON';
        } else if (loc.kind === 'propname') {
          msg = 'un nom de propriété doit être entre guillemets doubles';
        } else if (ch && /[A-Za-z_$]/.test(ch)) {
          const word = /^[A-Za-z_$][\w$]*/.exec(t.slice(loc.pos))[0].slice(0, 24);
          msg = 'valeur inconnue « ' + word + ' » (JSON n\'accepte que des chaînes, nombres, true, false, null, objets et tableaux)';
        } else {
          msg = 'caractère inattendu « ' + (ch === '\n' ? '\\n' : ch) + ' »';
        }
      }
    }
    const line = _jseLineOf(t, loc.anchor);
    const lineStart = t.lastIndexOf('\n', loc.anchor - 1) + 1;
    return { ok: false, line, col: loc.anchor - lineStart + 1, msg };
  }
}

// `blocking` (defaut true) : une erreur JSON est bloquante (etat « erreur »,
// a l'appelant de desactiver Enregistrer via onValidChange). `blocking:false`
// = mode AVERTISSEMENT (fichiers de templates/skills a placeholders {{...}},
// volontairement invalides) : meme diagnostic « Ligne N : ... », en couleur
// d'avertissement, avec la mention que l'enregistrement reste possible.
// onValidChange est appele a l'identique ; l'appelant ne bloque simplement pas.
function createJsonEditor({ value = '', onChange = null, onSave = null, onValidChange = null,
                            rows = 14, ariaLabel = 'Éditeur JSON', id = null, allowEmpty = false, fill = false,
                            blocking = true } = {}) {
  const uid = id || `jse-${++_jseCounter}`;
  const root = document.createElement('div');
  root.className = 'jse' + (fill ? ' jse-fill' : '') + (blocking ? '' : ' jse-nonblocking');
  root.style.setProperty('--jse-lh', JSE_LINE_H + 'px');
  root.style.setProperty('--jse-pad-y', JSE_PAD_Y + 'px');
  root.style.setProperty('--jse-pad-x', JSE_PAD_X + 'px');
  root['innerHTML'] = `
    <div class="jse-bar">
      <span class="jse-status" data-state="ok"><span class="jse-dot" aria-hidden="true"></span><span class="jse-status-text">JSON valide</span><span class="jse-count"></span></span>
      <button type="button" class="btn btn-sm btn-ghost jse-fmt" title="Réindente le JSON (2 espaces)">Mettre en forme</button>
    </div>
    <div class="jse-ed"${fill ? '' : ` style="height:${rows * JSE_LINE_H + 2 * JSE_PAD_Y}px"`}>
      <div class="jse-gut" aria-hidden="true"><div class="jse-gut-in"></div></div>
      <div class="jse-pane">
        <div class="jse-errline" aria-hidden="true"></div>
        <div class="jse-hl" aria-hidden="true"><pre class="jse-hl-in"></pre></div>
        <textarea class="jse-ta" id="${uid}-ta" data-no-trap spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" wrap="off"
                  aria-label="${escapeHtml(ariaLabel)}" aria-describedby="${uid}-msg ${uid}-hint" aria-invalid="false"></textarea>
      </div>
    </div>
    <div class="jse-msg" id="${uid}-msg" aria-hidden="true"></div>
    <div class="jse-sr" role="status" aria-live="polite"></div>
    <div class="jse-hint" id="${uid}-hint"></div>
  `;
  const q = (sel) => root.querySelector(sel);
  const ta = q('.jse-ta');
  const ed = q('.jse-ed');
  const gut = q('.jse-gut');
  const gutIn = q('.jse-gut-in');
  const hlIn = q('.jse-hl-in');
  const errLine = q('.jse-errline');
  const msgEl = q('.jse-msg');
  const srEl = q('.jse-sr');
  const hintEl = q('.jse-hint');
  const statusEl = q('.jse-status');
  const statusText = q('.jse-status-text');
  const countEl = q('.jse-count');
  const fmtBtn = q('.jse-fmt');

  let lines = [''];
  let curStart = 0;
  let curEnd = 0;
  let result = { ok: true };
  let lastState = null;           // 'valid' | 'invalid' | 'empty' (allowEmpty)
  let tabCapture = true;          // Tab indente (sinon : Tab quitte le champ)
  let escTimer = null;
  let valTimer = null;
  let srTimer = null;
  let lastSr = '';
  let destroyed = false;
  let digits = 0;

  const setHint = () => {
    hintEl['innerHTML'] = tabCapture
      ? '<kbd>Tab</kbd> indente · <kbd>Maj+Tab</kbd> désindente · <kbd>Ctrl+S</kbd> enregistre · <kbd>Ctrl+M</kbd> : Tab quitte le champ'
      : '<kbd>Tab</kbd> quitte le champ (mode clavier actif) · <kbd>Ctrl+M</kbd> : Tab indente à nouveau';
  };
  setHint();

  // Tab capture : data-no-trap present => le piege de modale laisse Tab a la textarea.
  const setTabCapture = (on, announce) => {
    tabCapture = on;
    if (on) ta.setAttribute('data-no-trap', ''); else ta.removeAttribute('data-no-trap');
    setHint();
    if (announce) speak(on ? 'La touche Tab indente le texte.' : 'La touche Tab déplace le focus hors du champ.');
  };

  const speak = (text) => {
    clearTimeout(srTimer);
    srTimer = setTimeout(() => {
      if (destroyed || text === lastSr) return;
      lastSr = text;
      srEl.textContent = text;
    }, 450);
  };

  // ---- Rendu fenetre ------------------------------------------------
  const viewLines = () => Math.ceil((ta.clientHeight || ed.clientHeight || rows * JSE_LINE_H) / JSE_LINE_H) + 1;

  const position = () => {
    const st = ta.scrollTop;
    const sl = ta.scrollLeft;
    hlIn.style.transform = `translate(${-sl}px, ${JSE_PAD_Y + curStart * JSE_LINE_H - st}px)`;
    gutIn.style.transform = `translateY(${JSE_PAD_Y + curStart * JSE_LINE_H - st}px)`;
    if (!result.ok && result.line) {
      const y = JSE_PAD_Y + (result.line - 1) * JSE_LINE_H - st;
      const visible = y > -JSE_LINE_H && y < ed.clientHeight;
      errLine.style.display = visible ? 'block' : 'none';
      errLine.style.transform = `translateY(${y}px)`;
    } else {
      errLine.style.display = 'none';
    }
  };

  const renderWindow = () => {
    const n = lines.length;
    const first = Math.floor(ta.scrollTop / JSE_LINE_H);
    curStart = Math.max(0, first - JSE_OVERSCAN);
    curEnd = Math.min(n, first + viewLines() + JSE_OVERSCAN);
    let html = '';
    let g = '';
    for (let i = curStart; i < curEnd; i++) {
      html += jseColorLine(lines[i]) + '\n';
      g += `<div${!result.ok && result.line === i + 1 ? ' class="bad"' : ''}>${i + 1}</div>`;
    }
    hlIn['innerHTML'] = html;
    gutIn['innerHTML'] = g;
    position();
  };

  const updateDigits = () => {
    const d = String(lines.length).length;
    if (d !== digits) {
      digits = d;
      root.style.setProperty('--jse-digits', String(Math.max(2, d)));
    }
  };

  const onScroll = () => {
    const first = Math.floor(ta.scrollTop / JSE_LINE_H);
    const last = first + viewLines();
    const n = lines.length;
    if ((curStart > 0 && first < curStart + 5) || (curEnd < n && last > curEnd - 5)) renderWindow();
    else position();
  };

  // ---- Validation -----------------------------------------------------
  const applyValidation = () => {
    valTimer = null;
    if (destroyed) return;
    const prevLine = result.ok ? 0 : result.line;
    result = (allowEmpty && !ta.value.trim()) ? { ok: true, empty: true } : jsonErrInfo(ta.value);
    const bad = !result.ok;
    const state = bad ? 'invalid' : (result.empty ? 'empty' : 'valid');
    // Mode non bloquant : aria-invalid reste a false (la saisie n'est pas
    // refusee), le diagnostic est porte par le message d'avertissement.
    ta.setAttribute('aria-invalid', bad && blocking ? 'true' : 'false');
    statusEl.dataset.state = bad ? (blocking ? 'err' : 'warn') : (result.empty ? 'empty' : 'ok');
    statusText.textContent = bad
      ? (blocking ? 'JSON invalide' : 'JSON invalide (enregistrement possible)')
      : (result.empty ? 'Champ vide' : 'JSON valide');
    countEl.textContent = ' · ' + lines.length + (lines.length > 1 ? ' lignes' : ' ligne');
    fmtBtn.disabled = bad || !!result.empty;
    const tail = blocking ? '' : ' -- normal si le fichier contient des placeholders {{...}}';
    msgEl.textContent = bad ? `Ligne ${result.line} : ${result.msg}${tail}` : '';
    msgEl.classList.toggle('show', bad);
    speak(bad
      ? `${blocking ? 'JSON invalide' : 'Avertissement, JSON invalide, enregistrement possible'}. Ligne ${result.line} : ${result.msg}`
      : (result.empty ? 'Champ vide' : 'JSON valide'));
    if ((bad ? result.line : 0) !== prevLine) renderWindow(); else position();
    if (lastState !== state) {
      lastState = state;
      // ok = vrai UNIQUEMENT pour un JSON valide et non vide (un champ vide
      // toléré via allowEmpty n'est pas « enregistrable »).
      if (onValidChange) onValidChange(state === 'valid', result);
    }
  };

  const scheduleValidation = () => {
    clearTimeout(valTimer);
    if (ta.value.length > JSE_BIG_TEXT) valTimer = setTimeout(applyValidation, 160);
    else applyValidation();
  };

  const onInput = (fromUser) => {
    lines = ta.value.split('\n');
    updateDigits();
    renderWindow();
    scheduleValidation();
    if (fromUser && onChange) onChange(ta.value);
  };

  // ---- Pile d'annulation maison ----------------------------------------
  // Les ecritures DIRECTES (gros fichier, cf. replaceRange) n'entrent pas dans
  // la pile native du navigateur. Elles sont empilees ici (instantanes texte
  // + selection + defilement). L'ecriture directe passe par ta.value = ...,
  // ce qui VIDE la pile native (Chromium) : elle ne contient ensuite que les
  // frappes posterieures, jamais d'operation decalee rejouee au mauvais
  // endroit. Ctrl+Z : tant que la pile native a de quoi annuler (frappe
  // normale), c'est elle qui sert ; une fois revenu a l'etat produit par
  // l'ecriture directe, l'instantane maison est restaure. Ctrl+Y /
  // Ctrl+Maj+Z : symetrique. Sans ecriture directe (cas courant), rien n'est
  // intercepte : annulation 100 % native. Limite : l'historique de frappe
  // ANTERIEUR a une ecriture directe est perdu (la pile native est videe).
  const JSE_UNDO_MAX = 30;
  let undoStack = [];
  let redoStack = [];
  const snap = () => ({ v: ta.value, s: ta.selectionStart, e: ta.selectionEnd, top: ta.scrollTop, left: ta.scrollLeft });
  const restoreSnap = (st) => {
    ta.value = st.v;
    ta.setSelectionRange(st.s, st.e);
    ta.scrollTop = st.top;
    ta.scrollLeft = st.left;
    onInput(true);
  };
  // Tente l'annulation / le retablissement natif ; true si le texte a change.
  const tryNative = (cmd) => {
    const v0 = ta.value;
    try { document.execCommand(cmd); } catch { /* commande non supportee */ }
    return ta.value !== v0;
  };
  const customUndo = () => {
    const top = undoStack[undoStack.length - 1];
    if (ta.value !== top.after.v && tryNative('undo')) return;
    undoStack.pop();
    // Si de la frappe non annulable s'est intercalee, le retablissement
    // ramene a l'etat courant (frappe comprise), pas a l'ancien « apres ».
    redoStack.push({ before: top.before, after: ta.value === top.after.v ? top.after : snap() });
    restoreSnap(top.before);
  };
  const customRedo = () => {
    const top = redoStack[redoStack.length - 1];
    if (ta.value !== top.before.v && tryNative('redo')) return;
    redoStack.pop();
    undoStack.push({ before: ta.value === top.before.v ? top.before : snap(), after: top.after });
    restoreSnap(top.after);
  };

  // ---- Edition clavier ----------------------------------------------
  // Remplace [a,b) par text en conservant la pile d'annulation native
  // (execCommand) ; repli sur une ecriture directe (pile maison) sinon.
  const replaceRange = (a, b, text, caretA = null, caretB = null) => {
    const before = snap();
    ta.setSelectionRange(a, b);
    let done = false;
    // execCommand conserve l'annulation native (Ctrl+Z) mais son cout explose
    // avec la taille (mesure : 72 Kio / 6300 lignes = plus de 40 s). Au-dela
    // du seuil on ecrit directement (instantane) et l'operation (Mettre en
    // forme / indenter tout un gros fichier) part dans la pile maison.
    if (text.length <= JSE_NATIVE_EDIT_MAX && (b - a) <= JSE_NATIVE_EDIT_MAX) {
      try {
        done = text === '' ? document.execCommand('delete') : document.execCommand('insertText', false, text);
      } catch { done = false; }
    }
    let direct = false;
    if (!done || (text !== '' && ta.value.slice(a, a + text.length) !== text)) {
      direct = true;
      ta.value = before.v.slice(0, a) + text + before.v.slice(b);
      ta.setSelectionRange(a + text.length, a + text.length);
      ta.scrollTop = before.top;
      ta.scrollLeft = before.left;
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (caretA !== null) ta.setSelectionRange(caretA, caretB === null ? caretA : caretB);
    if (direct) {
      undoStack.push({ before, after: snap() });
      if (undoStack.length > JSE_UNDO_MAX) undoStack.shift();
      redoStack = [];
    }
  };

  // Vrai si le curseur est a l'interieur d'une chaine (nombre impair de
  // guillemets non echappes sur la portion de ligne avant le curseur).
  const inString = (lineBefore) => {
    let inside = false;
    for (let i = 0; i < lineBefore.length; i++) {
      const c = lineBefore[i];
      if (c === '\\' && inside) { i++; continue; }
      if (c === '"') inside = !inside;
    }
    return inside;
  };

  const PAIRS = { '{': '}', '[': ']', '"': '"' };

  const onKeyDown = (e) => {
    if (e.defaultPrevented || e.isComposing || e.keyCode === 229) return;
    const key = e.key;
    const ctrlOnly = (e.ctrlKey || e.metaKey) && !e.altKey;   // AltGr = Ctrl+Alt sur Windows : pas un raccourci
    const v = ta.value;
    const s = ta.selectionStart;
    const en = ta.selectionEnd;

    if (ctrlOnly && (key === 's' || key === 'S')) { e.preventDefault(); if (onSave) onSave(); return; }
    if (ctrlOnly && (key === 'm' || key === 'M')) { e.preventDefault(); setTabCapture(!tabCapture, true); return; }
    // Annuler / retablir : intercepte seulement si la pile maison a servi
    // (sinon comportement natif inchange). e.key suit la disposition : Ctrl+Z
    // sur AZERTY donne bien 'z' ; AltGr (Ctrl+Alt) exclu par ctrlOnly.
    const isZ = key === 'z' || key === 'Z';
    if (ctrlOnly && isZ && !e.shiftKey && undoStack.length) { e.preventDefault(); customUndo(); return; }
    if (ctrlOnly && ((isZ && e.shiftKey) || key === 'y' || key === 'Y') && redoStack.length) { e.preventDefault(); customRedo(); return; }
    if (key === 'Escape') {
      // Ne bloque pas Echap (la modale gere la fermeture / la confirmation) :
      // arme seulement la sortie clavier pour 1,5 s.
      if (tabCapture) {
        setTabCapture(false, false);
        clearTimeout(escTimer);
        escTimer = setTimeout(() => { if (!destroyed) setTabCapture(true, false); }, 1500);
      }
      return;
    }
    if (e.ctrlKey || e.metaKey) { if (!(e.ctrlKey && e.altKey)) return; }

    if (key === 'Tab') {
      if (!tabCapture || e.altKey) return;       // le focus quitte le champ (piege de modale compris)
      e.preventDefault();
      const multi = v.slice(s, en).includes('\n');
      if (s === en && !e.shiftKey) { replaceRange(s, en, '  '); return; }
      if (!multi && !e.shiftKey) { replaceRange(s, en, '  '); return; }
      // Bloc : indente / desindente chaque ligne touchee par la selection.
      const a = v.lastIndexOf('\n', s - 1) + 1;
      const endAdj = (en > s && v[en - 1] === '\n') ? en - 1 : en;   // ne pas toucher la ligne suivante
      const blk = v.slice(a, endAdj);
      let out;
      if (e.shiftKey) out = blk.replace(/^ {1,2}/gm, '');
      else out = blk.replace(/^/gm, '  ');
      if (out === blk) return;
      const firstRemoved = e.shiftKey ? Math.min(2, (/^ */.exec(blk)[0]).length) : 2;
      const newS = e.shiftKey ? Math.max(a, s - firstRemoved) : s + 2;
      replaceRange(a, endAdj, out, newS, a + out.length + (en - endAdj));
      return;
    }

    if (key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const ls = v.lastIndexOf('\n', s - 1) + 1;
      const before = v.slice(ls, s);
      const ind = /^ */.exec(before)[0];
      const pv = v[s - 1];
      const nx = v[en];
      const opens = /[{\[]$/.test(before.trimEnd()) && !inString(before.replace(/[{\[]\s*$/, ''));
      if ((pv === '{' && nx === '}') || (pv === '[' && nx === ']')) {
        const ins = '\n' + ind + '  ' + '\n' + ind;
        replaceRange(s, en, ins, s + 1 + ind.length + 2);
      } else {
        replaceRange(s, en, '\n' + ind + (opens ? '  ' : ''));
      }
      return;
    }

    if (PAIRS[key]) {
      const lsx = v.lastIndexOf('\n', s - 1) + 1;
      const beforeLine = v.slice(lsx, s);
      if (key === '"') {
        if (s === en && v[s] === '"') { e.preventDefault(); ta.setSelectionRange(s + 1, s + 1); return; }
        if (s === en && beforeLine.endsWith('\\')) return;           // guillemet echappe : natif
        if (s === en && inString(beforeLine)) return;                // dans une chaine : guillemet simple natif
      } else if (s === en && inString(beforeLine)) return;
      e.preventDefault();
      const sel = v.slice(s, en);
      replaceRange(s, en, key + sel + PAIRS[key], s + 1, s + 1 + sel.length);
      return;
    }

    if ((key === '}' || key === ']') && s === en && v[s] === key) {
      e.preventDefault();
      ta.setSelectionRange(s + 1, s + 1);
      return;
    }

    if (key === 'Backspace' && s === en && s > 0 && PAIRS[v[s - 1]] && PAIRS[v[s - 1]] === v[s]) {
      e.preventDefault();
      replaceRange(s - 1, s + 1, '');
    }
  };

  const onBlur = () => {
    // Retour au mode « Tab indente » quand le champ perd le focus.
    clearTimeout(escTimer);
    if (!tabCapture) setTabCapture(true, false);
  };

  // ---- Mise en forme --------------------------------------------------
  const format = () => {
    const r = jsonErrInfo(ta.value);
    if (!r.ok) return;
    // JSON.stringify ne preserve pas les entiers > 2^53 : on refuse plutot
    // que de corrompre silencieusement une valeur.
    if (/(^|[^\w."])-?\d{16,}(?![\w."])/.test(ta.value)) {
      speak('Mise en forme refusée : un nombre dépasse la précision de JavaScript.');
      msgEl.textContent = 'Mise en forme refusée : un nombre entier dépasse la précision de JavaScript (elle l\'arrondirait).';
      msgEl.classList.add('show');
      return;
    }
    const pretty = JSON.stringify(r.value, null, 2);
    if (pretty === ta.value) return;
    ta.focus();
    replaceRange(0, ta.value.length, pretty, 0, 0);
    ta.scrollTop = 0;
  };

  // ---- Cablage --------------------------------------------------------
  // Une nouvelle saisie (hors annuler / retablir natifs) invalide le retablissement.
  const onTaInput = (e) => {
    if (e && e.inputType && !/^history/.test(e.inputType)) redoStack = [];
    onInput(true);
  };
  ta.addEventListener('input', onTaInput);
  ta.addEventListener('scroll', onScroll);
  ta.addEventListener('keydown', onKeyDown);
  ta.addEventListener('blur', onBlur);
  fmtBtn.addEventListener('click', format);
  let ro = null;
  if (typeof ResizeObserver === 'function') {
    ro = new ResizeObserver(() => { if (!destroyed) renderWindow(); });
    ro.observe(ed);
  }

  const setValue = (v, { silent = true } = {}) => {
    ta.value = String(v ?? '').replace(/^\uFEFF/, '');    // BOM tolere a la lecture
    undoStack = [];
    redoStack = [];
    ta.scrollTop = 0;
    ta.scrollLeft = 0;
    lines = ta.value.split('\n');
    updateDigits();
    clearTimeout(valTimer);
    applyValidation();
    renderWindow();
    if (!silent && onChange) onChange(ta.value);
  };

  setTabCapture(true, false);
  setValue(value);

  return {
    el: root,
    ta,
    getValue: () => ta.value,
    setValue,
    validate: () => { clearTimeout(valTimer); applyValidation(); return result; },
    isValid: () => result.ok,
    focus: () => { ta.focus(); },
    // Force un nouveau rendu (ex. apres affichage d'un onglet qui etait cache).
    refresh: () => { renderWindow(); },
    destroy: () => {
      destroyed = true;
      clearTimeout(valTimer); clearTimeout(srTimer); clearTimeout(escTimer);
      if (ro) ro.disconnect();
      ta.removeEventListener('input', onTaInput);
      ta.removeEventListener('scroll', onScroll);
      ta.removeEventListener('keydown', onKeyDown);
      ta.removeEventListener('blur', onBlur);
      fmtBtn.removeEventListener('click', format);
    },
  };
}

// Editeur de fichier des modales Templates / Skills (panneau .tpl-pane).
// `ta` = la <textarea> deja en place. Fichier .json -> remplace la textarea
// par createJsonEditor en mode NON BLOQUANT (les placeholders {{...}} peuvent
// rendre le JSON volontairement invalide : avertissement, jamais de blocage
// de l'enregistrement). Autres fichiers -> la textarea telle quelle.
// Dans les deux cas : onChange a chaque saisie, onSave sur Ctrl+S.
// Retourne { el, getValue, focus, destroy, isJson }.
function mountFileEditor(ta, path, { onChange = null, onSave = null } = {}) {
  if (!/\.json$/i.test(path || '')) {
    ta.addEventListener('input', () => { if (onChange) onChange(); });
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        if (onSave) onSave();
      }
    });
    return { el: ta, getValue: () => ta.value, focus: () => ta.focus(), destroy: () => {}, isJson: false };
  }
  const editor = createJsonEditor({
    value: ta.value, fill: true, blocking: false, ariaLabel: `Contenu de ${path}`,
    onChange: () => { if (onChange) onChange(); },
    onSave: () => { if (onSave) onSave(); },
  });
  ta.replaceWith(editor.el);
  return { el: editor.el, getValue: editor.getValue, focus: editor.focus, destroy: editor.destroy, isJson: true };
}

window.createJsonEditor = createJsonEditor;
window.mountFileEditor = mountFileEditor;
window.jsonErrInfo = jsonErrInfo;
