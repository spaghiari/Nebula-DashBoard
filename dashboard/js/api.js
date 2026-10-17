/* ================================================================
   Nebula - API client
   ----------------------------------------------------------------
   Wrapper fetch centralise pour toutes les routes /api/* du serveur.
   Charge AVANT app.js dans index.html (apres state.js si presence
   de dependance future).

   Securite : header X-Nebula-XHR custom sur chaque requete, posable
   uniquement par fetch/XHR same-origin. Bloque les CSRF basiques
   (un <form> ou <img> ne peut pas le poser).

   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

const API = {
  async _req(method, url, body) {
    const opts = { method, headers: { 'X-Nebula-XHR': '1' } };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let r;
    try { r = await fetch(url, opts); }
    catch (e) { throw new Error('Serveur injoignable'); }
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch {}
      throw new Error(msg);
    }
    const ct = r.headers.get('content-type') || '';
    return ct.includes('json') ? r.json() : r.text();
  },
  get(url) { return this._req('GET', url); },
  post(url, body = {}) { return this._req('POST', url, body); },
  // POST qui ne throw PAS sur un statut non-ok : rend {status, ok, data} pour
  // les routes dont la réponse d'erreur porte des données utiles (409 du
  // retrait d'un module : `dependents`, `active_session`, aperçu frais).
  // Serveur injoignable -> throw comme _req.
  async postStatus(url, body = {}) {
    let r;
    try {
      r = await fetch(url, {
        method: 'POST',
        headers: { 'X-Nebula-XHR': '1', 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) { throw new Error('Serveur injoignable'); }
    let data = {};
    try { data = await r.json(); } catch { data = { error: `HTTP ${r.status}` }; }
    if (!data || typeof data !== 'object') data = {};
    if (!r.ok && !data.error) data.error = `HTTP ${r.status}`;
    return { status: r.status, ok: r.ok, data };
  },
  del(url) { return this._req('DELETE', url); },

  // Téléchargement d'un fichier servi par une route protégée (header
  // X-Nebula-XHR exigé) : fetch -> Blob -> <a download>. Un <a href> ou
  // window.location ne poserait pas le header (403). Nom de fichier lu dans
  // Content-Disposition, sinon `fallbackName`. Erreur HTTP -> throw avec le
  // message `error` du serveur. Toujours appelé sur un clic explicite.
  async download(method, url, fallbackName, body) {
    const opts = { method, headers: { 'X-Nebula-XHR': '1' } };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let r;
    try { r = await fetch(url, opts); }
    catch (e) { throw new Error('Serveur injoignable'); }
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch { /* corps non-JSON */ }
      throw new Error(msg);
    }
    const blob = await r.blob();
    let filename = fallbackName || 'download';
    const m = (r.headers.get('content-disposition') || '').match(/filename="?([^"]+)"?/);
    if (m) filename = m[1];
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Libère l'URL objet après un court délai (laisse le temps au download).
    setTimeout(() => URL.revokeObjectURL(href), 2000);
    return filename;
  },
};

// Helper : GET avec fallback silencieux en cas d'erreur (utile pour
// les pollers de stats / sanity ou un 5xx ne doit pas casser la page).
const safe = (url, fallback) => API.get(url).catch(() => fallback);
