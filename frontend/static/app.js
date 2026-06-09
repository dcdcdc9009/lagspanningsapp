'use strict';
/* ================================================================
   LÅGSPÄNNINGSBEREDNING – SPA
   ================================================================ */

// ----------------------------------------------------------------
// STATE
// ----------------------------------------------------------------
const S = {
  admin: false,
  view:  'projekt',
  projekt: [],
  beredare: [],
  kategorier: [],
  leverantorer: [],
  mallar: [],
  installningar: {},
  valtProjektKonstr: null,
  user: null,          // { anvandarnamn, namn, roll, beredare }
  minBeredare: null,   // beredare-namn för auto-filter på egna jobb
};

// ----------------------------------------------------------------
// API
// ----------------------------------------------------------------
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch('/api' + path, opts);
  let data;
  try { data = await r.json(); } catch { data = {}; }
  if (!r.ok) throw new Error(data.fel || data.error || `HTTP ${r.status}`);
  return data;
}

// ----------------------------------------------------------------
// TOAST
// ----------------------------------------------------------------
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toastContainer').appendChild(el);
  el.addEventListener('click', () => el.remove());
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; setTimeout(() => el.remove(), 400); }, 3500);
}

// ----------------------------------------------------------------
// CONFIRM DIALOG
// ----------------------------------------------------------------
function confirm(title, msg, label = 'Ta bort') {
  return new Promise(resolve => {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMsg').textContent   = msg;
    document.getElementById('confirmOk').textContent    = label;
    const dlg = document.getElementById('confirmDialog');
    dlg.classList.remove('hidden');
    const ok  = () => { cleanup(); resolve(true); };
    const can = () => { cleanup(); resolve(false); };
    function cleanup() {
      dlg.classList.add('hidden');
      document.getElementById('confirmOk').removeEventListener('click', ok);
      document.getElementById('confirmCancel').removeEventListener('click', can);
    }
    document.getElementById('confirmOk').addEventListener('click', ok);
    document.getElementById('confirmCancel').addEventListener('click', can);
  });
}

// ----------------------------------------------------------------
// MODAL
// ----------------------------------------------------------------
const Modal = {
  noBackdropClose: false,
  open(title, bodyHTML, footerHTML = '', opts = {}) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML   = bodyHTML;
    document.getElementById('modalFooter').innerHTML = footerHTML;
    document.getElementById('modal').classList.remove('hidden');
    Modal.noBackdropClose = !!opts.noBackdropClose;
  },
  close() { document.getElementById('modal').classList.add('hidden'); Modal.noBackdropClose = false; },
};

// ----------------------------------------------------------------
// ROUTING
// ----------------------------------------------------------------
function navigate(view, params = {}) {
  S.view = view;
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.view === view);
  });
  render(view, params);
}

window.addEventListener('hashchange', () => {
  const [view, ...rest] = location.hash.replace('#', '').split('/');
  if (view) navigate(view, { id: rest[0] });
});

function render(view, params = {}) {
  const app = document.getElementById('app');
  app.innerHTML = '';
  app.dataset.view = view;
  document.body.dataset.view = view;
  switch (view) {
    case 'projekt':         renderProjekt(app); break;
    case 'projekt-detail':  renderProjektDetail(app, params.id); break;
    case 'artiklar':        renderArtiklar(app); break;
    case 'konstruktioner':  renderKonstruktioner(app); break;
    case 'admin':           renderAdmin(app); break;
    case 'anslutning':      renderAnslutning(app); break;
    case 'tjallmo':         renderTjallmo(app); break;
    case 'kabeltrummor':    renderKabeltrummor(app); break;
    case 'tidplan':         renderTidplan(app); break;
    case 'kontrollrum':     renderKontrollrum(app); break;
    case 'rapport':         renderRapport(app); break;
    case 'statistik':       renderStatistik(app); break;
    default:                renderProjekt(app);
  }
}

// ----------------------------------------------------------------
// HELPERS
// ----------------------------------------------------------------
function badge(status) {
  const map = {
    'Planerat': 'badge-planerat', 'Pågående': 'badge-pagaende', 'Klart': 'badge-klart',
    'Utkast': 'badge-utkast', 'Granskat': 'badge-granskat', 'Godkänt': 'badge-godkant',
    'Klar': 'badge-klart', 'Pausad': 'badge-utkast', 'Avbruten': 'badge-danger',
  };
  return `<span class="badge ${map[status] || ''}">${status}</span>`;
}

function badgeTyp(typ) {
  const map = {
    'Kabelskåp':       'badge-navy',
    'Kabelförläggning':'badge-pagaende',
    'Nätstation':      'badge-planerat',
    'Övrigt':          'badge-utkast',
  };
  return `<span class="badge ${map[typ] || ''}">${escHtml(typ)}</span>`;
}

function kr(val) {
  if (val == null || val === '') return '–';
  return Number(val).toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' kr';
}

function num(val) {
  if (val == null) return '–';
  const n = Number(val);
  return Number.isInteger(n) ? n.toString() : n.toLocaleString('sv-SE', { maximumFractionDigits: 3 });
}

function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ----------------------------------------------------------------
// FAS-HJÄLPFUNKTIONER
// ----------------------------------------------------------------
const FASER = ['Beredning', 'Projektledning', 'Utförda'];
const C_OMRADEN = ['C05', 'C12', 'C13'];  // E.ON C-områden
const FAS_TROSKEL = { 'Beredning': 30, 'Projektledning': 21, 'Utförda': 14 };
const FAS_CSS = {
  'Beredning': 'badge-beredning', 'Projektledning': 'badge-offert', 'Utförda': 'badge-klart',
};

// ----------------------------------------------------------------
// CHECKLISTA
// ----------------------------------------------------------------
const CHECKLISTA = [
  { nr:  0, kort: 'PWB',         namn: 'Starta upp projekt i PWB',                               grupp: 0 },
  { nr:  1, kort: 'Persl.',      namn: 'Personaliggare projekt över behövs >236800kr',            grupp: 0 },
  { nr:  2, kort: 'Projna.',     namn: 'Starta upp projektet i projektnavet',                     grupp: 0 },
  { nr:  3, kort: 'Beställn.',   namn: 'Gå igenom beställningen',                                grupp: 0 },
  { nr:  4, kort: 'Inst.',       namn: 'Kontakta installatören',                                 grupp: 0 },
  { nr:  5, kort: 'Upps.best.',  namn: 'Kontakta beställaren för uppstart av beredning',         grupp: 0 },
  { nr:  6, kort: 'Pärmstr.',    namn: 'Skapa projektpärmstruktur',                              grupp: 0 },
  { nr:  7, kort: 'Platsbek.',   namn: 'Platsbesök (bilder/markklass)',                          grupp: 0 },
  { nr:  8, kort: 'Schaktk.',    namn: 'Schaktkarta',                                            grupp: 1 },
  { nr:  9, kort: 'Markpr.',     namn: 'Markprover',                                             grupp: 1 },
  { nr: 10, kort: 'Ledningk.',   namn: 'Ledningskarta',                                          grupp: 1 },
  { nr: 11, kort: 'Återst.k.',   namn: 'Återställningskarta',                                    grupp: 1 },
  { nr: 12, kort: 'Hinderk.',    namn: 'Hinderkarta',                                            grupp: 1 },
  { nr: 13, kort: 'Rasering.',   namn: 'Raseringskarta',                                         grupp: 1 },
  { nr: 14, kort: 'Byggprot.',   namn: 'Byggprotokoll',                                          grupp: 2 },
  { nr: 15, kort: 'Bildbesk.',   namn: 'Bildbeskrivning',                                        grupp: 2 },
  { nr: 16, kort: 'Matl.lista',  namn: 'Materiallista',                                          grupp: 2 },
  { nr: 17, kort: 'Kalkyl',      namn: 'Kalkyl',                                                 grupp: 2 },
  { nr: 18, kort: 'Mat.best.',   namn: 'Materialbeställning',                                    grupp: 2 },
  { nr: 19, kort: 'Schaktprot.', namn: 'Schaktprotokoll',                                        grupp: 2 },
  { nr: 20, kort: 'Ledningsk.',  namn: 'Ledningskollen',                                         grupp: 3 },
  { nr: 21, kort: 'Trafikv.',    namn: 'Trafikverket',                                           grupp: 3 },
  { nr: 22, kort: 'Rev avtal',   namn: 'Rev avtal',                                              grupp: 3 },
  { nr: 23, kort: 'Grävtillst.', namn: 'Grävtillstånd',                                         grupp: 3 },
  { nr: 24, kort: 'TA-plan',     namn: 'TA-plan',                                                grupp: 3 },
  { nr: 25, kort: 'Vägfören.',   namn: 'Vägförening/Samfälligheter/Gemensamhetsanläggningar',   grupp: 3 },
  { nr: 26, kort: 'Skyddad N.',  namn: 'Skyddad Natur',                                          grupp: 3 },
  { nr: 27, kort: 'Skogens P.',  namn: 'Skogens Pärlor',                                        grupp: 3 },
  { nr: 28, kort: 'Fornsök',     namn: 'Fornsök',                                                grupp: 3 },
  { nr: 29, kort: 'Artport.',    namn: 'Artportalen',                                            grupp: 3 },
  { nr: 30, kort: 'Samråd',      namn: 'Samråd',                                                 grupp: 3 },
  { nr: 31, kort: 'Strandsk.',   namn: 'Strandskydd',                                            grupp: 3 },
  { nr: 32, kort: 'Föror.mark',  namn: 'Förorenad mark',                                         grupp: 3 },
  { nr: 33, kort: 'Markäg.',     namn: 'Kontakta markägaren',                                    grupp: 3 },
  { nr: 34, kort: 'AMplan',      namn: 'Arbetsmiljöplan',                                        grupp: 4 },
  { nr: 35, kort: 'Miljöplan',   namn: 'Miljöplan',                                              grupp: 4 },
  { nr: 36, kort: 'Kval.plan',   namn: 'Kvalitetsplan',                                          grupp: 4 },
  { nr: 37, kort: 'Masshant.',   namn: 'Masshanteringsplan',                                     grupp: 4 },
];
const GRUPPER = [
  { id: 0, namn: 'Uppstart',     color: '#7c3aed', count: 8  },
  { id: 1, namn: 'Kartläggning', color: '#d97706', count: 6  },
  { id: 2, namn: 'Handlingar',   color: '#2563eb', count: 6  },
  { id: 3, namn: 'Tillstånd',    color: '#16a34a', count: 14 },
  { id: 4, namn: 'Kvalitet',     color: '#dc2626', count: 4  },
];

function badgeFas(fas) {
  if (!fas) return '<span class="text-muted" style="font-size:12px">Ingen fas</span>';
  return `<span class="badge ${FAS_CSS[fas] || ''}">${escHtml(fas)}</span>`;
}

function formatKr(belopp) {
  return (belopp || 0).toLocaleString('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' kr';
}

function dagarIFas(fasStartdatum) {
  if (!fasStartdatum) return null;
  const ms = Date.now() - new Date(fasStartdatum).getTime();
  return Math.floor(ms / 86400000);
}

function rodFlaggHtml(fas, dagar) {
  if (dagar === null || !fas) return '';
  const troskel = FAS_TROSKEL[fas];
  if (!troskel || dagar <= troskel) return '';
  return `<span class="rod-flagg" title="${dagar} dagar – gräns ${troskel}d">⚑ ${dagar}d</span>`;
}

// ----------------------------------------------------------------
// VIEW: PROJEKT (card dashboard)
// ----------------------------------------------------------------
async function renderProjekt(app) {
  app.innerHTML = `<div class="text-muted" style="padding:48px;text-align:center">Laddar dashboard…</div>`;
  let checklistor = {};
  let kommandeMontage = [];
  let anslProjekt = [];
  let anslAktivaCount = 0, anslRiskerCount = 0, anslBlkCount = 0, anslDoneCount = 0;
  let anslAvgLT = '–', anslNyaManed = 0, nyaDelta = 0;
  try {
    const [pr, ck, ansl] = await Promise.all([
      api('GET', '/projekt'),
      api('GET', '/projekt/checklistor').catch(() => ({ checklistor: {} })),
      api('GET', '/anslutning').catch(() => ({ projekt: [] })),
    ]);
    S.projekt = pr.projekt || [];
    checklistor = ck.checklistor || {};
    const idag = new Date(); idag.setHours(0,0,0,0);
    const om30 = new Date(idag); om30.setDate(om30.getDate()+30);
    kommandeMontage = (ansl.projekt || []).filter(x => {
      if (!x.montStart || x.driftDat) return false;
      if (x.fas==='Avslutat'||x.fas==='Drifttagning klar') return false;
      const d = new Date(x.montStart);
      return d >= idag && d <= om30;
    }).sort((a,b)=>a.montStart.localeCompare(b.montStart));
    anslProjekt = ansl.projekt || [];
    anslAktivaCount = anslProjekt.filter(x=>x.fas!=='Avslutat').length;
    anslRiskerCount = anslProjekt.filter(anslRisk).length;
    anslBlkCount    = anslProjekt.filter(x=>x.blockering).length;
    const anslDone  = anslProjekt.filter(x=>x.fas==='Avslutat'||x.fas==='Drifttagning klar'||!!x.driftDat);
    anslDoneCount   = anslDone.length;
    const withLT    = anslDone.filter(x=>anslLT(x));
    anslAvgLT       = withLT.length ? Math.round(withLT.map(anslLT).reduce((a,b)=>a+b,0)/withLT.length) : '–';
    const nowD      = new Date();
    anslNyaManed    = anslProjekt.filter(x=>{ if(!x.berStart) return false; const d=new Date(x.berStart); return d.getFullYear()===nowD.getFullYear()&&d.getMonth()===nowD.getMonth(); }).length;
    const prevMs    = new Date(nowD.getFullYear(),nowD.getMonth()-1,1);
    const prevMe    = new Date(nowD.getFullYear(),nowD.getMonth(),0);
    const anslForeg = anslProjekt.filter(x=>{ if(!x.berStart) return false; const d=new Date(x.berStart); return d>=prevMs&&d<=prevMe; }).length;
    nyaDelta        = anslNyaManed - anslForeg;
  } catch (e) {
    app.innerHTML = `<p class="text-red" style="padding:24px">Fel: ${e.message}</p>`;
    return;
  }
  await laddaBeredare();

  const ckMap = {};
  for (const [pid, data] of Object.entries(checklistor)) {
    const doneArr  = Array.isArray(data) ? data : (data.done || []);
    const ejRelArr = Array.isArray(data) ? [] : (data.ej_rel || []);
    ckMap[parseInt(pid)] = new Set([...doneArr, ...ejRelArr]);
  }
  const N = CHECKLISTA.length;

  function getDone(p)        { return ckMap[p.id] ? ckMap[p.id].size : (parseInt(p.checklista_klar) || 0); }
  function getGruppDone(p,g) { return CHECKLISTA.filter(c => c.grupp === g).filter(c => ckMap[p.id]?.has(c.nr)).length; }

  const FAS_COLOR = { 'Beredning': '#d97706', 'Projektledning': '#7c3aed', 'Utförda': '#16a34a' };

  const montageListHtml = kommandeMontage.length === 0
    ? `<div style="padding:16px 0;text-align:center;color:rgba(42,36,64,.4);font-size:11px;font-family:monospace">Inga montagestart inom 30 dagar</div>`
    : kommandeMontage.map(x => {
        const dt = x.montStart.slice(5).replace('-','/');
        const daysLeft = Math.round((new Date(x.montStart)-new Date())/86400000);
        const dlColor = daysLeft<=7?'var(--red)':daysLeft<=14?'var(--amber)':'rgba(124,58,237,.9)';
        return `<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(124,58,237,.08)">
          <div style="font-size:12px;font-family:monospace;font-weight:700;color:${dlColor};flex-shrink:0;min-width:34px">${dt}</div>
          <div style="flex:1;min-width:0;font-size:11px;font-weight:600;color:rgba(42,36,64,.9);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(x.namn)}</div>
          <div style="font-size:11px;font-family:monospace;font-weight:700;color:${dlColor};flex-shrink:0">${daysLeft}d</div>
        </div>`;
      }).join('');

  app.innerHTML = `
    <div class="pk-banner" style="align-items:flex-start;flex-direction:column;gap:16px">
      <div class="pk-banner-title" style="position:relative;z-index:1">Projektöversikt</div>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;width:100%;position:relative;z-index:1">
        ${anslKpiHtml('Ärenden totalt',anslProjekt.length,`${anslAktivaCount} aktiva`,undefined,'var(--cyan)')}
        ${anslKpiHtml('Nya denna månad',anslNyaManed,'beställda denna månad',nyaDelta,'var(--blue)')}
        ${anslKpiHtml('Riskärenden',anslRiskerCount,'< 21d eller blockerade',anslRiskerCount>3?1:-1,'var(--red)')}
        ${anslKpiHtml('Blockerade',anslBlkCount,'väntar på åtgärd',undefined,'var(--amber)')}
        ${anslKpiHtml('Avg. ledtid',anslAvgLT,`dagar (${anslDoneCount} avslutade)`,undefined,'var(--green)')}
      </div>
      <div style="display:grid;grid-template-columns:1fr min(360px,40%);gap:16px;width:100%;position:relative;z-index:1">
        <div style="background:rgba(124,58,237,.05);border-radius:10px;border:1px solid rgba(124,58,237,.12);backdrop-filter:blur(4px);padding:14px 16px">
          <div style="font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:rgba(124,58,237,.6);margin-bottom:12px">Nya ärenden / månad</div>
          ${anslBarChartHtml(anslProjekt)}
        </div>
        <div style="background:rgba(124,58,237,.05);border-radius:10px;border:1px solid rgba(124,58,237,.15);backdrop-filter:blur(6px)">
          <div style="padding:11px 16px;border-bottom:1px solid rgba(124,58,237,.10);display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:rgba(124,58,237,.7)">Kommande montagestart</span>
            <span style="font-size:10px;font-family:monospace;color:rgba(42,36,64,.4)">${kommandeMontage.length} st / 30 dagar</span>
          </div>
          <div class="ansl-scroll" style="padding:4px 16px;max-height:160px">${montageListHtml}</div>
        </div>
      </div>
    </div>

    <div class="pk-banner" style="align-items:flex-start">
      <div class="pk-banner-left">
        <div class="pk-banner-title">Beredningsöversikt</div>
        <div class="pk-banner-sub" id="pkSub"></div>
        <div style="margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;position:relative;z-index:1">
          <div class="pk-fas-stats" id="pkFasStat"></div>
          <button class="btn btn-primary btn-lg" id="btnNyttProjekt" style="flex-shrink:0">+ Nytt projekt</button>
        </div>
      </div>
    </div>

    <div class="pk-controls">
      <input type="search" class="form-control pk-search" id="pkSok" placeholder="🔍  Sök projekt, IB-nummer, beredare…">
      <select class="form-control" id="pkFas" style="max-width:155px">
        <option value="">Alla faser</option>
        ${FASER.map(f => `<option>${escHtml(f)}</option>`).join('')}
      </select>
      <select class="form-control" id="pkBer" style="max-width:170px">
        <option value="">Alla beredare</option>
        ${S.beredare.map(b => `<option ${S.minBeredare === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('')}
      </select>
      <select class="form-control" id="pkOmrade" style="max-width:150px">
        <option value="">Alla områden</option>
        ${C_OMRADEN.map(o => `<option>${o}</option>`).join('')}
      </select>
      <div class="pk-toggle">
        <button class="pk-tb" id="pkTKort" title="Kortvyn">▦ Kort</button>
        <button class="pk-tb active" id="pkTLista" title="Listvy">☰ Lista</button>
      </div>
    </div>

    <div id="pkContent"></div>`;

  let viewMode = 'lista';

  function updateBanner() {
    const tot = S.projekt.length;
    const totDone = S.projekt.reduce((s, p) => s + getDone(p), 0);
    const pct = (tot * N) ? Math.round(100 * totDone / (tot * N)) : 0;
    document.getElementById('pkSub').innerHTML =
      `<span class="pk-stat-chip">${tot} projekt</span> <span class="pk-stat-chip pk-green">${pct}% klara checklistpunkter</span>`;
    document.getElementById('pkFasStat').innerHTML = FASER.map(f => {
      const cnt = S.projekt.filter(p => p.fas === f).length;
      const col = FAS_COLOR[f] || 'var(--gray-400)';
      return `<div class="pk-fas-box" style="border-color:${col}40">
        <span class="pk-fas-num" style="color:${col}">${cnt}</span>
        <span class="pk-fas-lbl">${escHtml(f)}</span>
      </div>`;
    }).join('') + (() => {
      const ing = S.projekt.filter(p => !p.fas).length;
      return `<div class="pk-fas-box" style="border-color:#ffffff30">
        <span class="pk-fas-num" style="color:rgba(255,255,255,.6)">${ing}</span>
        <span class="pk-fas-lbl">Ingen fas</span>
      </div>`;
    })();
  }

  function getFiltered() {
    const sok = document.getElementById('pkSok').value.toLowerCase();
    const fas = document.getElementById('pkFas').value;
    const ber = document.getElementById('pkBer').value;
    const omr = document.getElementById('pkOmrade').value;
    return S.projekt.filter(p => {
      if (fas && p.fas !== fas) return false;
      if (ber && p.beredare !== ber) return false;
      if (omr && (p.omrade || '') !== omr) return false;
      if (sok) {
        const hay = `${p.projektnummer} ${p.projektnamn} ${p.beredare} ${p.kund||''} ${p.ib_nummer||''} ${p.tilldelat_till||''}`.toLowerCase();
        if (!hay.includes(sok)) return false;
      }
      return true;
    });
  }

  function kortHtml(p) {
    const done = getDone(p);
    const pct  = Math.round(100 * done / N);
    const tc   = FAS_COLOR[p.fas] || '#a1a1aa';
    const period = (p.beredning_start || p.beredning_slut)
      ? `${p.beredning_start || '?'} → ${p.beredning_slut || '?'}` : null;
    const grupper = GRUPPER.map(g => {
      const kl  = getGruppDone(p, g.id);
      const gPct = Math.round(100 * kl / g.count);
      return `<div class="pk-grp">
        <span class="pk-grp-lbl" style="color:${g.color}">${escHtml(g.namn)}</span>
        <div class="pk-grp-track"><div class="pk-grp-fill" style="width:${gPct}%;background:${g.color}"></div></div>
        <span class="pk-grp-num">${kl}/${g.count}</span>
      </div>`;
    }).join('');
    const tags = [
      p.ib_nummer    && `<span class="pk-tag">IB ${escHtml(p.ib_nummer)}</span>`,
      p.tilldelat_till && `<span class="pk-tag">👤 ${escHtml(p.tilldelat_till)}</span>`,
      p.omrade       && `<span class="pk-tag">📍 ${escHtml(p.omrade)}</span>`,
    ].filter(Boolean).join('');
    return `<div class="pk-card" style="--tc:${tc}">
      <div class="pk-card-head">
        <span class="pk-card-nr">${escHtml(p.projektnummer)}</span>
        ${badgeFas(p.fas)}
      </div>
      <div class="pk-card-name">${escHtml(p.projektnamn)}</div>
      ${tags ? `<div class="pk-tags">${tags}</div>` : ''}
      ${period ? `<div class="pk-period">📅 ${escHtml(period)}</div>` : ''}
      <div class="pk-grps">${grupper}</div>
      <div class="pk-tot-row">
        <div class="pk-tot-track"><div class="pk-tot-fill" style="width:${pct}%"></div></div>
        <span class="pk-tot-txt">${done}/${N} (${pct}%)</span>
      </div>
      <div class="pk-card-foot">
        <span class="pk-card-ber">👷 ${escHtml(p.beredare)}</span>
        <div class="pk-card-btns">
          <button class="btn btn-sm btn-navy" data-id="${p.id}" data-a="oppna">Öppna</button>
          <button class="btn btn-sm btn-outline" data-id="${p.id}" data-a="red">✎</button>
          <button class="btn btn-sm btn-danger" data-id="${p.id}" data-a="del">✕</button>
        </div>
      </div>
    </div>`;
  }

  function renderKort() {
    const lista = getFiltered();
    const c = document.getElementById('pkContent');
    if (!lista.length) {
      c.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-title">Inga projekt hittades</div></div>`;
      return;
    }
    c.innerHTML = `<div class="pk-grid">${lista.map(kortHtml).join('')}</div>`;
    wireActions(c);
  }

  function renderLista() {
    const lista = getFiltered();
    const c = document.getElementById('pkContent');
    if (!lista.length) {
      c.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-title">Inga projekt hittades</div></div>`;
      return;
    }
    c.innerHTML = `<div class="card"><div class="table-wrap"><table>
      <thead><tr>
        <th>Projektnr</th><th>Projektnamn</th><th>Beredare</th><th>IB Nr</th><th>Beredning</th><th>Fas</th>
        ${GRUPPER.map(g => `<th style="min-width:90px">${escHtml(g.namn)}</th>`).join('')}
        <th style="min-width:80px">Totalt</th><th></th>
      </tr></thead>
      <tbody>${lista.map(p => {
        const done = getDone(p);
        const pct  = Math.round(100 * done / N);
        const period = (p.beredning_start || p.beredning_slut)
          ? `${(p.beredning_start||'').slice(5) || '?'} – ${(p.beredning_slut||'').slice(5) || '?'}` : '–';
        const grpCols = GRUPPER.map(g => {
          const kl = getGruppDone(p, g.id);
          const gp = Math.round(100 * kl / g.count);
          return `<td>
            <div style="font-size:11px;font-weight:700;color:${g.color}">${kl}/${g.count}</div>
            <div style="height:4px;background:${g.color}22;border-radius:2px;margin-top:3px">
              <div style="height:100%;width:${gp}%;background:${g.color};border-radius:2px"></div>
            </div></td>`;
        }).join('');
        return `<tr>
          <td class="mono">${escHtml(p.projektnummer)}</td>
          <td><strong>${escHtml(p.projektnamn)}</strong></td>
          <td>${escHtml(p.beredare || '–')}</td>
          <td>${escHtml(p.ib_nummer || '–')}</td>
          <td style="font-size:11px;white-space:nowrap">${escHtml(period)}</td>
          <td>${badgeFas(p.fas)}</td>
          ${grpCols}
          <td>
            <div style="font-size:12px;font-weight:700;color:#7c3aed">${pct}%</div>
            <div class="pm-prog" style="margin-top:3px"><div class="pm-prog-fill" style="width:${pct}%"></div></div>
          </td>
          <td><div class="flex gap-1">
            <button class="btn btn-sm btn-navy" data-id="${p.id}" data-a="oppna">Öppna</button>
            <button class="btn btn-sm btn-danger" data-id="${p.id}" data-a="del">✕</button>
          </div></td>
        </tr>`;
      }).join('')}</tbody>
    </table></div></div>`;
    wireActions(c);
  }

  function wireActions(container) {
    container.querySelectorAll('button[data-a]').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const p  = S.projekt.find(x => x.id == id);
        if (btn.dataset.a === 'oppna') {
          navigate('projekt-detail', { id });
        } else if (btn.dataset.a === 'red') {
          modalRedigeraProjekt(p);
        } else if (btn.dataset.a === 'del') {
          const ok = await confirm('Ta bort projekt', `Ta bort "${p.projektnamn}"?`);
          if (!ok) return;
          try {
            await api('DELETE', `/projekt/${id}`);
            toast('Projekt borttaget', 'success');
            S.projekt = S.projekt.filter(x => x.id != id);
            delete ckMap[id];
            updateBanner();
            renderAll();
          } catch (e2) { toast(e2.message, 'error'); }
        }
      });
    });
  }

  function renderAll() {
    viewMode === 'kort' ? renderKort() : renderLista();
  }

  updateBanner();
  renderAll();

  document.getElementById('pkSok').addEventListener('input', renderAll);
  document.getElementById('pkFas').addEventListener('change', renderAll);
  document.getElementById('pkBer').addEventListener('change', renderAll);
  document.getElementById('pkOmrade').addEventListener('change', renderAll);
  document.getElementById('btnNyttProjekt').addEventListener('click', () => modalNyttProjekt());
  document.getElementById('pkTKort').addEventListener('click', () => {
    viewMode = 'kort';
    document.getElementById('pkTKort').classList.add('active');
    document.getElementById('pkTLista').classList.remove('active');
    renderAll();
  });
  document.getElementById('pkTLista').addEventListener('click', () => {
    viewMode = 'lista';
    document.getElementById('pkTLista').classList.add('active');
    document.getElementById('pkTKort').classList.remove('active');
    renderAll();
  });
}

async function laddaProjekt() {
  S.projekt = (await api('GET', '/projekt')).projekt || [];
}

async function laddaBeredare() {
  if (S.beredare.length) return;
  S.beredare = (await api('GET', '/beredare')).beredare || [];
}

function modalNyttProjekt(prefill = {}) {
  modalProjektForm(null, prefill);
}
function modalRedigeraProjekt(p) {
  modalProjektForm(p, p);
}

async function modalProjektFormEnkel(onSuccess) {
  await laddaBeredare();
  const nasta = (await api('GET', '/projekt/nasta-nummer')).projektnummer || '';
  const berOpts = S.beredare.map(b => `<option>${escHtml(b.namn)}</option>`).join('');
  Modal.open(
    'Nytt projekt',
    `<form id="projektFormEnkel">
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Projektnummer <span class="req">*</span></label>
          <input name="projektnummer" class="form-control" value="${escHtml(nasta)}" required>
        </div>
        <div class="form-group">
          <label class="form-label">Beredare <span class="req">*</span></label>
          <select name="beredare" class="form-control" required>
            <option value="">– välj –</option>${berOpts}
          </select>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Projektnamn <span class="req">*</span></label>
        <input name="projektnamn" class="form-control" required>
      </div>
      <div class="form-group">
        <label class="form-label">Anteckningar</label>
        <textarea name="anteckningar" class="form-control" rows="2"></textarea>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaProjektEnkel">Skapa</button>
     <button class="btn btn-secondary" id="avbrytProjektEnkel">Avbryt</button>`
  );
  document.getElementById('avbrytProjektEnkel').addEventListener('click', Modal.close);
  document.getElementById('sparaProjektEnkel').addEventListener('click', async () => {
    const f = document.getElementById('projektFormEnkel');
    if (!f.reportValidity()) return;
    const body = Object.fromEntries(new FormData(f).entries());
    try {
      const res = await api('POST', '/projekt', body);
      toast('Projekt skapat', 'success');
      Modal.close();
      if (onSuccess) await onSuccess(res);
    } catch (e) { toast(e.message, 'error'); }
  });
}

async function modalProjektForm(existing, data = {}, onSuccess = null) {
  await laddaBeredare();
  const nasta = existing ? '' : ((await api('GET', '/projekt/nasta-nummer')).projektnummer || '');
  const berOpts = S.beredare.map(b =>
    `<option ${data.beredare === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('');
  const fasOpts = ['', ...FASER].map(f =>
    `<option value="${f}" ${(data.fas || '') === f ? 'selected' : ''}>${f || '– ingen fas –'}</option>`).join('');

  Modal.open(
    existing ? 'Redigera projekt' : 'Nytt projekt',
    `<form id="projektForm">
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Projektnummer <span class="req">*</span></label>
          <input name="projektnummer" class="form-control" value="${escHtml(data.projektnummer || nasta)}" ${existing ? '' : 'required'}>
        </div>
        <div class="form-group">
          <label class="form-label">IB Nummer</label>
          <input name="ib_nummer" class="form-control" value="${escHtml(data.ib_nummer || '')}">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Projektnamn <span class="req">*</span></label>
        <input name="projektnamn" class="form-control" value="${escHtml(data.projektnamn || '')}" required>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Kategori</label>
          <input name="kategori" class="form-control" value="${escHtml(data.kategori || '')}">
        </div>
        <div class="form-group">
          <label class="form-label">Tilldelat till</label>
          <input name="tilldelat_till" class="form-control" value="${escHtml(data.tilldelat_till || '')}">
        </div>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Område (C-område)</label>
          <input name="omrade" class="form-control" list="cOmradenList" value="${escHtml(data.omrade || '')}" placeholder="t.ex. C05">
          <datalist id="cOmradenList">${C_OMRADEN.map(o => `<option value="${o}">`).join('')}</datalist>
        </div>
        <div class="form-group">
          <label class="form-label">Kund</label>
          <input name="kund" class="form-control" value="${escHtml(data.kund || '')}">
        </div>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Inkommande beställningar</label>
          <input name="inkommande_bestallningar" class="form-control" value="${escHtml(data.inkommande_bestallningar || '')}">
        </div>
        <div class="form-group">
          <label class="form-label">Bekräftade beställningar</label>
          <input name="bekraftade_bestallningar" class="form-control" value="${escHtml(data.bekraftade_bestallningar || '')}">
        </div>
      </div>
      <div class="form-row cols-3">
        <div class="form-group">
          <label class="form-label">Fas</label>
          <select name="fas" class="form-control">${fasOpts}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Beredning start</label>
          <input type="date" name="beredning_start" class="form-control" value="${data.beredning_start || ''}">
        </div>
        <div class="form-group">
          <label class="form-label">Beredning slut</label>
          <input type="date" name="beredning_slut" class="form-control" value="${data.beredning_slut || ''}">
        </div>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Beredare <span class="req">*</span></label>
          <select name="beredare" class="form-control" required>
            <option value="">– välj –</option>${berOpts}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Anslutningspunkt</label>
          <input name="anslutningspunkt" class="form-control" value="${escHtml(data.anslutningspunkt || '')}">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Anteckningar</label>
        <textarea name="anteckningar" class="form-control">${escHtml(data.anteckningar || '')}</textarea>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaProjekt">${existing ? 'Spara' : 'Skapa'}</button>
     <button class="btn btn-secondary" id="avbrytProjekt">Avbryt</button>`,
    { noBackdropClose: !!onSuccess }
  );

  document.getElementById('avbrytProjekt').addEventListener('click', Modal.close);
  document.getElementById('sparaProjekt').addEventListener('click', async () => {
    const f = document.getElementById('projektForm');
    if (!f.reportValidity()) return;
    const body = Object.fromEntries(new FormData(f).entries());
    try {
      if (existing) {
        await api('PUT', `/projekt/${existing.id}`, body);
        toast('Projekt sparat', 'success');
      } else {
        await api('POST', '/projekt', body);
        toast('Projekt skapat', 'success');
      }
      Modal.close();
      if (onSuccess) { await onSuccess(); } else { navigate('projekt'); }
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// VIEW: PROJEKT DETAIL
// ----------------------------------------------------------------
async function renderProjektDetail(app, id) {
  app.innerHTML = `<div class="text-muted" style="padding:32px;text-align:center">Laddar…</div>`;
  let p, fasData, tillstandLista, aktiviteter, checklista, statusVarden;
  try {
    [p, fasData, tillstandLista, aktiviteter, checklista, statusVarden] = await Promise.all([
      api('GET', `/projekt/${id}`).then(r => r.projekt),
      api('GET', `/projekt/${id}/fas`).catch(() => ({ fas: null, historik: [] })),
      api('GET', `/projekt/${id}/tillstand`).then(r => r.tillstand || []).catch(() => []),
      api('GET', `/projekt/${id}/aktiviteter`).then(r => r.aktiviteter || []).catch(() => []),
      api('GET', `/projekt/${id}/checklista`).then(r => r.checklista || []).catch(() => []),
      api('GET', `/projekt/${id}/status`).then(r => r.status || {}).catch(() => ({})),
    ]);
  } catch (e) {
    app.innerHTML = `<p class="text-red" style="padding:24px">Kunde inte ladda projekt: ${e.message}</p>`;
    return;
  }

  const fasHistorik = fasData.historik || [];
  const aktuellFas = p.fas || null;
  const ckSet    = new Set(checklista.filter(c => c.utford).map(c => c.item_nr));
  const ejRelSet = new Set(checklista.filter(c => c.ej_relevant).map(c => c.item_nr));

  function fasTidslinjeHtml() {
    return `<div class="fas-tidslinje" id="fasTidslinje">` +
      FASER.map((fas, i) => {
        const hrad = fasHistorik.find(h => h.fas === fas);
        const arAktiv = fas === aktuellFas;
        const arKlar  = fasHistorik.some(h => h.fas === fas && h.slutdatum);
        const cls = arAktiv ? 'aktiv' : arKlar ? 'klar' : '';
        const datumTxt = hrad ? `<span class="fas-steg-datum">${hrad.startdatum || ''}</span>` : '';
        return `<div class="fas-steg ${cls}" data-fas="${escHtml(fas)}" title="Sätt fas: ${escHtml(fas)}">
          <span class="fas-steg-nr">${i + 1}.</span>${escHtml(fas)}${datumTxt}</div>`;
      }).join('') + `</div>`;
  }

  function tillstandHtml(lista) {
    if (!lista.length) return `<p class="text-muted" style="padding:12px;font-size:13px">Inga tillstånd registrerade</p>`;
    const bTill = { 'Inväntas': 'badge-inväntas', 'Mottaget': 'badge-mottaget', 'Ej krävs': 'badge-ej-kravs' };
    return `<ul class="tillstand-lista">` + lista.map(t => `
      <li class="tillstand-rad">
        <span class="tillstand-namn">${escHtml(t.namn)}</span>
        ${t.datum ? `<span class="tillstand-datum">${t.datum}</span>` : ''}
        <span class="badge ${bTill[t.status] || ''}">${escHtml(t.status)}</span>
        <button class="btn btn-sm btn-outline" data-tid="${t.id}" data-action="edit-till">✎</button>
        <button class="btn btn-sm btn-danger" data-tid="${t.id}" data-action="del-till">✕</button>
      </li>`).join('') + `</ul>`;
  }

  function aktivitetHtml(lista) {
    if (!lista.length) return `<p class="text-muted" style="padding:12px;font-size:13px">Inga aktiviteter ännu</p>`;
    const ikoner = { 'fas-byte': '🔄', 'anteckning': '📝' };
    return `<ul class="aktivitets-lista">` + lista.map(a => `
      <li class="aktivitets-rad">
        <span class="aktivitets-tid">${(a.tidpunkt||'').slice(0,16)}</span>
        <span class="aktivitets-ikon">${ikoner[a.typ] || '•'}</span>
        <span class="aktivitets-text">${escHtml(a.beskrivning)}</span>
      </li>`).join('') + `</ul>`;
  }

  const done0 = ckSet.size;
  const pct0  = Math.round(100 * done0 / CHECKLISTA.length);

  const infoFält = [
    ['IB Nummer', p.ib_nummer], ['Kategori', p.kategori], ['Tilldelat till', p.tilldelat_till],
    ['Område', p.omrade], ['Ink. beställningar', p.inkommande_bestallningar],
    ['Bek. beställningar', p.bekraftade_bestallningar],
    ['Beredning start', p.beredning_start], ['Beredning slut', p.beredning_slut],
    ['Beredare', p.beredare], ['Kund', p.kund],
  ];

  app.innerHTML = `
    <div class="page-header">
      <div class="flex items-center gap-2" style="flex-wrap:wrap;gap:8px">
        <button class="btn btn-outline btn-sm" id="btnBack">← Tillbaka</button>
        <h1 class="page-title">${escHtml(p.projektnummer)} – ${escHtml(p.projektnamn)}</h1>
        ${badgeFas(aktuellFas)}
      </div>
      <button class="btn btn-outline btn-sm" id="btnEditProjekt">Redigera</button>
    </div>

    <div class="pm-info-strip mb-2">
      ${infoFält.map(([l, v]) => `
        <div class="pm-info-cell">
          <div class="pm-info-lbl">${l}</div>
          <div class="pm-info-val">${escHtml(v || '–')}</div>
        </div>`).join('')}
    </div>

    <div class="tabs">
      <button class="tab-btn active" data-tab="oversikt">Översikt</button>
      <button class="tab-btn" data-tab="planering">Planeringsstatus</button>
    </div>
    <div class="tab-pane active" id="pdTabOversikt">
    <div class="detail-layout">
      <div>
        <div class="card mb-2">
          <div class="card-header"><span class="card-title">Fas</span><span class="text-sm text-muted">Klicka för att byta</span></div>
          <div class="card-body" style="padding:12px">${fasTidslinjeHtml()}</div>
        </div>
        <div class="card mb-2">
          <div class="card-header">
            <span class="card-title">Tillstånd</span>
            <button class="btn btn-navy btn-sm" id="btnNyttTillstand">+ Lägg till</button>
          </div>
          <div id="tillstandKontainer">${tillstandHtml(tillstandLista)}</div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Aktivitetslogg</span>
            <button class="btn btn-outline btn-sm" id="btnNyAktivitet">+ Anteckning</button>
          </div>
          <div id="aktivitetKontainer">${aktivitetHtml(aktiviteter)}</div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Checklista</span>
            <span id="ckProg" class="badge badge-klart">${done0}/${CHECKLISTA.length} (${pct0}%)</span>
          </div>
          <div class="pm-prog" style="border-radius:0;height:5px;margin:0">
            <div class="pm-prog-fill" id="ckBar" style="width:${pct0}%"></div>
          </div>
          <div id="ckLista"></div>
        </div>
        ${p.anteckningar ? `<div class="card mt-2"><div class="card-body"><p class="text-sm text-muted">${escHtml(p.anteckningar)}</p></div></div>` : ''}
      </div>
    </div>
    </div>
    <div class="tab-pane" id="pdTabPlanering">
      ${projektStatusPaneHtml(statusVarden || {})}
    </div>
    `;

  function renderCk() {
    const ejRels = ejRelSet.size;
    const done   = ckSet.size + ejRels;
    const pct    = Math.round(100 * done / CHECKLISTA.length);
    document.getElementById('ckBar').style.width = pct + '%';
    document.getElementById('ckProg').textContent =
      `${done}/${CHECKLISTA.length} utförda${ejRels ? ` · ${ejRels} ej relevant` : ''}`;
    document.getElementById('ckLista').innerHTML = GRUPPER.map(g => {
      const items = CHECKLISTA.filter(c => c.grupp === g.id);
      const doneG = items.filter(c => ckSet.has(c.nr) || ejRelSet.has(c.nr)).length;
      return `<div class="ck-grupp">
        <div class="ck-grp-hdr" style="border-left-color:${g.color}">
          <span style="color:${g.color};font-weight:700">${escHtml(g.namn)}</span>
          <span class="text-sm text-muted">${doneG}/${items.length}</span>
        </div>
        ${items.map(c => {
          const ok    = ckSet.has(c.nr);
          const ejRel = ejRelSet.has(c.nr);
          return `<div class="ck-item${ok ? ' ok' : ejRel ? ' ej-rel' : ''}">
            <span class="ck-text">${escHtml(c.namn)}</span>
            <div class="ck-actions">
              <label class="ck-lbl ck-lbl-utford" title="Markera som utförd">
                <input type="checkbox" class="ck-cb" data-nr="${c.nr}" data-type="utford"
                  ${ok ? 'checked' : ''} style="accent-color:${g.color}">
                <span>Utförd</span>
              </label>
              <label class="ck-lbl ck-lbl-ejrel" title="Markera som ej relevant">
                <input type="checkbox" class="ck-cb" data-nr="${c.nr}" data-type="ejrel"
                  ${ejRel ? 'checked' : ''}>
                <span>Ej relevant</span>
              </label>
            </div>
          </div>`;
        }).join('')}
      </div>`;
    }).join('');

    document.getElementById('ckLista').querySelectorAll('.ck-cb').forEach(cb => {
      cb.addEventListener('change', async () => {
        const nr   = parseInt(cb.dataset.nr);
        const type = cb.dataset.type;
        const item = cb.closest('.ck-item');
        const cbUtford = item.querySelector('[data-type="utford"]');
        const cbEjrel  = item.querySelector('[data-type="ejrel"]');
        if (type === 'utford' && cb.checked) cbEjrel.checked = false;
        if (type === 'ejrel'  && cb.checked) cbUtford.checked = false;
        const utford    = cbUtford.checked ? 1 : 0;
        const ej_relevant = cbEjrel.checked ? 1 : 0;
        try {
          await api('PUT', `/projekt/${id}/checklista/${nr}`, { utford, ej_relevant });
          utford      ? ckSet.add(nr)    : ckSet.delete(nr);
          ej_relevant ? ejRelSet.add(nr) : ejRelSet.delete(nr);
          renderCk();
        } catch (e) {
          cb.checked = !cb.checked;
          toast(e.message, 'error');
        }
      });
    });
  }
  renderCk();

  document.getElementById('btnBack').addEventListener('click', () => navigate('projekt'));
  document.getElementById('btnEditProjekt').addEventListener('click', () => modalRedigeraProjekt(p));

  document.getElementById('fasTidslinje').querySelectorAll('.fas-steg').forEach(el => {
    el.addEventListener('click', async () => {
      const nyFas = el.dataset.fas;
      if (nyFas === aktuellFas) return;
      try {
        await api('POST', `/projekt/${id}/fas`, { fas: nyFas });
        toast(`Fas: ${nyFas}`, 'success');
        renderProjektDetail(app, id);
      } catch (e) { toast(e.message, 'error'); }
    });
  });

  document.getElementById('btnNyttTillstand').addEventListener('click', () =>
    modalTillstandForm(id, null, () => renderProjektDetail(app, id)));

  document.getElementById('tillstandKontainer').addEventListener('click', async e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const tid = btn.dataset.tid;
    if (btn.dataset.action === 'edit-till') {
      const t = tillstandLista.find(x => x.id == tid);
      modalTillstandForm(id, t, () => renderProjektDetail(app, id));
    } else if (btn.dataset.action === 'del-till') {
      const ok = await confirm('Ta bort tillstånd', 'Ta bort detta tillstånd?');
      if (!ok) return;
      try {
        await api('DELETE', `/projekt/${id}/tillstand/${tid}`);
        toast('Borttaget', 'success');
        renderProjektDetail(app, id);
      } catch (e) { toast(e.message, 'error'); }
    }
  });

  document.getElementById('btnNyAktivitet').addEventListener('click', () =>
    modalNyAktivitet(id, () => renderProjektDetail(app, id)));

  document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn[data-tab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab-pane').forEach(tp => tp.classList.remove('active'));
      const tabId = 'pdTab' + btn.dataset.tab.charAt(0).toUpperCase() + btn.dataset.tab.slice(1);
      document.getElementById(tabId).classList.add('active');
    });
  });

  const planeringPane = document.getElementById('pdTabPlanering');
  if (planeringPane) bindStatusAutospar(planeringPane, id);
}

// ----------------------------------------------------------------
// MODAL: TILLSTÅND
// ----------------------------------------------------------------
function modalTillstandForm(projektId, existing, onDone) {
  const d = existing || {};
  const statusOpts = ['Inväntas', 'Mottaget', 'Ej krävs'].map(s =>
    `<option ${(d.status || 'Inväntas') === s ? 'selected' : ''}>${s}</option>`).join('');
  Modal.open(
    existing ? 'Redigera tillstånd' : 'Nytt tillstånd',
    `<form id="tillstandForm">
      <div class="form-group">
        <label class="form-label">Tillståndsnamn <span class="req">*</span></label>
        <input name="namn" class="form-control" value="${escHtml(d.namn || '')}" required>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Status</label>
          <select name="status" class="form-control">${statusOpts}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Datum</label>
          <input type="date" name="datum" class="form-control" value="${d.datum || ''}">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Anteckning</label>
        <textarea name="anteckning" class="form-control" rows="2">${escHtml(d.anteckning || '')}</textarea>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaTillstand">${existing ? 'Spara' : 'Lägg till'}</button>
     <button class="btn btn-secondary" id="avbrytTillstand">Avbryt</button>`
  );
  document.getElementById('avbrytTillstand').addEventListener('click', Modal.close);
  document.getElementById('sparaTillstand').addEventListener('click', async () => {
    const f = document.getElementById('tillstandForm');
    if (!f.reportValidity()) return;
    const body = Object.fromEntries(new FormData(f).entries());
    try {
      if (existing) {
        await api('PUT', `/projekt/${projektId}/tillstand/${existing.id}`, body);
        toast('Tillstånd sparat', 'success');
      } else {
        await api('POST', `/projekt/${projektId}/tillstand`, body);
        toast('Tillstånd tillagt', 'success');
      }
      Modal.close();
      if (onDone) onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// MODAL: NY AKTIVITET (anteckning)
// ----------------------------------------------------------------
function modalNyAktivitet(projektId, onDone) {
  Modal.open(
    'Lägg till anteckning',
    `<form id="aktivitetForm">
      <div class="form-group">
        <label class="form-label">Anteckning <span class="req">*</span></label>
        <textarea name="beskrivning" class="form-control" rows="3" required></textarea>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaAktivitet">Spara</button>
     <button class="btn btn-secondary" id="avbrytAktivitet">Avbryt</button>`
  );
  document.getElementById('avbrytAktivitet').addEventListener('click', Modal.close);
  document.getElementById('sparaAktivitet').addEventListener('click', async () => {
    const f = document.getElementById('aktivitetForm');
    if (!f.reportValidity()) return;
    const body = Object.fromEntries(new FormData(f).entries());
    try {
      await api('POST', `/projekt/${projektId}/aktiviteter`, body);
      toast('Anteckning sparad', 'success');
      Modal.close();
      if (onDone) onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// MODAL: NYTT PROTOKOLL (wizard)
// ----------------------------------------------------------------
async function modalNyttProtokoll(projektId, onDone) {
  if (!S.mallar.length) {
    try { S.mallar = (await api('GET', '/mallar')).mallar || []; } catch {}
  }

  let steg = 1;
  let valdMall = null;
  let inputdata = {};
  let mallDef = null;

  function wizardHtml(body, footer) {
    return `
      <div class="wizard-steps">
        <div class="wizard-step ${steg === 1 ? 'active' : 'done'}">1. Välj mall</div>
        <div class="wizard-step ${steg === 2 ? 'active' : steg > 2 ? 'done' : ''}">2. Parametrar</div>
        <div class="wizard-step ${steg === 3 ? 'active' : ''}">3. Granska</div>
      </div>
      ${body}`;
  }

  async function visaSteg1() {
    steg = 1;
    const mallKort = S.mallar.map(m => `
      <div class="card mb-1" style="cursor:pointer;border:2px solid ${valdMall?.id===m.id?'var(--navy)':'var(--gray-200)'}; transition:border-color .15s;" data-mid="${m.id}">
        <div class="card-body">
          <strong>${escHtml(m.namn)}</strong>
          <p class="text-sm text-muted mt-1">${escHtml(m.beskrivning||'')}</p>
        </div>
      </div>`).join('');

    Modal.open('Nytt byggprotokoll',
      wizardHtml(`<div id="mallVal">${mallKort}</div>`),
      `<button class="btn btn-navy" id="wizNasta1">Nästa →</button>
       <button class="btn btn-secondary" id="wizAvbryt">Avbryt</button>`
    );

    document.getElementById('wizAvbryt').addEventListener('click', Modal.close);
    document.getElementById('mallVal').querySelectorAll('.card').forEach(c => {
      c.addEventListener('click', () => {
        valdMall = S.mallar.find(m => m.id == c.dataset.mid);
        document.getElementById('mallVal').querySelectorAll('.card').forEach(x =>
          x.style.borderColor = 'var(--gray-200)');
        c.style.borderColor = 'var(--navy)';
      });
    });
    document.getElementById('wizNasta1').addEventListener('click', async () => {
      if (!valdMall) { toast('Välj en mall', 'error'); return; }
      mallDef = (await api('GET', `/mallar/${valdMall.id}`)).mall;
      visaSteg2();
    });
  }

  async function visaSteg2() {
    steg = 2;
    const falt = mallDef.inputfalt || [];
    const faltHtml = await byggInputfalt(falt, inputdata);

    Modal.open('Nytt byggprotokoll',
      wizardHtml(`<form id="wizForm">${faltHtml}</form>`),
      `<button class="btn btn-navy" id="wizNasta2">Förhandsgranska →</button>
       <button class="btn btn-outline" id="wizTillbaka2">← Tillbaka</button>
       <button class="btn btn-secondary" id="wizAvbryt2">Avbryt</button>`
    );

    document.getElementById('wizTillbaka2').addEventListener('click', visaSteg1);
    document.getElementById('wizAvbryt2').addEventListener('click', Modal.close);
    document.getElementById('wizNasta2').addEventListener('click', async () => {
      const f = document.getElementById('wizForm');
      if (!f.reportValidity()) return;
      const fd = new FormData(f);
      inputdata = {};
      for (const [k, v] of fd.entries()) inputdata[k] = v;
      // checkboxes
      f.querySelectorAll('input[type=checkbox]').forEach(cb => {
        inputdata[cb.name] = cb.checked;
      });
      await visaSteg3();
    });
  }

  async function visaSteg3() {
    steg = 3;
    let rader = [];
    try {
      const res = await api('POST', '/byggprotokoll/berakna', { mall_id: valdMall.id, inputdata });
      rader = res.rader || [];
    } catch (e) { toast(e.message, 'error'); return; }

    const tabHtml = rader.length ? `
      <div class="table-wrap">
        <table>
          <thead><tr><th>Artikel</th><th>Kategori</th><th>Enhet</th><th class="right">Antal</th></tr></thead>
          <tbody>
            ${rader.map(r => `<tr>
              <td>${escHtml(r.artikelnamn)}</td>
              <td>${escHtml(r.kategori||'')}</td>
              <td>${escHtml(r.enhet)}</td>
              <td class="num">${num(r.antal)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="form-group mt-2">
        <label class="form-label">Anteckning (valfritt)</label>
        <textarea class="form-control" id="bpAnteckning" rows="2"></textarea>
      </div>` : `<p class="text-muted">Inga rader beräknades.</p>`;

    Modal.open('Nytt byggprotokoll',
      wizardHtml(tabHtml),
      `<button class="btn btn-success" id="wizSpara">✔ Skapa protokoll</button>
       <button class="btn btn-outline" id="wizTillbaka3">← Tillbaka</button>
       <button class="btn btn-secondary" id="wizAvbryt3">Avbryt</button>`
    );

    document.getElementById('wizTillbaka3').addEventListener('click', visaSteg2);
    document.getElementById('wizAvbryt3').addEventListener('click', Modal.close);
    document.getElementById('wizSpara').addEventListener('click', async () => {
      const ant = document.getElementById('bpAnteckning')?.value || '';
      try {
        await api('POST', '/byggprotokoll', {
          projekt_id: projektId,
          mall_id:    valdMall.id,
          inputdata,
          anteckningar: ant,
        });
        toast('Protokoll skapat', 'success');
        Modal.close();
        // refresh protokoll list
        const lista = (await api('GET', `/byggprotokoll?projekt_id=${projektId}`)).byggprotokoll || [];
        // re-render detail
        renderProjektDetail(document.getElementById('app'), projektId);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  visaSteg1();
}

async function byggInputfalt(falt, existing = {}) {
  let html = '';
  for (const f of falt) {
    const val = existing[f.faltnamn] ?? '';
    const label = `<label class="form-label">${escHtml(f.etikett)}</label>`;
    const hint  = f.hjalp ? `<div class="form-hint">${escHtml(f.hjalp)}</div>` : '';

    if (f.typ === 'number') {
      html += `<div class="form-group">${label}<input type="number" name="${f.faltnamn}" class="form-control" value="${val}" min="0" step="any">${hint}</div>`;
    } else if (f.typ === 'checkbox') {
      const chk = val === true || val === 'true' || val === '1' ? 'checked' : '';
      html += `<div class="form-group"><label class="form-check"><input type="checkbox" name="${f.faltnamn}" ${chk}> ${escHtml(f.etikett)}</label>${hint}</div>`;
    } else if (f.typ === 'artikel_select') {
      // Fetch articles by category (alternativ-JSON has key kategori_namn)
      let alts = [];
      try { alts = JSON.parse(f.alternativ || '{}'); } catch {}
      const kategori = alts.kategori_namn || alts.kategori || '';
      let artiklar = [];
      try {
        artiklar = (await api('GET', `/artiklar?kategori=${encodeURIComponent(kategori)}`)).artiklar || [];
      } catch {}
      if (alts.filter) {
        const terms = alts.filter.toLowerCase().split('|');
        artiklar = artiklar.filter(a => terms.some(t => a.artikelnamn.toLowerCase().includes(t)));
      }
      const opts = artiklar.map(a =>
        `<option value="${a.id}" ${val == a.id ? 'selected' : ''}>${escHtml(a.artikelnamn)}</option>`
      ).join('');
      html += `<div class="form-group">${label}<select name="${f.faltnamn}" class="form-control"><option value="">– välj –</option>${opts}</select>${hint}</div>`;
    } else if (f.typ === 'select') {
      let alts = [];
      try { alts = JSON.parse(f.alternativ || '[]'); } catch {}
      const opts = alts.map(a => `<option ${val===a?'selected':''}>${escHtml(a)}</option>`).join('');
      html += `<div class="form-group">${label}<select name="${f.faltnamn}" class="form-control">${opts}</select>${hint}</div>`;
    } else {
      html += `<div class="form-group">${label}<input type="text" name="${f.faltnamn}" class="form-control" value="${escHtml(val)}">${hint}</div>`;
    }
  }
  return html;
}

// ----------------------------------------------------------------
// MODAL: VISA/REDIGERA PROTOKOLL
// ----------------------------------------------------------------
async function modalVisaProtokoll(bpid, projektId, protokollLista, onDone) {
  // Ladda kategorier i förväg (behövs för inline-formuläret)
  if (!S.kategorier.length) {
    try { S.kategorier = (await api('GET', '/kategorier')).kategorier || []; } catch {}
  }

  let bp;
  try { bp = (await api('GET', `/byggprotokoll/${bpid}`)).byggprotokoll; }
  catch (e) { toast(e.message, 'error'); return; }

  const statusOpts = ['Utkast', 'Granskat', 'Godkänt'].map(s =>
    `<option ${bp.status === s ? 'selected' : ''}>${s}</option>`).join('');

  const tabRader = (bp.rader || []).map((r, i) => `
    <tr class="${r.manuell ? 'rad-manuell' : ''}" data-idx="${i}">
      <td>${escHtml(r.artikelnamn)}</td>
      <td>${escHtml(r.kategori||'')}</td>
      <td>${escHtml(r.enhet)}</td>
      <td class="num"><input type="number" class="form-control" style="width:80px;text-align:right" name="antal_${i}" value="${r.antal}" min="0" step="any"></td>
      <td><button class="btn btn-sm btn-danger" data-del="${i}">✕</button></td>
    </tr>`).join('');

  // Bygg egenkontroll HTML
  const egkLista = bp.egenkontroll || [];
  const egkUtforda = egkLista.filter(e => e.utford).length;
  const egkTotal   = egkLista.length;
  const egkHtml = egkTotal ? `
    <div class="egk-section">
      <div class="egk-section-title">
        Egenkontroll
        <span class="egk-progress">${egkUtforda}/${egkTotal} utförda</span>
      </div>
      <ul class="egk-list" id="egkList">
        ${egkLista.map((e, i) => `
          <li class="egk-item ${e.utford ? 'utford' : ''} ${e.ej_relevant ? 'ej-rel' : ''}"
              data-egk-id="${e.id}" data-idx="${i}">
            <span class="egk-nr">${i + 1}.</span>
            <span class="egk-punkt">${escHtml(e.punkt)}</span>
            <div class="egk-checkboxes">
              <label class="egk-check-label">
                <input type="checkbox" class="egk-utford" ${e.utford ? 'checked' : ''}> Utförd
              </label>
              <label class="egk-check-label">
                <input type="checkbox" class="egk-ej-rel" ${e.ej_relevant ? 'checked' : ''}> Ej relevant
              </label>
            </div>
          </li>`).join('')}
      </ul>
    </div>` : '';

  Modal.open('Byggprotokoll',
    `<div class="flex gap-2 items-center mb-2">
       <strong>${escHtml(bp.mall_namn)}</strong>
       <select id="bpStatus" class="form-control" style="width:140px">${statusOpts}</select>
       <span class="ml-auto text-sm text-muted">Skapad: ${(bp.skapad||'').slice(0,16)}</span>
     </div>
     <div class="table-wrap">
       <table id="radTabell">
         <thead><tr><th>Artikel</th><th>Kategori</th><th>Enhet</th><th class="right">Antal</th><th></th></tr></thead>
         <tbody id="radBody">${tabRader}</tbody>
       </table>
     </div>
     <div class="mt-2 flex gap-1 items-center">
       <button class="btn btn-outline btn-sm" id="btnLaggTillRad">+ Lägg till rad</button>
     </div>
     <div id="inlineRadForm" style="display:none;background:rgba(124,58,237,.06);border:1px solid rgba(124,58,237,.22);border-radius:6px;padding:12px;margin-top:8px">
       <div class="form-row cols-2" style="margin-bottom:6px">
         <div class="form-group" style="margin:0">
           <label class="form-label">Kategori</label>
           <select id="inlineKat" class="form-control">
             <option value="">– alla –</option>
             ${S.kategorier.map(k => `<option value="${k.id}">${escHtml(k.namn)}</option>`).join('')}
           </select>
         </div>
         <div class="form-group" style="margin:0">
           <label class="form-label">Artikel</label>
           <select id="inlineArt" class="form-control"><option value="">Laddar...</option></select>
         </div>
       </div>
       <div class="form-row cols-2" style="margin-bottom:8px">
         <div class="form-group" style="margin:0">
           <label class="form-label">Antal</label>
           <input type="number" id="inlineAntal" class="form-control" value="1" min="0" step="any">
         </div>
         <div class="form-group" style="margin:0">
           <label class="form-label">Anteckning (valfri)</label>
           <input type="text" id="inlineAnt" class="form-control" placeholder="">
         </div>
       </div>
       <div class="flex gap-1">
         <button class="btn btn-success btn-sm" id="inlineLeggTill">✓ Lägg till</button>
         <button class="btn btn-outline btn-sm" id="inlineStang">Stäng</button>
       </div>
     </div>
     ${egkHtml}
     <div class="form-group mt-2">
       <label class="form-label">Anteckning</label>
       <textarea class="form-control" id="bpAnt" rows="2">${escHtml(bp.anteckningar||'')}</textarea>
     </div>`,
    `<button class="btn btn-success" id="sparaBP">Spara</button>
     <a class="btn btn-secondary" href="/api/byggprotokoll/${bpid}/pdf" target="_blank">⬇ PDF</a>
     <button class="btn btn-outline" id="avbrytBP">Stäng</button>`
  );

  // local rader copy
  let rader = JSON.parse(JSON.stringify(bp.rader || []));

  function syncAntal() {
    rader.forEach((r, i) => {
      const inp = document.querySelector(`input[name="antal_${i}"]`);
      if (inp) r.antal = parseFloat(inp.value) || 0;
    });
  }

  document.getElementById('radBody').addEventListener('input', syncAntal);

  document.getElementById('radBody').addEventListener('click', e => {
    const btn = e.target.closest('button[data-del]');
    if (!btn) return;
    const idx = parseInt(btn.dataset.del);
    rader.splice(idx, 1);
    renderRadBody();
  });

  function renderRadBody() {
    document.getElementById('radBody').innerHTML = rader.map((r, i) => `
      <tr class="${r.manuell ? 'rad-manuell' : ''}">
        <td>${escHtml(r.artikelnamn)}</td><td>${escHtml(r.kategori||'')}</td><td>${escHtml(r.enhet)}</td>
        <td class="num"><input type="number" class="form-control" style="width:80px;text-align:right" name="antal_${i}" value="${r.antal}" min="0" step="any"></td>
        <td><button class="btn btn-sm btn-danger" data-del="${i}">✕</button></td>
      </tr>`).join('');
  }

  // Inline "Lägg till rad"-formulär
  async function laddaInlineArtiklar() {
    const katId = document.getElementById('inlineKat').value;
    const sel = document.getElementById('inlineArt');
    sel.innerHTML = '<option value="">Laddar...</option>';
    try {
      const url = katId ? `/artiklar?kategori_id=${katId}` : '/artiklar';
      const arts = (await api('GET', url)).artiklar || [];
      sel.innerHTML = '<option value="">– välj artikel –</option>' +
        arts.map(a => `<option value="${a.id}" data-enhet="${escHtml(a.enhet||'')}" data-kat="${escHtml(a.kategori_namn||'')}">
          ${escHtml(a.artikelnamn)}</option>`).join('');
    } catch { sel.innerHTML = '<option value="">Fel vid laddning</option>'; }
  }

  document.getElementById('btnLaggTillRad').addEventListener('click', async () => {
    const form = document.getElementById('inlineRadForm');
    const visible = form.style.display !== 'none';
    form.style.display = visible ? 'none' : '';
    if (!visible) await laddaInlineArtiklar();
  });

  document.getElementById('inlineStang').addEventListener('click', () => {
    document.getElementById('inlineRadForm').style.display = 'none';
  });

  document.getElementById('inlineKat').addEventListener('change', laddaInlineArtiklar);

  document.getElementById('inlineLeggTill').addEventListener('click', () => {
    const artSel = document.getElementById('inlineArt');
    const artId  = parseInt(artSel.value);
    if (!artId) { toast('Välj en artikel', 'error'); return; }
    const opt   = artSel.options[artSel.selectedIndex];
    const antal = parseFloat(document.getElementById('inlineAntal').value) || 1;
    const ant   = document.getElementById('inlineAnt').value.trim();
    rader.push({
      artikel_id:      artId,
      artikelnamn:     opt.textContent.trim(),
      kategori:        opt.dataset.kat  || '',
      enhet:           opt.dataset.enhet || '',
      antal,
      a_pris:          null,
      leverantor_id:   null,
      leverantor_namn: null,
      artikelnummer:   null,
      anteckning:      ant,
      manuell:         1,
    });
    renderRadBody();
    document.getElementById('inlineAntal').value = '1';
    document.getElementById('inlineAnt').value   = '';
    toast('Rad tillagd ✓', 'success');
  });

  // Egenkontroll interaktivitet
  const egkListEl = document.getElementById('egkList');
  if (egkListEl) {
    egkListEl.addEventListener('change', e => {
      const item = e.target.closest('.egk-item');
      if (!item) return;
      const cbUtford = item.querySelector('.egk-utford');
      const cbEjRel  = item.querySelector('.egk-ej-rel');
      if (e.target === cbUtford && cbUtford.checked) {
        cbEjRel.checked = false;
        item.classList.add('utford'); item.classList.remove('ej-rel');
      } else if (e.target === cbEjRel && cbEjRel.checked) {
        cbUtford.checked = false;
        item.classList.add('ej-rel'); item.classList.remove('utford');
      } else {
        item.classList.remove('utford', 'ej-rel');
      }
      // Update progress
      const allItems = egkListEl.querySelectorAll('.egk-item');
      const done = [...allItems].filter(i => i.querySelector('.egk-utford').checked).length;
      const tot  = allItems.length;
      const progEl = document.querySelector('.egk-progress');
      if (progEl) progEl.textContent = `${done}/${tot} utförda`;
    });
  }

  document.getElementById('avbrytBP').addEventListener('click', Modal.close);
  document.getElementById('sparaBP').addEventListener('click', async () => {
    syncAntal();
    // Samla egenkontroll-data
    const egkData = [];
    document.querySelectorAll('.egk-item[data-egk-id]').forEach(item => {
      egkData.push({
        id:          parseInt(item.dataset.egkId),
        utford:      item.querySelector('.egk-utford').checked ? 1 : 0,
        ej_relevant: item.querySelector('.egk-ej-rel').checked ? 1 : 0,
      });
    });
    try {
      await api('PUT', `/byggprotokoll/${bpid}`, {
        status:        document.getElementById('bpStatus').value,
        anteckningar:  document.getElementById('bpAnt').value,
        rader,
        egenkontroll:  egkData,
      });
      toast('Protokoll sparat', 'success');
      Modal.close();
      onDone && onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// MODAL: LÄGG TILL MATERIALRAD MANUELLT
// ----------------------------------------------------------------
async function modalLaggTillRad(rader, onDone) {
  if (!S.kategorier.length) {
    try { S.kategorier = (await api('GET', '/kategorier')).kategorier || []; } catch {}
  }
  const katOpts = S.kategorier.map(k => `<option value="${k.id}">${escHtml(k.namn)}</option>`).join('');

  // We'll open a second modal by reusing the same modal (swap content)
  Modal.open('Lägg till materialrad',
    `<form id="radForm">
      <div class="form-group">
        <label class="form-label">Kategori</label>
        <select id="radKat" class="form-control"><option value="">– alla –</option>${katOpts}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Artikel <span class="req">*</span></label>
        <select id="radArtSelect" name="artikel_id" class="form-control" required>
          <option value="">– laddar –</option>
        </select>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Antal <span class="req">*</span></label>
          <input type="number" name="antal" class="form-control" min="0.001" step="any" required>
        </div>
        <div class="form-group">
          <label class="form-label">Anteckning</label>
          <input type="text" name="anteckning" class="form-control">
        </div>
      </div>
    </form>`,
    `<button class="btn btn-success" id="laggTillRadBtn">Lägg till</button>
     <button class="btn btn-secondary" id="avbrytRadBtn">Avbryt</button>`
  );

  async function laddaArtiklar(katId = '') {
    const url = katId ? `/artiklar?kategori_id=${katId}` : '/artiklar';
    try {
      const data = await api('GET', url);
      const arts = data.artiklar || [];
      document.getElementById('radArtSelect').innerHTML =
        `<option value="">– välj artikel –</option>` +
        arts.map(a => `<option value="${a.id}" data-enhet="${a.enhet}" data-kat="${escHtml(a.kategori_namn||'')}">${escHtml(a.artikelnamn)}</option>`).join('');
    } catch {}
  }
  laddaArtiklar();

  document.getElementById('radKat').addEventListener('change', e => laddaArtiklar(e.target.value));
  document.getElementById('avbrytRadBtn').addEventListener('click', Modal.close);
  document.getElementById('laggTillRadBtn').addEventListener('click', async () => {
    const f = document.getElementById('radForm');
    if (!f.reportValidity()) return;
    const artSel = document.getElementById('radArtSelect');
    const opt    = artSel.options[artSel.selectedIndex];
    const artId  = parseInt(artSel.value);
    if (!artId) { toast('Välj en artikel', 'error'); return; }
    const antal  = parseFloat(f.querySelector('[name=antal]').value);
    const ant    = f.querySelector('[name=anteckning]').value;

    // fetch article details for price
    let artData = {};
    try { artData = (await api('GET', `/artiklar/${artId}`)).artikel || {}; } catch {}

    rader.push({
      artikel_id:      artId,
      artikelnamn:     opt.textContent,
      kategori:        opt.dataset.kat || '',
      enhet:           opt.dataset.enhet || '',
      antal,
      a_pris:          artData.a_pris || null,
      leverantor_id:   artData.leverantor_id || null,
      leverantor_namn: artData.leverantor_namn || null,
      artikelnummer:   artData.artikelnummer || null,
      anteckning:      ant,
      manuell:         1,
    });
    toast('Rad tillagd', 'success');
    Modal.close();
    onDone && onDone();
  });
}

// ----------------------------------------------------------------
// VIEW: KONSTRUKTIONER
// ----------------------------------------------------------------
async function renderKonstruktioner(app) {
  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Konstruktioner</h1>
    </div>
    <div class="card" style="margin-bottom:1rem;padding:1rem 1.25rem;">
      <div class="flex gap-2 items-center flex-wrap">
        <label class="form-label" style="margin:0;white-space:nowrap;font-weight:600;">Beredare:</label>
        <select class="form-control" id="filtKonstrBeredare" style="max-width:200px;">
          <option value="">Alla beredare</option>
        </select>
        <label class="form-label" style="margin:0;white-space:nowrap;font-weight:600;">Välj projekt:</label>
        <select class="form-control" id="projektValjare" style="max-width:320px;">
          <option value="">– välj projekt –</option>
        </select>
        <button class="btn btn-navy btn-sm" id="btnNyttProjektKonstr" style="white-space:nowrap;">+ Nytt projekt</button>
        <button class="btn btn-danger btn-sm" id="btnRaderaProjektKonstr" style="white-space:nowrap;display:none;">🗑 Ta bort projekt</button>
      </div>
    </div>
    <div id="konstrInnehall"></div>`;

  let allaProjekt = [];

  async function laddaProjektDropdown(valjId) {
    try {
      allaProjekt = (await api('GET', '/projekt')).projekt || [];
    } catch(e) { toast(e.message, 'error'); }
    byggProjektOptions(valjId);
  }

  function byggProjektOptions(valjId) {
    const sel = document.getElementById('projektValjare');
    const ber = document.getElementById('filtKonstrBeredare')?.value || '';
    // Behåll bara default-option, rensa resten
    while (sel.options.length > 1) sel.remove(1);
    allaProjekt
      .filter(p => !ber || p.beredare === ber)
      .forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.projektnummer} – ${p.projektnamn}`;
        sel.appendChild(opt);
      });
    if (valjId) sel.value = valjId;
  }

  // Fyll beredare-filtret
  if (!S.beredare.length) {
    try { S.beredare = (await api('GET', '/beredare')).beredare || []; } catch {}
  }
  const berSel = document.getElementById('filtKonstrBeredare');
  S.beredare.forEach(b => { berSel.innerHTML += `<option>${escHtml(b.namn)}</option>`; });
  if (S.minBeredare) berSel.value = S.minBeredare;

  await laddaProjektDropdown(S.valtProjektKonstr);

  const sel = document.getElementById('projektValjare');

  berSel.addEventListener('change', () => {
    byggProjektOptions();
    S.valtProjektKonstr = sel.value || null;
    uppdateraRaderaKnapp();
    renderKonstrKontainer(sel.value);
  });

  function uppdateraRaderaKnapp() {
    document.getElementById('btnRaderaProjektKonstr').style.display =
      sel.value ? '' : 'none';
  }

  sel.addEventListener('change', () => {
    S.valtProjektKonstr = sel.value;
    uppdateraRaderaKnapp();
    renderKonstrKontainer(sel.value);
  });

  uppdateraRaderaKnapp();

  document.getElementById('btnRaderaProjektKonstr').addEventListener('click', async () => {
    const valt = allaProjekt.find(p => String(p.id) === sel.value);
    if (!valt) return;
    const ok = await confirm('Ta bort projekt',
      `Ta bort "${valt.projektnamn}"? Alla byggprotokoll kopplade till projektet tas också bort.`);
    if (!ok) return;
    try {
      await api('DELETE', `/projekt/${valt.id}`);
      toast('Projekt borttaget', 'success');
      S.valtProjektKonstr = null;
      await laddaProjektDropdown(null);
      uppdateraRaderaKnapp();
      renderKonstrKontainer('');
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('btnNyttProjektKonstr').addEventListener('click', () => {
    modalProjektFormEnkel(async (res) => {
      const nyprojekt = res.projekt;
      if (nyprojekt) {
        S.valtProjektKonstr = String(nyprojekt.id);
        await laddaProjektDropdown(S.valtProjektKonstr);
        renderKonstrKontainer(S.valtProjektKonstr);
      }
    });
  });

  renderKonstrKontainer(sel.value);

  async function renderKonstrKontainer(projektId) {
    const div = document.getElementById('konstrInnehall');
    if (!projektId) {
      div.innerHTML = `<div class="card text-center muted" style="padding:2rem;">Välj ett projekt ovan för att se och skapa konstruktioner.</div>`;
      return;
    }

    div.innerHTML = `
      <div class="page-header" style="margin-top:0;">
        <div></div>
        <div class="flex gap-2">
          <a class="btn btn-secondary" href="/api/konstruktioner/byggprotokoll/pdf?projekt_id=${projektId}" target="_blank">⬇ Byggprotokoll PDF</a>
          <a class="btn btn-secondary" href="/api/konstruktioner/materiallista/pdf?projekt_id=${projektId}" target="_blank">⬇ Materiallista PDF</a>
          <a class="btn btn-secondary" href="/api/konstruktioner/materiallista/excel?projekt_id=${projektId}" target="_blank">⬇ Materiallista Excel</a>
          <button class="btn btn-secondary" id="btnNyKonstr">+ Ny konstruktion</button>
        </div>
      </div>
      <div class="filter-bar">
        <input type="search" class="form-control" id="sokKonstr" placeholder="Sök namn, byggnr, fri ID…">
        <select class="form-control" id="filtKonstrTyp">
          <option value="">Alla typer</option>
          <option>Kabelskåp</option>
          <option>Kabelförläggning</option>
          <option>Nätstation</option>
          <option>Övrigt</option>
        </select>
        <select class="form-control" id="filtKonstrStatus">
          <option value="">Alla statusar</option>
          <option>Pågående</option>
          <option>Klar</option>
          <option>Pausad</option>
          <option>Avbruten</option>
        </select>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>Typ</th><th>Byggnr</th><th>Namn</th><th>Fri ID</th><th>Status</th><th>Skapad</th><th>Åtgärder</th>
            </tr></thead>
            <tbody id="konstrBody"></tbody>
          </table>
        </div>
      </div>`;

    let konstruktioner = [];

    async function ladda() {
      const sok    = document.getElementById('sokKonstr').value.trim();
      const typ    = document.getElementById('filtKonstrTyp').value;
      const status = document.getElementById('filtKonstrStatus').value;
      let url = `/konstruktioner?projekt_id=${projektId}`;
      if (sok)    url += `&sok=${encodeURIComponent(sok)}`;
      if (typ)    url += `&typ=${encodeURIComponent(typ)}`;
      if (status) url += `&status=${encodeURIComponent(status)}`;
      try {
        konstruktioner = (await api('GET', url)).konstruktioner || [];
      } catch (e) { toast(e.message, 'error'); return; }
      renderKonstrRader();
    }

    function renderKonstrRader() {
      const tbody = document.getElementById('konstrBody');
      if (!tbody) return;
      if (!konstruktioner.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="muted text-center">Inga konstruktioner hittades</td></tr>`;
        return;
      }
      tbody.innerHTML = konstruktioner.map(k => `
        <tr style="cursor:pointer">
          <td>${badgeTyp(k.typ)}</td>
          <td>${escHtml(k.byggnr || '–')}</td>
          <td><strong>${escHtml(k.namn)}</strong></td>
          <td>${escHtml(k.fri_id || '–')}</td>
          <td>${badge(k.status)}</td>
          <td>${(k.skapad || '').slice(0, 10)}</td>
          <td class="flex gap-1">
            <button class="btn btn-sm btn-navy" data-id="${k.id}" data-action="oppna">Öppna</button>
            <button class="btn btn-sm btn-outline" data-id="${k.id}" data-action="redigera">Redigera</button>
            <button class="btn btn-sm btn-danger" data-id="${k.id}" data-action="radera">Ta bort</button>
          </td>
        </tr>`).join('');

      tbody.querySelectorAll('button[data-action]').forEach(btn => {
        btn.addEventListener('click', async e => {
          e.stopPropagation();
          const id = btn.dataset.id;
          const k  = konstruktioner.find(x => x.id == id);
          if (btn.dataset.action === 'oppna') {
            await modalVisaKonstruktion(id, ladda);
          } else if (btn.dataset.action === 'redigera') {
            await modalKonstruktionForm(k, ladda, projektId);
          } else if (btn.dataset.action === 'radera') {
            const ok = await confirm('Ta bort konstruktion', `Ta bort "${k.namn}"?`);
            if (!ok) return;
            try {
              await api('DELETE', `/konstruktioner/${id}`);
              toast('Konstruktion borttagen', 'success');
              await ladda();
            } catch (e) { toast(e.message, 'error'); }
          }
        });
      });

      tbody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', async e => {
          if (e.target.closest('button')) return;
          const btn = row.querySelector('button[data-action="oppna"]');
          if (btn) await modalVisaKonstruktion(btn.dataset.id, ladda);
        });
      });
    }

    document.getElementById('sokKonstr').addEventListener('input', ladda);
    document.getElementById('filtKonstrTyp').addEventListener('change', ladda);
    document.getElementById('filtKonstrStatus').addEventListener('change', ladda);
    document.getElementById('btnNyKonstr').addEventListener('click', () => modalKonstruktionForm(null, ladda, projektId));

    await ladda();
  }
}

// ----------------------------------------------------------------
// MODAL: KONSTRUKTION FORMULÄR (skapa/redigera)
// ----------------------------------------------------------------
async function modalKonstruktionForm(existing, onDone, projektId) {
  const typer = ['Kabelskåp', 'Kabelförläggning', 'Nätstation', 'Övrigt'];
  const statusar = ['Pågående', 'Klar', 'Pausad', 'Avbruten'];
  const d = existing || {};

  const typOpts = typer.map(t =>
    `<option ${d.typ === t ? 'selected' : ''}>${escHtml(t)}</option>`).join('');
  const statusOpts = statusar.map(s =>
    `<option ${(d.status || 'Pågående') === s ? 'selected' : ''}>${escHtml(s)}</option>`).join('');

  Modal.open(
    existing ? 'Redigera konstruktion' : 'Ny konstruktion',
    `<form id="konstrForm">
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Typ <span class="req">*</span></label>
          <select name="typ" class="form-control" required ${existing ? 'disabled' : ''}>
            <option value="">– välj –</option>${typOpts}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Status</label>
          <select name="status" class="form-control">${statusOpts}</select>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Namn <span class="req">*</span></label>
        <input name="namn" class="form-control" value="${escHtml(d.namn || '')}" required placeholder="T.ex. KS-42 Storgatan 12">
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Byggnr</label>
          <input name="byggnr" class="form-control" value="${escHtml(d.byggnr || '')}" placeholder="T.ex. B-42">
        </div>
        <div class="form-group">
          <label class="form-label">Fri ID</label>
          <input name="fri_id" class="form-control" value="${escHtml(d.fri_id || '')}" placeholder="Valfritt fält">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Anmärkning</label>
        <textarea name="anmarkning" class="form-control" rows="2">${escHtml(d.anmarkning || '')}</textarea>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaKonstr">${existing ? 'Spara' : 'Skapa'}</button>
     <button class="btn btn-secondary" id="avbrytKonstr">Avbryt</button>`
  );

  document.getElementById('avbrytKonstr').addEventListener('click', Modal.close);
  document.getElementById('sparaKonstr').addEventListener('click', async () => {
    const f = document.getElementById('konstrForm');
    if (!f.reportValidity()) return;
    const fd   = new FormData(f);
    const body = Object.fromEntries(fd.entries());
    // Om typ är disabled används inte värdet i FormData
    if (existing) body.typ = existing.typ;
    try {
      if (existing) {
        await api('PUT', `/konstruktioner/${existing.id}`, body);
        toast('Konstruktion sparad', 'success');
      } else {
        await api('POST', '/konstruktioner', {...body, projekt_id: projektId});
        toast('Konstruktion skapad', 'success');
      }
      Modal.close();
      onDone && await onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// MODAL: VISA KONSTRUKTION (komplett vy med rader + egenkontroll)
// ----------------------------------------------------------------
async function modalVisaKonstruktion(kid, onDone) {
  // Ladda kategorier i förväg
  if (!S.kategorier.length) {
    try { S.kategorier = (await api('GET', '/kategorier')).kategorier || []; } catch {}
  }

  let k;
  try { k = (await api('GET', `/konstruktioner/${kid}`)).konstruktion; }
  catch (e) { toast(e.message, 'error'); return; }

  const statusar    = ['Pågående', 'Klar', 'Pausad', 'Avbruten'];
  const statusOpts  = statusar.map(s => `<option ${k.status === s ? 'selected' : ''}>${s}</option>`).join('');
  const erKabelskap = k.typ === 'Kabelskåp';

  function beraknaModuler(rader) {
    const kapacitet = rader.reduce((s, r) => s + ((r.moduler || 0) > 0 ? (r.moduler || 0) * (r.antal || 1) : 0), 0);
    const anvant    = rader.reduce((s, r) => s + ((r.moduler || 0) < 0 ? Math.abs(r.moduler || 0) * (r.antal || 1) : 0), 0);
    const kvar      = kapacitet - anvant;
    return { kapacitet, anvant, kvar };
  }

  function modulIndikatorHtml(rader) {
    if (!erKabelskap) return '';
    const { kapacitet, anvant, kvar } = beraknaModuler(rader);
    const pct = kapacitet > 0 ? Math.min(100, Math.round(anvant / kapacitet * 100)) : 0;
    const färg = kvar < 0 ? '#ef4444' : kvar <= 2 ? '#f59e0b' : '#7c3aed';
    return `
      <div style="background:rgba(124,58,237,.06);border:1px solid rgba(124,58,237,.22);border-radius:6px;padding:10px 14px;margin-bottom:10px">
        <div style="font-weight:600;color:#7c3aed;margin-bottom:6px;font-size:13px">Moduler – ${escHtml(k.namn)}</div>
        <div style="display:flex;gap:16px;font-size:12px;margin-bottom:6px">
          <span>Kapacitet: <strong>${kapacitet}</strong></span>
          <span>Använt: <strong>${anvant}</strong></span>
          <span style="color:${färg}">Kvar: <strong>${kvar}</strong></span>
        </div>
        <div style="background:rgba(124,58,237,.12);border-radius:4px;height:10px;overflow:hidden">
          <div style="width:${pct}%;height:100%;background:${färg};transition:width .3s"></div>
        </div>
      </div>`;
  }

  function radTabellHtml(rader) {
    if (!rader.length) return '<p class="text-muted text-sm">Inga materialrader ännu.</p>';
    return `
      <div class="table-wrap">
        <table id="konstrRadTabell">
          <thead><tr>
            <th>Artikel</th><th>Enhet</th><th class="right">Antal</th>
            ${erKabelskap ? '<th class="right">Moduler</th>' : ''}
            <th>Anteckning</th><th></th>
          </tr></thead>
          <tbody id="konstrRadBody">
            ${rader.map((r, i) => `
              <tr>
                <td>${escHtml(r.artikelnamn)}</td>
                <td>${escHtml(r.enhet)}</td>
                <td class="num"><input type="number" class="form-control" style="width:80px;text-align:right"
                    name="antal_${i}" value="${r.antal}" min="0" step="any"></td>
                ${erKabelskap ? `<td class="num" style="color:${(r.moduler || 0) > 0 ? '#7c3aed' : (r.moduler || 0) < 0 ? '#dc2626' : '#666'}">${r.moduler || 0}</td>` : ''}
                <td><input type="text" class="form-control" style="width:120px" name="ant_${i}" value="${escHtml(r.anteckning || '')}"></td>
                <td><button class="btn btn-sm btn-danger" data-del="${i}">✕</button></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function egkHtml(egkLista) {
    if (!egkLista.length) return '';
    const utforda = egkLista.filter(e => e.utford).length;
    return `
      <div class="egk-section">
        <div class="egk-section-title">
          Egenkontroll
          <span class="egk-progress">${utforda}/${egkLista.length} utförda</span>
        </div>
        <ul class="egk-list" id="konstrEgkList">
          ${egkLista.map((e, i) => `
            <li class="egk-item ${e.utford ? 'utford' : ''} ${e.ej_relevant ? 'ej-rel' : ''}"
                data-egk-id="${e.id}" data-idx="${i}">
              <span class="egk-nr">${i + 1}.</span>
              <span class="egk-punkt">${escHtml(e.punkt)}</span>
              <div class="egk-checkboxes">
                <label class="egk-check-label">
                  <input type="checkbox" class="egk-utford" ${e.utford ? 'checked' : ''}> Utförd
                </label>
                <label class="egk-check-label">
                  <input type="checkbox" class="egk-ej-rel" ${e.ej_relevant ? 'checked' : ''}> Ej relevant
                </label>
              </div>
            </li>`).join('')}
        </ul>
      </div>`;
  }

  // Lokal kopia av rader
  let rader = JSON.parse(JSON.stringify(k.rader || []));

  // ── Autospar ──────────────────────────────────────────────────
  let _saveTimer = null;

  function samlaPayload() {
    syncRader();
    const egkData = [];
    document.querySelectorAll('#konstrEgkList .egk-item[data-egk-id]').forEach(item => {
      egkData.push({
        id:          parseInt(item.dataset.egkId),
        utford:      item.querySelector('.egk-utford').checked ? 1 : 0,
        ej_relevant: item.querySelector('.egk-ej-rel').checked ? 1 : 0,
      });
    });
    const statusEl = document.getElementById('konstrStatus');
    const antEl    = document.getElementById('konstrAnt');
    return {
      status:       statusEl ? statusEl.value : k.status,
      anmarkning:   antEl ? antEl.value : k.anmarkning,
      rader,
      egenkontroll: egkData,
    };
  }

  function visaSparStatus(text, cls) {
    const el = document.getElementById('konstrSparStatus');
    if (el) el.className = 'text-sm ' + (cls || 'text-muted');
    if (el) el.textContent = text;
  }

  async function saveNow() {
    if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
    try {
      visaSparStatus('Sparar…', 'text-muted');
      await api('PUT', `/konstruktioner/${kid}`, samlaPayload());
      visaSparStatus('Sparat ✓', 'text-success');
    } catch (e) {
      visaSparStatus('Kunde inte spara: ' + e.message, 'text-danger');
    }
  }

  function scheduleSave() {
    visaSparStatus('Ändrat…', 'text-muted');
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(saveNow, 700);
  }

  function byggModalBody() {
    return `
      <div class="flex gap-2 items-center mb-2 flex-wrap">
        ${badgeTyp(k.typ)}
        ${k.byggnr ? `<span class="text-muted text-sm">Byggnr: <strong>${escHtml(k.byggnr)}</strong></span>` : ''}
        ${k.fri_id ? `<span class="text-muted text-sm">ID: <strong>${escHtml(k.fri_id)}</strong></span>` : ''}
        <select id="konstrStatus" class="form-control" style="width:140px">${statusOpts}</select>
        <span class="ml-auto text-sm text-muted">Skapad: ${(k.skapad || '').slice(0, 10)}</span>
      </div>
      ${k.anmarkning ? `<p class="text-sm text-muted mb-2" style="background:rgba(124,58,237,.06);border:1px solid rgba(124,58,237,.12);padding:6px 10px;border-radius:4px">${escHtml(k.anmarkning)}</p>` : ''}
      <div id="konstrModulIndikator">${modulIndikatorHtml(rader)}</div>
      <div id="konstrRadWrapper">${radTabellHtml(rader)}</div>
      <div class="mt-2 flex gap-1 items-center">
        <button class="btn btn-outline btn-sm" id="btnKonstrLaggTillRad">+ Lägg till rad</button>
      </div>
      <div id="konstrInlineForm" style="display:none;background:rgba(124,58,237,.06);border:1px solid rgba(124,58,237,.22);border-radius:6px;padding:12px;margin-top:8px">
        <div class="form-row cols-2" style="margin-bottom:6px">
          <div class="form-group" style="margin:0">
            <label class="form-label">Kategori</label>
            <select id="konstrInlineKat" class="form-control">
              <option value="">– alla –</option>
              ${S.kategorier.map(k2 => `<option value="${k2.id}">${escHtml(k2.namn)}</option>`).join('')}
            </select>
          </div>
          <div class="form-group" style="margin:0">
            <label class="form-label">Sök artikel</label>
            <input type="search" id="konstrInlineSok" class="form-control" placeholder="🔍 Namn eller E-nummer…" autocomplete="off">
          </div>
        </div>
        <div class="form-group" style="margin:0 0 6px">
          <label class="form-label">Artikel</label>
          <select id="konstrInlineArt" class="form-control" size="8" style="height:auto"><option value="">Laddar...</option></select>
        </div>
        <div class="form-row cols-2" style="margin-bottom:8px">
          <div class="form-group" style="margin:0">
            <label class="form-label">Antal</label>
            <input type="number" id="konstrInlineAntal" class="form-control" value="1" min="0" step="any">
          </div>
          <div class="form-group" style="margin:0">
            <label class="form-label">Anteckning (valfri)</label>
            <input type="text" id="konstrInlineAnt" class="form-control" placeholder="">
          </div>
        </div>
        <div class="flex gap-1">
          <button class="btn btn-success btn-sm" id="konstrInlineLeggTill">✓ Lägg till</button>
          <button class="btn btn-outline btn-sm" id="konstrInlineStang">Stäng</button>
        </div>
      </div>
      ${egkHtml(k.egenkontroll || [])}
      <div class="form-group mt-2">
        <label class="form-label">Anmärkning</label>
        <textarea class="form-control" id="konstrAnt" rows="2">${escHtml(k.anmarkning || '')}</textarea>
      </div>`;
  }

  Modal.open(
    `${escHtml(k.namn)}`,
    byggModalBody(),
    `<span id="konstrSparStatus" class="text-sm text-muted">Sparas automatiskt</span>
     <a class="btn btn-secondary" href="/api/konstruktioner/${kid}/pdf" target="_blank">⬇ PDF</a>
     <button class="btn btn-outline" id="avbrytKonstrModal">Stäng</button>`,
    { noBackdropClose: true }
  );

  function uppdateraModulIndikator() {
    const el = document.getElementById('konstrModulIndikator');
    if (el) el.innerHTML = modulIndikatorHtml(rader);
  }

  function syncRader() {
    rader.forEach((r, i) => {
      const inp = document.querySelector(`input[name="antal_${i}"]`);
      const ant = document.querySelector(`input[name="ant_${i}"]`);
      if (inp) r.antal = parseFloat(inp.value) || 0;
      if (ant) r.anteckning = ant.value;
    });
  }

  function renderRadWrapper() {
    const el = document.getElementById('konstrRadWrapper');
    if (el) el.innerHTML = radTabellHtml(rader);
    bindRadEvents();
    uppdateraModulIndikator();
  }

  function bindRadEvents() {
    const radBody = document.getElementById('konstrRadBody');
    if (!radBody) return;
    radBody.addEventListener('input', () => { syncRader(); uppdateraModulIndikator(); scheduleSave(); });
    radBody.addEventListener('click', e => {
      const btn = e.target.closest('button[data-del]');
      if (!btn) return;
      syncRader();
      rader.splice(parseInt(btn.dataset.del), 1);
      renderRadWrapper();
      saveNow();
    });
  }

  bindRadEvents();

  // Inline lägg till rad
  let inlineArtiklar = [];

  function renderInlineOptions() {
    const sel = document.getElementById('konstrInlineArt');
    if (!sel) return;
    const sok = (document.getElementById('konstrInlineSok').value || '').trim().toLowerCase();
    const filtrerade = sok
      ? inlineArtiklar.filter(a =>
          (a.artikelnamn || '').toLowerCase().includes(sok) ||
          (a.artikelnummer || '').toLowerCase().includes(sok))
      : inlineArtiklar;
    if (!filtrerade.length) {
      sel.innerHTML = '<option value="">Inga artiklar matchar</option>';
      return;
    }
    sel.innerHTML = filtrerade.map(a => `<option value="${a.id}"
        data-namn="${escHtml(a.artikelnamn)}"
        data-enhet="${escHtml(a.enhet || '')}"
        data-enr="${escHtml(a.artikelnummer || '')}"
        data-moduler="${a.moduler || 0}">${escHtml(a.artikelnamn)}${a.artikelnummer ? '  ·  ' + escHtml(a.artikelnummer) : ''}</option>`).join('');
  }

  async function laddaKonstrArtiklar() {
    const katId = document.getElementById('konstrInlineKat').value;
    const sel   = document.getElementById('konstrInlineArt');
    sel.innerHTML = '<option value="">Laddar...</option>';
    try {
      const url  = katId ? `/artiklar?kategori_id=${katId}` : '/artiklar';
      inlineArtiklar = (await api('GET', url)).artiklar || [];
      renderInlineOptions();
    } catch { sel.innerHTML = '<option value="">Fel vid laddning</option>'; }
  }

  document.getElementById('btnKonstrLaggTillRad').addEventListener('click', async () => {
    const form    = document.getElementById('konstrInlineForm');
    const visible = form.style.display !== 'none';
    form.style.display = visible ? 'none' : '';
    if (!visible) {
      await laddaKonstrArtiklar();
      const sokEl = document.getElementById('konstrInlineSok');
      if (sokEl) sokEl.focus();
    }
  });

  document.getElementById('konstrInlineStang').addEventListener('click', () => {
    document.getElementById('konstrInlineForm').style.display = 'none';
  });

  document.getElementById('konstrInlineKat').addEventListener('change', laddaKonstrArtiklar);
  document.getElementById('konstrInlineSok').addEventListener('input', renderInlineOptions);

  document.getElementById('konstrInlineLeggTill').addEventListener('click', () => {
    const artSel = document.getElementById('konstrInlineArt');
    const artId  = parseInt(artSel.value);
    if (!artId) { toast('Välj en artikel', 'error'); return; }
    const opt    = artSel.options[artSel.selectedIndex];
    const antal  = parseFloat(document.getElementById('konstrInlineAntal').value) || 1;
    const ant    = document.getElementById('konstrInlineAnt').value.trim();
    const moduler = parseInt(opt.dataset.moduler || '0') || 0;
    syncRader();
    rader.push({
      artikel_id:  artId,
      artikelnamn: opt.dataset.namn || opt.textContent.trim(),
      enhet:       opt.dataset.enhet || '',
      antal,
      moduler,
      anteckning:  ant,
    });
    renderRadWrapper();
    document.getElementById('konstrInlineAntal').value = '1';
    document.getElementById('konstrInlineAnt').value   = '';
    saveNow();
    toast('Rad tillagd ✓', 'success');
  });

  // Egenkontroll interaktivitet
  const egkListEl = document.getElementById('konstrEgkList');
  if (egkListEl) {
    egkListEl.addEventListener('change', e => {
      const item = e.target.closest('.egk-item');
      if (!item) return;
      const cbUtford = item.querySelector('.egk-utford');
      const cbEjRel  = item.querySelector('.egk-ej-rel');
      if (e.target === cbUtford && cbUtford.checked) {
        cbEjRel.checked = false;
        item.classList.add('utford'); item.classList.remove('ej-rel');
      } else if (e.target === cbEjRel && cbEjRel.checked) {
        cbUtford.checked = false;
        item.classList.add('ej-rel'); item.classList.remove('utford');
      } else {
        item.classList.remove('utford', 'ej-rel');
      }
      const allItems = egkListEl.querySelectorAll('.egk-item');
      const done = [...allItems].filter(i => i.querySelector('.egk-utford').checked).length;
      const tot  = allItems.length;
      const progEl = egkListEl.closest('.egk-section')?.querySelector('.egk-progress');
      if (progEl) progEl.textContent = `${done}/${tot} utförda`;
      saveNow();
    });
  }

  // Status och anmärkning autosparas också
  const statusEl = document.getElementById('konstrStatus');
  if (statusEl) statusEl.addEventListener('change', saveNow);
  const antEl = document.getElementById('konstrAnt');
  if (antEl) antEl.addEventListener('input', scheduleSave);

  // Stäng: spara säkert en sista gång, stäng och uppdatera listan
  const modalCloseBtn = document.getElementById('modalClose');
  const onX = () => stangKonstrModal();
  let _stanger = false;
  async function stangKonstrModal() {
    if (_stanger) return;
    _stanger = true;
    modalCloseBtn.removeEventListener('click', onX);   // undvik läckage till nästa modal
    await saveNow();
    Modal.close();
    onDone && await onDone();
  }
  document.getElementById('avbrytKonstrModal').addEventListener('click', stangKonstrModal);
  modalCloseBtn.addEventListener('click', onX);
}

// ----------------------------------------------------------------
// VIEW: ARTIKLAR (katalog)
// ----------------------------------------------------------------
async function renderArtiklar(app) {
  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Artikelkatalog</h1>
    </div>
    <div class="filter-bar">
      <input type="search" class="form-control" id="sokArt" placeholder="Sök artikel…">
      <select class="form-control" id="filtKat"><option value="">Alla kategorier</option></select>
    </div>
    <div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Artikelnamn</th><th>Kategori</th><th>Enhet</th>
          </tr></thead>
          <tbody id="artBody"></tbody>
        </table>
      </div>
    </div>`;

  // Load filters
  if (!S.kategorier.length) {
    try { S.kategorier = (await api('GET', '/kategorier')).kategorier || []; } catch {}
  }
  const filtKat = document.getElementById('filtKat');
  S.kategorier.forEach(k => { filtKat.innerHTML += `<option value="${k.id}">${escHtml(k.namn)}</option>`; });

  async function ladda() {
    const sok = document.getElementById('sokArt').value;
    const kat = document.getElementById('filtKat').value;
    let url = '/artiklar?';
    if (sok) url += `sok=${encodeURIComponent(sok)}&`;
    if (kat) url += `kategori_id=${kat}&`;
    const arts = (await api('GET', url)).artiklar || [];
    const tbody = document.getElementById('artBody');
    if (!arts.length) { tbody.innerHTML = `<tr><td colspan="3" class="muted text-center">Inga artiklar hittades</td></tr>`; return; }
    tbody.innerHTML = arts.map(a => `
      <tr style="cursor:pointer" data-id="${a.id}" data-namn="${escHtml(a.artikelnamn)}"
          data-kat="${escHtml(a.kategori_namn||'')}" data-enhet="${escHtml(a.enhet)}"
          data-beskrivning="${escHtml(a.beskrivning||'')}">
        <td><strong>${escHtml(a.artikelnamn)}</strong>${a.beskrivning ? ' <span class="text-muted text-sm">ℹ</span>' : ''}</td>
        <td>${escHtml(a.kategori_namn||'')}</td>
        <td>${escHtml(a.enhet)}</td>
      </tr>`).join('');

    tbody.querySelectorAll('tr[data-id]').forEach(row => {
      row.addEventListener('click', () => {
        const besk = row.dataset.beskrivning;
        Modal.open(row.dataset.namn, `
          <dl class="info-dl">
            <dt>Kategori</dt><dd>${row.dataset.kat || '–'}</dd>
            <dt>Enhet</dt>  <dd>${row.dataset.enhet || '–'}</dd>
            ${besk ? `<dt>Beskrivning</dt><dd style="white-space:pre-wrap">${escHtml(besk)}</dd>` : ''}
          </dl>
          ${!besk ? '<p class="text-muted text-sm mt-2">Ingen beskrivning tillagd ännu. Admins kan lägga till via Admin → Artiklar → Redigera.</p>' : ''}`,
          `<button class="btn btn-secondary" onclick="document.getElementById('modal').classList.add('hidden')">Stäng</button>`
        );
      });
    });
  }

  document.getElementById('sokArt').addEventListener('input', ladda);
  document.getElementById('filtKat').addEventListener('change', ladda);
  ladda();
}

// ----------------------------------------------------------------
// VIEW: ADMIN
// ----------------------------------------------------------------
async function renderAdmin(app) {
  if (!S.admin) {
    renderAdminLogin(app);
    return;
  }
  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Administration</h1>
      <button class="btn btn-outline btn-sm" id="btnLogga">Logga ut</button>
    </div>
    <div class="tabs">
      <button class="tab-btn active" data-tab="artiklar">Artiklar</button>
      <button class="tab-btn" data-tab="kategorier">Kategorier</button>
      <button class="tab-btn" data-tab="leverantorer">Leverantörer</button>
      <button class="tab-btn" data-tab="beredare">Beredare</button>
      <button class="tab-btn" data-tab="anvandare">Användare</button>
      <button class="tab-btn" data-tab="installningar">Inställningar</button>
    </div>
    <div id="adminTabContent"></div>`;

  document.getElementById('btnLogga').addEventListener('click', async () => {
    await api('POST', '/admin/logout');
    S.admin = false;
    document.getElementById('adminBadge').classList.add('hidden');
    navigate('admin');
  });

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      ladminTab(btn.dataset.tab);
    });
  });

  ladminTab('artiklar');
}

function renderAdminLogin(app) {
  app.innerHTML = `
    <div class="login-box">
      <div class="card">
        <div class="card-header"><span class="card-title">Adminlogin</span></div>
        <div class="card-body">
          <div class="form-group">
            <label class="form-label">Lösenord</label>
            <input type="password" id="adminPw" class="form-control" autofocus>
          </div>
          <button class="btn btn-navy w-full" id="loginBtn">Logga in</button>
          <p class="text-sm text-muted mt-2">Standardlösenord: admin</p>
        </div>
      </div>
    </div>`;

  async function doLogin() {
    const pw = document.getElementById('adminPw').value;
    try {
      await api('POST', '/admin/login', { losenord: pw });
      S.admin = true;
      document.getElementById('adminBadge').classList.remove('hidden');
      toast('Inloggad', 'success');
      renderAdmin(document.getElementById('app'));
    } catch (e) { toast(e.message || 'Fel lösenord', 'error'); }
  }

  document.getElementById('loginBtn').addEventListener('click', doLogin);
  document.getElementById('adminPw').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
}

async function ladminTab(tab) {
  const cont = document.getElementById('adminTabContent');
  cont.innerHTML = '<div class="text-muted">Laddar…</div>';

  if (tab === 'artiklar')     await adminArtiklar(cont);
  if (tab === 'kategorier')   await adminKategorier(cont);
  if (tab === 'leverantorer') await adminLeverantorer(cont);
  if (tab === 'beredare')     await adminBeredare(cont);
  if (tab === 'anvandare')    await adminAnvandare(cont);
  if (tab === 'installningar') await adminInstallningar(cont);
}

// ---- ADMIN: ARTIKLAR ----
async function adminArtiklar(cont) {
  if (!S.kategorier.length) {
    try { S.kategorier = (await api('GET', '/kategorier')).kategorier || []; } catch {}
  }
  if (!S.leverantorer.length) {
    try { S.leverantorer = (await api('GET', '/leverantorer')).leverantorer || []; } catch {}
  }
  let arts = [];
  try { arts = (await api('GET', '/artiklar?filter=alla')).artiklar || []; } catch {}

  const katOpts = S.kategorier.map(k => `<option value="${k.id}">${escHtml(k.namn)}</option>`).join('');

  cont.innerHTML = `
    <div class="flex gap-2 mb-2">
      <button class="btn btn-navy btn-sm" id="btnNyArt">+ Ny artikel</button>
      <input type="search" class="form-control" id="sokAdmArt" placeholder="Sök…" style="max-width:240px">
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Artikelnamn</th><th>E-nummer</th><th>Kategori</th><th>Enhet</th><th>Aktiv</th><th>Åtgärder</th></tr></thead>
        <tbody id="admArtBody"></tbody>
      </table>
    </div>`;

  function render(lista) {
    const sok = document.getElementById('sokAdmArt').value.toLowerCase();
    const filtered = lista.filter(a => !sok || a.artikelnamn.toLowerCase().includes(sok) || (a.artikelnummer||'').toLowerCase().includes(sok));
    document.getElementById('admArtBody').innerHTML = filtered.map(a => `
      <tr>
        <td>${escHtml(a.artikelnamn)}</td>
        <td class="mono">${escHtml(a.artikelnummer||'–')}</td>
        <td>${escHtml(a.kategori_namn||'')}</td>
        <td>${escHtml(a.enhet)}</td>
        <td>${a.aktiv ? '✔' : '–'}</td>
        <td class="flex gap-1">
          <button class="btn btn-sm btn-outline" data-id="${a.id}" data-action="edit">Redigera</button>
          <button class="btn btn-sm btn-secondary" data-id="${a.id}" data-action="pris">Priser</button>
          <button class="btn btn-sm btn-danger"  data-id="${a.id}" data-action="del">Ta bort</button>
        </td>
      </tr>`).join('');

    document.getElementById('admArtBody').querySelectorAll('button[data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const art = arts.find(x => x.id == btn.dataset.id);
        if (btn.dataset.action === 'edit') modalArtForm(art, katOpts, async () => {
          arts = (await api('GET', '/artiklar?filter=alla')).artiklar || [];
          render(arts);
        });
        else if (btn.dataset.action === 'pris') modalPriser(art.id, art.artikelnamn);
        else if (btn.dataset.action === 'del') {
          const ok = await confirm('Ta bort artikel', `Ta bort "${art.artikelnamn}"?`);
          if (!ok) return;
          try {
            await api('DELETE', `/admin/artiklar/${art.id}`);
            arts = arts.filter(x => x.id != art.id);
            toast('Borttagen', 'success');
            render(arts);
          } catch (e) { toast(e.message, 'error'); }
        }
      });
    });
  }

  document.getElementById('sokAdmArt').addEventListener('input', () => render(arts));
  document.getElementById('btnNyArt').addEventListener('click', () => modalArtForm(null, katOpts, async () => {
    arts = (await api('GET', '/artiklar?filter=alla')).artiklar || [];
    render(arts);
  }));
  render(arts);
}

function modalArtForm(art, katOpts, onDone) {
  // Hämta befintligt E-nummer från Onninen-posten om vi redigerar
  const befEnummer = art?.priser?.find(p => p.leverantor_namn === 'Onninen')?.artikelnummer
                  || art?.artikelnummer || '';

  Modal.open(art ? 'Redigera artikel' : 'Ny artikel', `
    <form id="artForm">
      <div class="form-group">
        <label class="form-label">Artikelnamn <span class="req">*</span></label>
        <input name="artikelnamn" class="form-control" value="${escHtml(art?.artikelnamn||'')}" required>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Kategori <span class="req">*</span></label>
          <select name="kategori_id" class="form-control" required>
            <option value="">– välj –</option>${katOpts.replace(`value="${art?.kategori_id}"`, `value="${art?.kategori_id}" selected`)}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Enhet <span class="req">*</span></label>
          <input name="enhet" class="form-control" value="${escHtml(art?.enhet||'')}" required>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">E-nummer (Onninen)</label>
        <input name="enummer" class="form-control" value="${escHtml(befEnummer)}" placeholder="t.ex. 3012345">
        <span class="form-hint">Sparas automatiskt kopplat till leverantören Onninen</span>
      </div>
      <div class="form-group">
        <label class="form-label">Beskrivning</label>
        <textarea name="beskrivning" class="form-control" rows="3" placeholder="Valfri beskrivning av artikeln…">${escHtml(art?.beskrivning||'')}</textarea>
      </div>
      <div class="form-check">
        <input type="checkbox" name="aktiv" id="artAktiv" ${(!art || art.aktiv) ? 'checked' : ''}>
        <label for="artAktiv">Aktiv</label>
      </div>
    </form>`,
    `<button class="btn btn-navy" id="sparaArt">Spara</button>
     <button class="btn btn-secondary" id="avbrytArt">Avbryt</button>`
  );
  document.getElementById('avbrytArt').addEventListener('click', Modal.close);
  document.getElementById('sparaArt').addEventListener('click', async () => {
    const f = document.getElementById('artForm');
    if (!f.reportValidity()) return;
    const fd = new FormData(f);
    const body = Object.fromEntries(fd.entries());
    const enummer = (body.enummer || '').trim();
    delete body.enummer;
    body.aktiv = document.getElementById('artAktiv').checked ? 1 : 0;
    try {
      let artId;
      if (art) {
        await api('PUT', `/admin/artiklar/${art.id}`, body);
        artId = art.id;
      } else {
        const res = await api('POST', '/admin/artiklar', body);
        artId = res.id;
      }
      // Spara E-nummer till Onninen om det angetts
      if (enummer) {
        if (!S.leverantorer.length) {
          try { S.leverantorer = (await api('GET', '/leverantorer')).leverantorer || []; } catch {}
        }
        const onninen = S.leverantorer.find(l => l.namn === 'Onninen');
        if (onninen) {
          await api('POST', `/admin/artiklar/${artId}/priser`, {
            leverantor_id: onninen.id,
            artikelnummer: enummer,
            a_pris: null
          });
        }
      }
      toast('Sparad', 'success');
      Modal.close();
      onDone && onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
}

async function modalPriser(artId, artNamn) {
  let priser = [];
  try { priser = (await api('GET', `/admin/artiklar/${artId}/priser`)).priser || []; } catch {}
  if (!S.leverantorer.length) {
    try { S.leverantorer = (await api('GET', '/leverantorer')).leverantorer || []; } catch {}
  }
  const levOpts = S.leverantorer.map(l =>
    `<option value="${l.id}">${escHtml(l.namn)}</option>`).join('');

  function renderPriserHtml() {
    const rows = priser.map((p, i) => `
      <tr>
        <td>${escHtml(p.leverantor_namn)}</td>
        <td class="mono">${escHtml(p.artikelnummer||'')}</td>
        <td class="num">${p.a_pris != null ? kr(p.a_pris) : '–'}</td>
        <td><button class="btn btn-sm btn-danger" data-del="${p.id}">✕</button></td>
      </tr>`).join('');
    return `
      <h4 class="text-navy mb-1">${escHtml(artNamn)}</h4>
      <div class="table-wrap mb-2">
        <table><thead><tr><th>Leverantör</th><th>Art.nr</th><th class="right">À-pris</th><th></th></tr></thead>
        <tbody id="prisBody">${rows || '<tr><td colspan="4" class="muted">Inga priser</td></tr>'}</tbody></table>
      </div>
      <form id="prisForm" class="form-row cols-3">
        <div class="form-group"><label class="form-label">Leverantör</label>
          <select name="leverantor_id" class="form-control" required><option value="">– välj –</option>${levOpts}</select></div>
        <div class="form-group"><label class="form-label">Art.nr</label>
          <input name="artikelnummer" class="form-control"></div>
        <div class="form-group"><label class="form-label">À-pris</label>
          <input type="number" name="a_pris" class="form-control" step="0.01" min="0"></div>
      </form>`;
  }

  Modal.open('Priser',
    renderPriserHtml(),
    `<button class="btn btn-success" id="laggTillPris">+ Lägg till pris</button>
     <button class="btn btn-secondary" id="stangPris">Stäng</button>`
  );

  function bindEvents() {
    document.getElementById('stangPris').addEventListener('click', Modal.close);
    document.getElementById('prisBody').querySelectorAll('button[data-del]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ok = await confirm('Ta bort pris', 'Ta bort detta pris?');
        if (!ok) return;
        try {
          await api('DELETE', `/admin/artiklar/${artId}/priser/${btn.dataset.del}`);
          priser = priser.filter(p => p.id != btn.dataset.del);
          document.getElementById('modalBody').innerHTML = renderPriserHtml();
          bindEvents();
          toast('Borttaget', 'success');
        } catch (e) { toast(e.message, 'error'); }
      });
    });
    document.getElementById('laggTillPris').addEventListener('click', async () => {
      const f = document.getElementById('prisForm');
      if (!f.querySelector('[name=leverantor_id]').value) { toast('Välj leverantör', 'error'); return; }
      const fd = new FormData(f);
      const body = Object.fromEntries(fd.entries());
      try {
        const ny = await api('POST', `/admin/artiklar/${artId}/priser`, body);
        priser.push(ny.pris || body);
        priser = (await api('GET', `/admin/artiklar/${artId}/priser`)).priser || [];
        document.getElementById('modalBody').innerHTML = renderPriserHtml();
        bindEvents();
        toast('Pris tillagt', 'success');
      } catch (e) { toast(e.message, 'error'); }
    });
  }
  bindEvents();
}

// ---- ADMIN: KATEGORIER ----
async function adminKategorier(cont) {
  let kats = [];
  try { kats = (await api('GET', '/kategorier')).kategorier || []; } catch {}

  cont.innerHTML = `
    <div class="flex gap-2 mb-2">
      <button class="btn btn-navy btn-sm" id="btnNyKat">+ Ny kategori</button>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Namn</th><th>Sortering</th><th>Åtgärder</th></tr></thead>
        <tbody>${kats.map(k => `
          <tr>
            <td>${escHtml(k.namn)}</td>
            <td>${k.sortering}</td>
            <td class="flex gap-1">
              <button class="btn btn-sm btn-outline" data-id="${k.id}" data-action="edit">Redigera</button>
              <button class="btn btn-sm btn-danger"  data-id="${k.id}" data-action="del">Ta bort</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  function modalKatForm(k) {
    Modal.open(k ? 'Redigera kategori' : 'Ny kategori', `
      <form id="katForm">
        <div class="form-group"><label class="form-label">Namn <span class="req">*</span></label>
          <input name="namn" class="form-control" value="${escHtml(k?.namn||'')}" required></div>
        <div class="form-group"><label class="form-label">Sortering</label>
          <input type="number" name="sortering" class="form-control" value="${k?.sortering||0}"></div>
      </form>`,
      `<button class="btn btn-navy" id="sparaKat">Spara</button>
       <button class="btn btn-secondary" id="avbrytKat">Avbryt</button>`
    );
    document.getElementById('avbrytKat').addEventListener('click', Modal.close);
    document.getElementById('sparaKat').addEventListener('click', async () => {
      const f = document.getElementById('katForm');
      if (!f.reportValidity()) return;
      const body = Object.fromEntries(new FormData(f).entries());
      try {
        if (k) await api('PUT', `/admin/kategorier/${k.id}`, body);
        else   await api('POST', '/admin/kategorier', body);
        toast('Sparad', 'success');
        Modal.close();
        S.kategorier = [];
        await adminKategorier(cont);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  document.getElementById('btnNyKat').addEventListener('click', () => modalKatForm(null));
  cont.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const k = kats.find(x => x.id == btn.dataset.id);
      if (btn.dataset.action === 'edit') modalKatForm(k);
      else {
        const ok = await confirm('Ta bort kategori', `Ta bort "${k.namn}"?`);
        if (!ok) return;
        try {
          await api('DELETE', `/admin/kategorier/${k.id}`);
          toast('Borttagen', 'success');
          S.kategorier = [];
          await adminKategorier(cont);
        } catch (e) { toast(e.message, 'error'); }
      }
    });
  });
}

// ---- ADMIN: LEVERANTORER ----
async function adminLeverantorer(cont) {
  let levs = [];
  try { levs = (await api('GET', '/leverantorer')).leverantorer || []; } catch {}

  cont.innerHTML = `
    <div class="flex gap-2 mb-2">
      <button class="btn btn-navy btn-sm" id="btnNyLev">+ Ny leverantör</button>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Namn</th><th>Aktiv</th><th>Åtgärder</th></tr></thead>
        <tbody>${levs.map(l => `
          <tr>
            <td>${escHtml(l.namn)}</td>
            <td>${l.aktiv ? '✔' : '–'}</td>
            <td class="flex gap-1">
              <button class="btn btn-sm btn-outline" data-id="${l.id}" data-action="edit">Redigera</button>
              <button class="btn btn-sm btn-danger"  data-id="${l.id}" data-action="del">Ta bort</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  function modalLevForm(l) {
    Modal.open(l ? 'Redigera leverantör' : 'Ny leverantör', `
      <form id="levForm">
        <div class="form-group"><label class="form-label">Namn <span class="req">*</span></label>
          <input name="namn" class="form-control" value="${escHtml(l?.namn||'')}" required></div>
        <div class="form-check">
          <input type="checkbox" name="aktiv" id="levAktiv" ${(!l||l.aktiv)?'checked':''}>
          <label for="levAktiv">Aktiv</label>
        </div>
      </form>`,
      `<button class="btn btn-navy" id="sparaLev">Spara</button>
       <button class="btn btn-secondary" id="avbrytLev">Avbryt</button>`
    );
    document.getElementById('avbrytLev').addEventListener('click', Modal.close);
    document.getElementById('sparaLev').addEventListener('click', async () => {
      const f = document.getElementById('levForm');
      if (!f.reportValidity()) return;
      const body = Object.fromEntries(new FormData(f).entries());
      body.aktiv = document.getElementById('levAktiv').checked ? 1 : 0;
      try {
        if (l) await api('PUT', `/admin/leverantorer/${l.id}`, body);
        else   await api('POST', '/admin/leverantorer', body);
        toast('Sparad', 'success');
        Modal.close();
        S.leverantorer = [];
        await adminLeverantorer(cont);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  document.getElementById('btnNyLev').addEventListener('click', () => modalLevForm(null));
  cont.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const l = levs.find(x => x.id == btn.dataset.id);
      if (btn.dataset.action === 'edit') modalLevForm(l);
      else {
        const ok = await confirm('Ta bort leverantör', `Ta bort "${l.namn}"?`);
        if (!ok) return;
        try {
          await api('DELETE', `/admin/leverantorer/${l.id}`);
          toast('Borttagen', 'success');
          S.leverantorer = [];
          await adminLeverantorer(cont);
        } catch (e) { toast(e.message, 'error'); }
      }
    });
  });
}

// ---- ADMIN: BEREDARE ----
async function adminBeredare(cont) {
  S.beredare = [];
  await laddaBeredare();

  cont.innerHTML = `
    <div class="flex gap-2 mb-2">
      <button class="btn btn-navy btn-sm" id="btnNyBer">+ Ny beredare</button>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Namn</th><th>Aktiv</th><th>Åtgärder</th></tr></thead>
        <tbody>${S.beredare.map(b => `
          <tr>
            <td>${escHtml(b.namn)}</td>
            <td>${b.aktiv ? '✔' : '–'}</td>
            <td class="flex gap-1">
              <button class="btn btn-sm btn-outline" data-id="${b.id}" data-action="edit">Redigera</button>
              <button class="btn btn-sm btn-danger"  data-id="${b.id}" data-action="del">Ta bort</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  function modalBerForm(b) {
    Modal.open(b ? 'Redigera beredare' : 'Ny beredare', `
      <form id="berForm">
        <div class="form-group"><label class="form-label">Namn <span class="req">*</span></label>
          <input name="namn" class="form-control" value="${escHtml(b?.namn||'')}" required></div>
        <div class="form-check">
          <input type="checkbox" name="aktiv" id="berAktiv" ${(!b||b.aktiv)?'checked':''}>
          <label for="berAktiv">Aktiv</label>
        </div>
      </form>`,
      `<button class="btn btn-navy" id="sparaBer">Spara</button>
       <button class="btn btn-secondary" id="avbrytBer">Avbryt</button>`
    );
    document.getElementById('avbrytBer').addEventListener('click', Modal.close);
    document.getElementById('sparaBer').addEventListener('click', async () => {
      const f = document.getElementById('berForm');
      if (!f.reportValidity()) return;
      const body = Object.fromEntries(new FormData(f).entries());
      body.aktiv = document.getElementById('berAktiv').checked ? 1 : 0;
      try {
        if (b) await api('PUT', `/admin/beredare/${b.id}`, body);
        else   await api('POST', '/admin/beredare', body);
        toast('Sparad', 'success');
        Modal.close();
        S.beredare = [];
        await adminBeredare(cont);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  document.getElementById('btnNyBer').addEventListener('click', () => modalBerForm(null));
  cont.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const b = S.beredare.find(x => x.id == btn.dataset.id);
      if (btn.dataset.action === 'edit') modalBerForm(b);
      else {
        const ok = await confirm('Ta bort beredare', `Ta bort "${b.namn}"?`);
        if (!ok) return;
        try {
          await api('DELETE', `/admin/beredare/${b.id}`);
          toast('Borttagen', 'success');
          S.beredare = [];
          await adminBeredare(cont);
        } catch (e) { toast(e.message, 'error'); }
      }
    });
  });
}

// ---- ADMIN: ANVÄNDARE ----
const ROLL_NAMN = { admin: 'Administratör', beredare: 'Beredare', ue: 'UE (underentreprenör)' };

async function adminAnvandare(cont) {
  await laddaBeredare();
  let anv = [];
  try { anv = (await api('GET', '/admin/anvandare')).anvandare || []; } catch (e) { toast(e.message, 'error'); }

  cont.innerHTML = `
    <div class="flex gap-2 mb-2 items-center">
      <button class="btn btn-navy btn-sm" id="btnNyAnv">+ Ny användare</button>
      <span class="text-sm text-muted">Standardlösenord för seedade konton: <strong>oneco</strong> – be alla byta.</span>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Användarnamn</th><th>Namn</th><th>Roll</th><th>Beredare</th><th>Aktiv</th><th>Åtgärder</th></tr></thead>
        <tbody>${anv.map(u => `
          <tr>
            <td class="mono">${escHtml(u.anvandarnamn)}</td>
            <td>${escHtml(u.namn || '–')}</td>
            <td>${escHtml(ROLL_NAMN[u.roll] || u.roll)}</td>
            <td>${escHtml(u.beredare || '–')}</td>
            <td>${u.aktiv ? '✔' : '–'}</td>
            <td class="flex gap-1">
              <button class="btn btn-sm btn-outline" data-id="${u.id}" data-action="edit">Redigera</button>
              <button class="btn btn-sm btn-danger"  data-id="${u.id}" data-action="del">Ta bort</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  function rollOpts(vald) {
    return Object.entries(ROLL_NAMN).map(([v, txt]) =>
      `<option value="${v}" ${vald === v ? 'selected' : ''}>${txt}</option>`).join('');
  }
  function berOpts(vald) {
    return `<option value="">– ingen –</option>` +
      S.beredare.map(b => `<option ${vald === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('');
  }

  function modalAnvForm(u) {
    Modal.open(u ? `Redigera ${u.anvandarnamn}` : 'Ny användare', `
      <form id="anvForm">
        <div class="form-group"><label class="form-label">Användarnamn <span class="req">*</span></label>
          <input name="anvandarnamn" class="form-control" value="${escHtml(u?.anvandarnamn||'')}" ${u ? 'disabled' : 'required'}></div>
        <div class="form-group"><label class="form-label">Namn</label>
          <input name="namn" class="form-control" value="${escHtml(u?.namn||'')}"></div>
        <div class="form-group"><label class="form-label">Lösenord ${u ? '' : '<span class="req">*</span>'}</label>
          <input type="password" name="losenord" class="form-control" autocomplete="new-password"
                 placeholder="${u ? 'Lämna tomt för oförändrat' : ''}" ${u ? '' : 'required'}></div>
        <div class="form-row cols-2">
          <div class="form-group"><label class="form-label">Roll</label>
            <select name="roll" class="form-control">${rollOpts(u?.roll || 'beredare')}</select></div>
          <div class="form-group"><label class="form-label">Beredare (för auto-filter)</label>
            <select name="beredare" class="form-control">${berOpts(u?.beredare || '')}</select></div>
        </div>
        <div class="form-check">
          <input type="checkbox" name="aktiv" id="anvAktiv" ${(!u||u.aktiv)?'checked':''}>
          <label for="anvAktiv">Aktiv</label>
        </div>
      </form>`,
      `<button class="btn btn-navy" id="sparaAnv">Spara</button>
       <button class="btn btn-secondary" id="avbrytAnv">Avbryt</button>`
    );
    document.getElementById('avbrytAnv').addEventListener('click', Modal.close);
    document.getElementById('sparaAnv').addEventListener('click', async () => {
      const f = document.getElementById('anvForm');
      if (!f.reportValidity()) return;
      const body = Object.fromEntries(new FormData(f).entries());
      body.aktiv = document.getElementById('anvAktiv').checked ? 1 : 0;
      if (u && !body.losenord) delete body.losenord;  // behåll befintligt lösenord
      try {
        if (u) await api('PUT', `/admin/anvandare/${u.id}`, body);
        else   await api('POST', '/admin/anvandare', body);
        toast('Sparad', 'success');
        Modal.close();
        await adminAnvandare(cont);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  document.getElementById('btnNyAnv').addEventListener('click', () => modalAnvForm(null));
  cont.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const u = anv.find(x => x.id == btn.dataset.id);
      if (btn.dataset.action === 'edit') modalAnvForm(u);
      else {
        const ok = await confirm('Ta bort användare', `Ta bort kontot "${u.anvandarnamn}"?`);
        if (!ok) return;
        try {
          await api('DELETE', `/admin/anvandare/${u.id}`);
          toast('Borttagen', 'success');
          await adminAnvandare(cont);
        } catch (e) { toast(e.message, 'error'); }
      }
    });
  });
}

// ---- ADMIN: INSTÄLLNINGAR ----
async function adminInstallningar(cont) {
  let inst = {};
  try { inst = (await api('GET', '/installningar')).installningar || {}; } catch {}

  cont.innerHTML = `
    <div class="card" style="max-width:500px">
      <div class="card-header"><span class="card-title">Systeminställningar</span></div>
      <div class="card-body">
        <form id="instForm">
          <div class="form-group"><label class="form-label">Företagsnamn</label>
            <input name="foretagsnamn" class="form-control" value="${escHtml(inst.foretagsnamn||'')}"></div>
          <div class="form-group"><label class="form-label">Organisationsnummer</label>
            <input name="org_nummer" class="form-control" value="${escHtml(inst.org_nummer||'')}"></div>
          <div class="form-group"><label class="form-label">Telefon</label>
            <input name="telefon" class="form-control" value="${escHtml(inst.telefon||'')}"></div>
          <div class="form-group"><label class="form-label">E-post</label>
            <input name="epost" class="form-control" value="${escHtml(inst.epost||'')}"></div>
          <button type="submit" class="btn btn-navy">Spara</button>
        </form>
        <hr class="mt-3 mb-3" style="border-color:var(--gray-200)">
        <h4 class="text-navy mb-2">Byt lösenord</h4>
        <div class="form-group"><label class="form-label">Nytt lösenord</label>
          <input type="password" id="nyttLos" class="form-control"></div>
        <button class="btn btn-outline" id="bytLos">Byt lösenord</button>
      </div>
    </div>`;

  document.getElementById('instForm').addEventListener('submit', async e => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api('PUT', '/installningar', body);
      toast('Inställningar sparade', 'success');
    } catch (err) { toast(err.message, 'error'); }
  });

  document.getElementById('bytLos').addEventListener('click', async () => {
    const pw = document.getElementById('nyttLos').value;
    if (!pw) { toast('Ange ett lösenord', 'error'); return; }
    try {
      await api('PUT', '/admin/losenord', { losenord: pw });
      toast('Lösenord bytt', 'success');
      document.getElementById('nyttLos').value = '';
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// MODAL CLOSE ON OVERLAY CLICK
// ----------------------------------------------------------------
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === document.getElementById('modal') && !Modal.noBackdropClose) Modal.close();
});
document.getElementById('modalClose').addEventListener('click', Modal.close);

// ----------------------------------------------------------------
// NAV CLICKS
// ----------------------------------------------------------------
document.querySelectorAll('[data-view]').forEach(el => {
  el.addEventListener('click', () => navigate(el.dataset.view));
});

// ----------------------------------------------------------------
// LOGIN
// ----------------------------------------------------------------
function visaLoginSkarm() {
  document.querySelector('.topnav').style.display = 'none';
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="login-wrap">
      <div class="login-card">
        <div class="login-logo">
          <div class="login-logo-dot"></div>
        </div>
        <h1 class="login-title">Beredning-Projektledning</h1>
        <p class="login-sub">Logga in för att fortsätta</p>
        <form id="loginForm" class="login-form">
          <div class="form-group">
            <input type="text" id="loginUser" class="form-control login-input"
                   placeholder="Användarnamn" autocomplete="username" autofocus>
          </div>
          <div class="form-group">
            <input type="password" id="loginPw" class="form-control login-input"
                   placeholder="Lösenord" autocomplete="current-password" required>
          </div>
          <div id="loginFel" class="login-fel hidden">
            <img id="gandalfGif" src="https://media.giphy.com/media/njYrp176NQsHS/giphy.gif"
                 alt="You shall not pass!"
                 style="width:180px;display:block;margin:0 auto 8px;border-radius:8px;">
            <span>YOU SHALL NOT PASS! 🧙 Fel lösenord.</span>
          </div>
          <button type="submit" class="btn btn-navy login-btn">Logga in</button>
        </form>
      </div>
    </div>`;

  document.getElementById('loginForm').addEventListener('submit', async e => {
    e.preventDefault();
    const anvandarnamn = document.getElementById('loginUser').value.trim();
    const pw      = document.getElementById('loginPw').value;
    const felDiv  = document.getElementById('loginFel');
    const btn     = e.target.querySelector('button[type="submit"]');
    felDiv.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Loggar in…';
    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ anvandarnamn, losenord: pw }),
      });
      if (!r.ok) throw new Error('fel');
      sessionStorage.setItem('logged_in', '1');
      document.querySelector('.topnav').style.display = '';
      await boot();
    } catch {
      felDiv.classList.remove('hidden');
      // Starta om GIF:en genom att byta src
      const gif = document.getElementById('gandalfGif');
      gif.src = '';
      gif.src = 'https://media.giphy.com/media/njYrp176NQsHS/giphy.gif';
      document.getElementById('loginPw').value = '';
      document.getElementById('loginPw').focus();
      btn.disabled = false;
      btn.textContent = 'Logga in';
    }
  });
}

// ================================================================
// KONTROLLRUM — KPI Dashboard
// ================================================================
async function renderKontrollrum(app) {
  await anslLoadFromApi();
  const data  = AnslState.projekt !== null ? AnslState.projekt : ANSL_SAMPLE;
  const today = new Date();
  const in30  = new Date(today.getTime() + 30 * 86400000);
  const in60  = new Date(today.getTime() + 60 * 86400000);

  // === Beräkningar ===
  const total         = data.length;
  const aktiva        = data.filter(p => p.fas !== 'Avslutat' && p.fas !== 'Drifttagning klar').length;
  const klara         = data.filter(p => p.fas === 'Avslutat' || p.fas === 'Drifttagning klar').length;
  const medBlockering = data.filter(p => p.blockering).length;
  const atRisk        = data.filter(p => {
    if (p.fas === 'Avslutat' || p.fas === 'Drifttagning klar') return false;
    return (p.bestallningKlar && new Date(p.bestallningKlar) < today) || !!p.blockering;
  }).length;
  const leverans      = total > 0 ? Math.round(klara / total * 100) : 0;

  const berDays  = data.filter(p => p.berStart && p.berSlut)
    .map(p => Math.round((new Date(p.berSlut)  - new Date(p.berStart))  / 86400000));
  const avgBer   = berDays.length  ? Math.round(berDays.reduce((a,b)=>a+b,0)  / berDays.length)  : 0;

  const montDays = data.filter(p => p.montStart && p.montSlut)
    .map(p => Math.round((new Date(p.montSlut) - new Date(p.montStart)) / 86400000));
  const avgMont  = montDays.length ? Math.round(montDays.reduce((a,b)=>a+b,0) / montDays.length) : 0;

  const montageNext30     = data.filter(p => p.montStart && new Date(p.montStart) >= today && new Date(p.montStart) <= in30 && p.fas !== 'Avslutat').length;
  const driftNext60       = data.filter(p => p.driftDat  && new Date(p.driftDat)  >= today && new Date(p.driftDat)  <= in60 && p.fas !== 'Avslutat').length;
  const pagaendeBeredning = data.filter(p => p.fas === 'Beredning').length;
  const utanBeredare      = data.filter(p => !p.beredare && p.fas !== 'Avslutat' && p.fas !== 'Drifttagning klar').length;
  const utanBestallning   = data.filter(p => !p.bestallningKlar && p.fas !== 'Avslutat' && p.fas !== 'Drifttagning klar').length;

  const kundSet = [...new Set(data.filter(p => p.kund && p.kund !== '–').map(p => p.kund))];

  const iMontageFas = data.filter(p => p.fas === 'Montage' || p.fas === 'Byggstart').length;

  const monthNames = ['Jan','Feb','Mar','Apr','Maj','Jun','Jul','Aug','Sep','Okt','Nov','Dec'];
  const montageByMonth = [];
  for (let i = 0; i < 12; i++) {
    const m = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const count = data.filter(p => {
      if (!p.montStart) return false;
      const d = new Date(p.montStart);
      return d.getFullYear() === m.getFullYear() && d.getMonth() === m.getMonth();
    }).length;
    montageByMonth.push({ label: `${monthNames[m.getMonth()]} ${String(m.getFullYear()).slice(2)}`, count });
  }

  const beredningByMonth = [];
  for (let i = 0; i < 12; i++) {
    const m = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const count = data.filter(p => {
      if (!p.berStart) return false;
      const d = new Date(p.berStart);
      return d.getFullYear() === m.getFullYear() && d.getMonth() === m.getMonth();
    }).length;
    beredningByMonth.push({ label: `${monthNames[m.getMonth()]} ${String(m.getFullYear()).slice(2)}`, count });
  }

  const fasData   = ANSL_FAS_ORDER.map(f => data.filter(p => p.fas === f).length);
  const fasColors = ANSL_FAS_ORDER.map(f => ANSL_FAS_C[f]);

  const berMap = {};
  data.filter(p => p.fas !== 'Avslutat').forEach(p => {
    if (p.beredare) berMap[p.beredare] = (berMap[p.beredare] || 0) + 1;
  });
  const berSorted = Object.entries(berMap).sort((a,b) => b[1]-a[1]);

  // Fas-fördelning per beredare (staplat)
  const fasGrps = [
    { label:'Tidig fas',  faser:['Tidig fas','Sen fas'],           color:'rgba(59,130,246,.75)' },
    { label:'Beredning',  faser:['Beredning'],                     color:'rgba(155,89,182,.75)' },
    { label:'Montage',    faser:['Byggstart','Montage'],           color:'rgba(244,163,24,.75)' },
    { label:'Klar',       faser:['Drifttagning klar','Avslutat'], color:'rgba(46,204,142,.75)' },
  ];
  const berNames = berSorted.map(([n]) => n);

  const kommande = data
    .filter(p => p.bestallningKlar && new Date(p.bestallningKlar) >= today && p.fas !== 'Avslutat' && p.fas !== 'Drifttagning klar')
    .sort((a,b) => a.bestallningKlar.localeCompare(b.bestallningKlar))
    .slice(0, 10);

  const kommandeDrift = data
    .filter(p => p.driftDat && new Date(p.driftDat) >= today && p.fas !== 'Avslutat')
    .sort((a,b) => a.driftDat.localeCompare(b.driftDat))
    .slice(0, 10);

  const blockeringar = data.filter(p => p.blockering && p.fas !== 'Avslutat');

  function fmtD(str) {
    const d = new Date(str);
    return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
  }
  function dlRow(p, dateKey, dotStyle = '') {
    const d    = new Date(p[dateKey]);
    const days = Math.round((d - today) / 86400000);
    const cls  = days <= 14 ? 'kpi-dl-urgent' : days <= 30 ? 'kpi-dl-warn' : '';
    return `<div class="kpi-dl-row ${cls}">
      <div class="kpi-dl-dot"${dotStyle ? ` style="${dotStyle}"` : ''}></div>
      <div class="kpi-dl-info">
        <div class="kpi-dl-name">${escHtml(p.namn)}</div>
        <div class="kpi-dl-meta">${escHtml(p.id)} · ${escHtml(p.beredare||'–')}</div>
      </div>
      <div class="kpi-dl-right">
        <div class="kpi-dl-date">${fmtD(p[dateKey])}</div>
        <div class="kpi-dl-days">${days}d</div>
      </div>
    </div>`;
  }

  const dateLong = today.toLocaleDateString('sv-SE', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  app.innerHTML = `
  <div class="kpi-root">
    <div class="kpi-header">
      <div>
        <div class="kpi-header-title">Kontrollrum</div>
        <div class="kpi-header-sub">Realtidsöversikt · ${total} projekt · ${dateLong}</div>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-cards">
      <div class="kpi-card kpi-card-blue">
        <div class="kpi-card-top">
          <div class="kpi-card-icon">📋</div>
          ${kundSet.length > 0 ? `<div class="kpi-card-badge">${kundSet.length} kunder</div>` : ''}
        </div>
        <div class="kpi-card-val" data-target="${total}">0</div>
        <div class="kpi-card-lbl">Totalt projekt</div>
        <div class="kpi-card-ctx">${aktiva} aktiva · ${klara} klara</div>
        <div class="kpi-card-accent kpi-accent-blue"></div>
      </div>
      <div class="kpi-card kpi-card-cyan">
        <div class="kpi-card-top"><div class="kpi-card-icon">⚡</div></div>
        <div class="kpi-card-val" data-target="${aktiva}">0</div>
        <div class="kpi-card-lbl">Aktiva projekt</div>
        <div class="kpi-card-ctx">${total > 0 ? Math.round(aktiva/total*100) : 0}% av portföljen</div>
        <div class="kpi-card-accent kpi-accent-cyan"></div>
      </div>
      <div class="kpi-card kpi-card-green">
        <div class="kpi-card-top">
          <div class="kpi-card-icon">✅</div>
          <div class="kpi-card-pct kpi-pct-green">${leverans}%</div>
        </div>
        <div class="kpi-card-val" data-target="${klara}">0</div>
        <div class="kpi-card-lbl">Avslutade</div>
        <div class="kpi-progress-wrap"><div class="kpi-progress-fill kpi-prog-green" style="width:0%" data-pct="${leverans}"></div></div>
        <div class="kpi-card-accent kpi-accent-green"></div>
      </div>
      <div class="kpi-card kpi-card-red">
        <div class="kpi-card-top"><div class="kpi-card-icon">⚠️</div></div>
        <div class="kpi-card-val" data-target="${atRisk}">0</div>
        <div class="kpi-card-lbl">I riskzon</div>
        <div class="kpi-card-ctx">${medBlockering} blockerade · ${Math.max(0,atRisk-medBlockering)} försenade</div>
        <div class="kpi-card-accent kpi-accent-red"></div>
      </div>
    </div>

    <!-- Pipeline metrics -->
    <div class="kpi-pipeline">
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">🔨</div>
        <div class="kpi-pipe-val" style="color:var(--amber)">${montageNext30}</div>
        <div class="kpi-pipe-lbl">Montage start</div>
        <div class="kpi-pipe-ctx">nästa 30 dagar</div>
      </div>
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">🔌</div>
        <div class="kpi-pipe-val" style="color:var(--green)">${driftNext60}</div>
        <div class="kpi-pipe-lbl">Driftsättning</div>
        <div class="kpi-pipe-ctx">nästa 60 dagar</div>
      </div>
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">📐</div>
        <div class="kpi-pipe-val" style="color:var(--blue)">${pagaendeBeredning}</div>
        <div class="kpi-pipe-lbl">Pågående beredning</div>
        <div class="kpi-pipe-ctx">fas = Beredning</div>
      </div>
      <div class="kpi-pipe-card${utanBeredare > 0 ? ' kpi-pipe-warn' : ''}">
        <div class="kpi-pipe-icon">👤</div>
        <div class="kpi-pipe-val" style="color:${utanBeredare > 0 ? 'var(--red)' : 'var(--text-muted)'}">${utanBeredare}</div>
        <div class="kpi-pipe-lbl">Utan beredare</div>
        <div class="kpi-pipe-ctx">ej tilldelade</div>
      </div>
      <div class="kpi-pipe-card${utanBestallning > 0 ? ' kpi-pipe-warn' : ''}">
        <div class="kpi-pipe-icon">📅</div>
        <div class="kpi-pipe-val" style="color:${utanBestallning > 0 ? 'var(--amber)' : 'var(--text-muted)'}">${utanBestallning}</div>
        <div class="kpi-pipe-lbl">Utan beställningsdatum</div>
        <div class="kpi-pipe-ctx">aktiva projekt</div>
      </div>
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">⏱</div>
        <div class="kpi-pipe-val" style="color:var(--cyan)">${avgBer}</div>
        <div class="kpi-pipe-lbl">Avg beredtid</div>
        <div class="kpi-pipe-ctx">dagar</div>
      </div>
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">🏗</div>
        <div class="kpi-pipe-val" style="color:var(--cyan)">${avgMont}</div>
        <div class="kpi-pipe-lbl">Avg montage-tid</div>
        <div class="kpi-pipe-ctx">dagar</div>
      </div>
      <div class="kpi-pipe-card">
        <div class="kpi-pipe-icon">⚙️</div>
        <div class="kpi-pipe-val" style="color:var(--orange)">${iMontageFas}</div>
        <div class="kpi-pipe-lbl">I montage-fas</div>
        <div class="kpi-pipe-ctx">Montage / Byggstart</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="kpi-charts kpi-charts-3col">
      <div class="kpi-chart-box">
        <div class="kpi-chart-title">Fas-fördelning</div>
        <div class="kpi-chart-inner"><canvas id="kpiFasChart"></canvas></div>
      </div>
      <div class="kpi-chart-box">
        <div class="kpi-chart-title">Arbetsbelastning per beredare</div>
        <div class="kpi-chart-inner"><canvas id="kpiBerChart"></canvas></div>
      </div>
      <div class="kpi-chart-box">
        <div class="kpi-chart-title">Montage-pipeline · 12 månader</div>
        <div class="kpi-chart-inner"><canvas id="kpiMontChart"></canvas></div>
      </div>
    </div>

    <!-- Bottom 3-col -->
    <div class="kpi-bottom kpi-bottom-3col">
      <div class="kpi-section">
        <div class="kpi-section-title">Kommande beställningsdatum</div>
        ${kommande.length === 0
          ? '<div class="kpi-empty">Inga kommande deadlines registrerade</div>'
          : kommande.map(p => dlRow(p, 'bestallningKlar')).join('')}
      </div>
      <div class="kpi-section">
        <div class="kpi-section-title">Beredning-pipeline · 12 månader</div>
        <div class="kpi-chart-inner" style="height:210px"><canvas id="kpiBerPipChart"></canvas></div>
      </div>
      <div class="kpi-section">
        <div class="kpi-section-title">Fas-fördelning per beredare</div>
        <div class="kpi-chart-inner" style="height:210px"><canvas id="kpiFasBerChart"></canvas></div>
      </div>
    </div>
  </div>`;

  // Animerade siffror
  app.querySelectorAll('.kpi-card-val[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target);
    if (target === 0) { el.textContent = '0'; return; }
    let cur = 0;
    const step = Math.max(1, Math.ceil(target / 25));
    const timer = setInterval(() => {
      cur = Math.min(cur + step, target);
      el.textContent = cur;
      if (cur >= target) clearInterval(timer);
    }, 35);
  });

  // Animerad progress-bar (läs target-pct efter DOM är satt)
  requestAnimationFrame(() => {
    app.querySelectorAll('.kpi-progress-fill[data-pct]').forEach(el => {
      el.style.width = el.dataset.pct + '%';
    });
  });

  // Chart.js
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#4a6a8a';
    Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';
    const ttOpts = { backgroundColor:'#071428', borderColor:'rgba(124,58,237,.2)', borderWidth:1, titleColor:'#e8f4ff', bodyColor:'#c8e0f8' };

    const fasCtx = document.getElementById('kpiFasChart');
    if (fasCtx) {
      new Chart(fasCtx, {
        type: 'doughnut',
        data: { labels: ANSL_FAS_ORDER, datasets: [{ data: fasData, backgroundColor: fasColors, borderColor:'#040d1e', borderWidth:3 }] },
        options: {
          responsive: true, maintainAspectRatio: false, cutout:'62%',
          plugins: {
            legend: { position:'bottom', labels:{ color:'#c8e0f8', font:{size:11}, padding:12, boxWidth:12, borderRadius:3 } },
            tooltip: { ...ttOpts }
          }
        }
      });
    }

    const berCtx = document.getElementById('kpiBerChart');
    if (berCtx && berSorted.length > 0) {
      new Chart(berCtx, {
        type: 'bar',
        data: {
          labels: berSorted.map(([n]) => n),
          datasets: [{ label:'Aktiva projekt', data: berSorted.map(([,c]) => c),
            backgroundColor: berSorted.map((_,i) => `rgba(124,58,237,${0.2+i*0.06})`),
            borderColor:'rgba(124,58,237,.6)', borderWidth:1, borderRadius:4 }]
        },
        options: {
          indexAxis:'y', responsive:true, maintainAspectRatio:false,
          plugins: { legend:{display:false}, tooltip:{...ttOpts} },
          scales: {
            x: { grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a',stepSize:1}, border:{color:'rgba(124,58,237,.12)'} },
            y: { grid:{display:false}, ticks:{color:'#c8e0f8',font:{size:12,weight:'600'}}, border:{color:'rgba(124,58,237,.12)'} }
          }
        }
      });
    } else if (berCtx) {
      berCtx.parentElement.innerHTML = '<div class="kpi-empty" style="padding:40px 0">Importera Excel med PL Sign för beredare-data</div>';
    }

    const montCtx = document.getElementById('kpiMontChart');
    if (montCtx) {
      const hasAny = montageByMonth.some(m => m.count > 0);
      if (hasAny) {
        new Chart(montCtx, {
          type: 'bar',
          data: {
            labels: montageByMonth.map(m => m.label),
            datasets: [{ label:'Montage-starter', data: montageByMonth.map(m => m.count),
              backgroundColor: montageByMonth.map(m => m.count > 0 ? 'rgba(249,115,22,.55)' : 'rgba(249,115,22,.12)'),
              borderColor: montageByMonth.map(m => m.count > 0 ? 'rgba(249,115,22,.9)' : 'rgba(249,115,22,.2)'),
              borderWidth:1, borderRadius:4 }]
          },
          options: {
            responsive:true, maintainAspectRatio:false,
            plugins: { legend:{display:false}, tooltip:{...ttOpts} },
            scales: {
              x: { grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#c8e0f8',font:{size:10}}, border:{color:'rgba(124,58,237,.12)'} },
              y: { grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a',stepSize:1}, border:{color:'rgba(124,58,237,.12)'} }
            }
          }
        });
      } else {
        montCtx.parentElement.innerHTML = '<div class="kpi-empty" style="padding:40px 0">Inga montage-datum registrerade</div>';
      }
    }

    // Beredning-pipeline per månad
    const berPipCtx = document.getElementById('kpiBerPipChart');
    if (berPipCtx) {
      const hasAny = beredningByMonth.some(m => m.count > 0);
      if (hasAny) {
        new Chart(berPipCtx, {
          type: 'bar',
          data: {
            labels: beredningByMonth.map(m => m.label),
            datasets: [{ label:'Beredning-starter', data: beredningByMonth.map(m => m.count),
              backgroundColor: beredningByMonth.map(m => m.count > 0 ? 'rgba(59,130,246,.55)' : 'rgba(59,130,246,.10)'),
              borderColor:     beredningByMonth.map(m => m.count > 0 ? 'rgba(59,130,246,.9)'  : 'rgba(59,130,246,.2)'),
              borderWidth:1, borderRadius:4 }]
          },
          options: {
            responsive:true, maintainAspectRatio:false,
            plugins: { legend:{display:false}, tooltip:{...ttOpts} },
            scales: {
              x: { grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#c8e0f8',font:{size:10}}, border:{color:'rgba(124,58,237,.12)'} },
              y: { grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a',stepSize:1}, border:{color:'rgba(124,58,237,.12)'} }
            }
          }
        });
      } else {
        berPipCtx.parentElement.innerHTML = '<div class="kpi-empty" style="padding:40px 0">Inga beredning-datum registrerade</div>';
      }
    }

    // Fas-fördelning per beredare (staplat horisontellt)
    const fasBerCtx = document.getElementById('kpiFasBerChart');
    if (fasBerCtx && berNames.length > 0) {
      new Chart(fasBerCtx, {
        type: 'bar',
        data: {
          labels: berNames,
          datasets: fasGrps.map(g => ({
            label: g.label,
            data: berNames.map(ber => data.filter(p => p.beredare === ber && g.faser.includes(p.fas)).length),
            backgroundColor: g.color,
            borderWidth: 0,
            borderRadius: 2,
          }))
        },
        options: {
          indexAxis:'y', responsive:true, maintainAspectRatio:false,
          plugins: {
            legend: { position:'bottom', labels:{ color:'#c8e0f8', font:{size:10}, padding:10, boxWidth:10, borderRadius:2 } },
            tooltip: { ...ttOpts, mode:'index', intersect:false }
          },
          scales: {
            x: { stacked:true, grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a',stepSize:1}, border:{color:'rgba(124,58,237,.12)'} },
            y: { stacked:true, grid:{display:false}, ticks:{color:'#c8e0f8',font:{size:11,weight:'600'}}, border:{color:'rgba(124,58,237,.12)'} }
          }
        }
      });
    } else if (fasBerCtx) {
      fasBerCtx.parentElement.innerHTML = '<div class="kpi-empty" style="padding:40px 0">Importera Excel med PL Sign för beredare-data</div>';
    }
  }
}

// ================================================================
// RAPPORT — Rapportgenerator
// ================================================================
async function renderRapport(app) {
  await anslLoadFromApi();
  const data = AnslState.projekt !== null ? AnslState.projekt : ANSL_SAMPLE;
  const today = new Date();

  let rptType        = 'status';
  let rptBeredare    = 'alla';
  let statusBeredare = 'alla';
  let sortCol        = null;
  let sortDir        = 1;

  const allBeredare = [...new Set(data.filter(p=>p.beredare).map(p=>p.beredare))].sort();

  function getRows() {
    let d = [...data];
    if (rptType === 'deadline') {
      d = d.filter(p => p.bestallningKlar).sort((a,b)=>a.bestallningKlar.localeCompare(b.bestallningKlar));
    } else if (rptType === 'beredare') {
      if (rptBeredare !== 'alla') d = d.filter(p=>p.beredare===rptBeredare);
      d = d.sort((a,b)=>(a.beredare||'').localeCompare(b.beredare||''));
    } else {
      if (statusBeredare !== 'alla') d = d.filter(p=>p.beredare===statusBeredare);
      d = d.sort((a,b)=>ANSL_FAS_ORDER.indexOf(a.fas)-ANSL_FAS_ORDER.indexOf(b.fas));
    }
    if (sortCol) {
      d = d.sort((a,b) => {
        if (sortCol === 'fas') {
          return (ANSL_FAS_ORDER.indexOf(a.fas) - ANSL_FAS_ORDER.indexOf(b.fas)) * sortDir;
        }
        const av = String(a[sortCol]||''), bv = String(b[sortCol]||'');
        return av.localeCompare(bv, 'sv') * sortDir;
      });
    }
    return d;
  }

  const RPT_COLS = {
    status:   [['IB nr','id'],['Projektnamn','namn'],['Fas','fas'],['Beredare','beredare'],['Montage start','montStart'],['Beställning klar','bestallningKlar'],['Blockering','blockering']],
    deadline: [['Beställning klar','bestallningKlar'],['IB nr','id'],['Projektnamn','namn'],['Beredare','beredare'],['Montage start','montStart'],['Fas','fas']],
    beredare: [['Beredare','beredare'],['IB nr','id'],['Projektnamn','namn'],['Fas','fas'],['Montage start','montStart'],['Beställning klar','bestallningKlar']],
  };

  function bindTableSort() {
    app.querySelectorAll('.rpt-th-sort').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (sortCol === col) sortDir *= -1;
        else { sortCol = col; sortDir = 1; }
        app.querySelector('.rpt-table-wrap').innerHTML = buildTable(getRows());
        bindTableSort();
      });
    });
  }

  function buildTable(rows) {
    if (!rows.length) return '<div class="rpt-empty">Inga projekt matchade</div>';
    const cols = RPT_COLS[rptType];
    return `<table class="rpt-table">
      <thead><tr>${cols.map(([lbl,k]) => {
        const active = sortCol === k;
        const arrow  = active ? (sortDir === 1 ? ' ↑' : ' ↓') : '';
        return `<th class="rpt-th-sort${active?' rpt-th-active':''}" data-col="${k}">${lbl}${arrow}</th>`;
      }).join('')}</tr></thead>
      <tbody>${rows.map(p => `<tr class="${p.blockering ? 'rpt-row-blocked' : ''}">
        ${cols.map(([,k]) => {
          const val = String(p[k] || '–');
          if (k === 'fas') {
            const fc = ANSL_FAS_C[val] || '#4a6a8a';
            return `<td><span class="rpt-fas-badge" style="background:${fc}22;color:${fc};border-color:${fc}44">${escHtml(val)}</span></td>`;
          }
          if (k === 'blockering' && val !== '–') {
            return `<td class="rpt-td-blocked">${escHtml(val)}</td>`;
          }
          return `<td>${escHtml(val)}</td>`;
        }).join('')}
      </tr>`).join('')}</tbody>
    </table>`;
  }

  function buildSummary(rows) {
    if (rptType !== 'status' || rows.length === 0) return '';
    const total = rows.length;
    const fasStats = ANSL_FAS_ORDER.map(fas => {
      const count = rows.filter(p => p.fas === fas).length;
      return { fas, count, pct: total > 0 ? Math.round(count / total * 100) : 0, color: ANSL_FAS_C[fas] || '#4a6a8a' };
    }).filter(s => s.count > 0);
    const withBlk   = rows.filter(p => p.blockering).length;
    const utanBer   = rows.filter(p => !p.beredare).length;
    return `<div class="rpt-summary">
      <div class="rpt-sum-left">
        <div class="rpt-sum-total-num">${total}</div>
        <div class="rpt-sum-total-lbl">ärenden totalt</div>
        <div class="rpt-sum-chips">
          ${withBlk > 0 ? `<span class="rpt-sum-chip rpt-chip-red">⚠ ${withBlk} blockerade</span>` : ''}
          ${utanBer > 0 ? `<span class="rpt-sum-chip rpt-chip-amber">👤 ${utanBer} utan beredare</span>` : ''}
        </div>
      </div>
      <div class="rpt-sum-right">
        ${fasStats.map(s => `
          <div class="rpt-sum-row">
            <span class="rpt-sum-dot" style="background:${s.color}"></span>
            <span class="rpt-sum-name">${escHtml(s.fas)}</span>
            <div class="rpt-sum-bar-wrap">
              <div class="rpt-sum-bar-fill" style="width:${s.pct}%;background:${s.color}"></div>
            </div>
            <span class="rpt-sum-count">${s.count}</span>
            <span class="rpt-sum-pct">${s.pct}%</span>
          </div>`).join('')}
      </div>
    </div>`;
  }

  const typeLabels = { status:'Statusrapport', deadline:'Deadline-rapport', beredare:'Beredare-rapport' };

  function rebuild() {
    const rows = getRows();
    const lbl  = typeLabels[rptType];
    app.innerHTML = `
    <div class="rpt-root">
      <div class="rpt-sidebar">
        <div class="rpt-sidebar-logo">📄</div>
        <div class="rpt-sidebar-heading">Rapporttyp</div>
        <button class="rpt-type-btn${rptType==='status'?' rpt-type-on':''}" data-rtype="status">
          <span class="rpt-btn-icon">📊</span>Statusrapport
        </button>
        <button class="rpt-type-btn${rptType==='deadline'?' rpt-type-on':''}" data-rtype="deadline">
          <span class="rpt-btn-icon">📅</span>Deadline-rapport
        </button>
        <button class="rpt-type-btn${rptType==='beredare'?' rpt-type-on':''}" data-rtype="beredare">
          <span class="rpt-btn-icon">👷</span>Beredare-rapport
        </button>

        ${rptType==='status'?`
        <div class="rpt-sidebar-heading" style="margin-top:20px">Filtrera</div>
        <select class="rpt-ber-sel" id="rptStatusBerSel">
          <option value="alla">Alla beredare</option>
          ${allBeredare.map(b=>`<option value="${escHtml(b)}"${statusBeredare===b?' selected':''}>${escHtml(b)}</option>`).join('')}
        </select>`:''}

        ${rptType==='beredare'?`
        <div class="rpt-sidebar-heading" style="margin-top:20px">Filtrera</div>
        <select class="rpt-ber-sel" id="rptBerSel">
          <option value="alla">Alla beredare</option>
          ${allBeredare.map(b=>`<option value="${escHtml(b)}"${rptBeredare===b?' selected':''}>${escHtml(b)}</option>`).join('')}
        </select>`:''}

        <div class="rpt-sidebar-divider"></div>
        <div class="rpt-sidebar-heading">Exportera</div>
        <button class="btn btn-primary rpt-export-btn" id="rptXlsBtn">⬇ Excel (.xlsx)</button>
        <button class="btn btn-navy rpt-export-btn" id="rptPrintBtn">🖨 Skriv ut / PDF</button>
      </div>

      <div class="rpt-preview">
        <div class="rpt-preview-hdr">
          <div class="rpt-preview-title">${lbl}</div>
          <div class="rpt-preview-meta">${rows.length} rader · ${today.toLocaleDateString('sv-SE', {day:'numeric',month:'long',year:'numeric'})}</div>
        </div>
        ${buildSummary(rows)}
        <div class="rpt-table-wrap">${buildTable(rows)}</div>
      </div>
    </div>`;

    bindTableSort();
    app.querySelectorAll('[data-rtype]').forEach(b => b.addEventListener('click', () => { rptType=b.dataset.rtype; rptBeredare='alla'; statusBeredare='alla'; sortCol=null; sortDir=1; rebuild(); }));
    app.querySelector('#rptBerSel')?.addEventListener('change', e => { rptBeredare=e.target.value; app.querySelector('.rpt-table-wrap').innerHTML=buildTable(getRows()); bindTableSort(); });
    app.querySelector('#rptStatusBerSel')?.addEventListener('change', e => { statusBeredare=e.target.value; rebuild(); });

    document.getElementById('rptXlsBtn')?.addEventListener('click', () => {
      if (typeof XLSX === 'undefined') { toast('SheetJS saknas','error'); return; }
      const cols = RPT_COLS[rptType];
      const ws = XLSX.utils.json_to_sheet(getRows().map(p => Object.fromEntries(cols.map(([lbl,k])=>[lbl,p[k]||'']))));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, typeLabels[rptType]);
      XLSX.writeFile(wb, `${rptType}_rapport_${today.toISOString().slice(0,10)}.xlsx`);
      toast('Excel-fil exporterad ✓','success');
    });

    document.getElementById('rptPrintBtn')?.addEventListener('click', () => window.print());
  }

  rebuild();
}

// ================================================================
// STATISTIK — Faktureringsstatistik
// ================================================================
const StatState = { allData: null };

async function statLoadFromApi() {
  if (StatState.allData !== null) return;
  try {
    const r = await api('GET', '/fakturering');
    StatState.allData = r.rader || [];
  } catch { StatState.allData = []; }
}

async function renderStatistik(app) {
  await statLoadFromApi();

  // Alla tillgängliga månader
  const allManader = [...new Set((StatState.allData||[]).map(r=>r.manad))].sort().reverse();
  let valdManad = allManader[0] || null;

  function getManadData() {
    if (!valdManad) return [];
    return (StatState.allData||[]).filter(r => r.manad === valdManad);
  }

  function fmtKr(n) {
    return Math.round(n).toLocaleString('sv-SE') + ' kr';
  }
  function fmtPct(n) {
    return n.toFixed(1) + '%';
  }

  function buildContent() {
    const rows = getManadData();
    const totalVerkl = rows.reduce((s,r)=>s+r.verklIntakt,0);
    const totalKostn = rows.reduce((s,r)=>s+(r.verklKostn||0),0);
    const totalBudg  = rows.reduce((s,r)=>s+r.budgIntakt,0);
    const totalBudgKostn = rows.reduce((s,r)=>s+(r.budgKostn||0),0);
    const totalUte   = rows.reduce((s,r)=>s+r.utestående,0);
    const totalPct   = totalBudg > 0 ? ((totalBudg-totalBudgKostn)/totalBudg*100) : 0;
    const antalProjekt = rows.length;

    // Per projektledare
    const plMap = {};
    rows.forEach(r => {
      const pl = r.projektledare || 'Okänd';
      if (!plMap[pl]) plMap[pl] = { verkl:0, kostn:0, budg:0, budgKostn:0, ute:0, count:0 };
      plMap[pl].verkl += r.verklIntakt;
      plMap[pl].kostn += r.verklKostn || 0;
      plMap[pl].budg  += r.budgIntakt;
      plMap[pl].budgKostn += r.budgKostn || 0;
      plMap[pl].ute   += r.utestående;
      plMap[pl].count++;
    });
    const plSorted = Object.entries(plMap).sort((a,b)=>b[1].verkl-a[1].verkl);

    // Månadshistorik (alla månader, summerat)
    const manadHistorik = allManader.slice().reverse().map(m => {
      const md = (StatState.allData||[]).filter(r=>r.manad===m);
      return { manad: m, verkl: md.reduce((s,r)=>s+r.verklIntakt,0), budg: md.reduce((s,r)=>s+r.budgIntakt,0) };
    });

    const manadLabels = {
      '01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'Maj','06':'Jun',
      '07':'Jul','08':'Aug','09':'Sep','10':'Okt','11':'Nov','12':'Dec'
    };
    function manadLbl(ym) {
      const [y,m] = ym.split('-');
      return `${manadLabels[m]||m} ${y}`;
    }

    const plColors = [
      'rgba(124,58,237,.7)','rgba(249,115,22,.7)','rgba(16,185,129,.7)',
      'rgba(155,89,182,.7)','rgba(239,68,68,.7)','rgba(245,158,11,.7)'
    ];

    return `
    <div class="stat-content">

      <!-- KPI Cards -->
      <div class="stat-cards">
        <div class="stat-card stat-card-cyan">
          <div class="stat-card-icon">💰</div>
          <div class="stat-card-val">${Math.round(totalVerkl).toLocaleString('sv-SE')}</div>
          <div class="stat-card-unit">kr</div>
          <div class="stat-card-lbl">Fakturerat totalt</div>
          <div class="stat-card-accent stat-accent-cyan"></div>
        </div>
        <div class="stat-card stat-card-orange">
          <div class="stat-card-icon">⏳</div>
          <div class="stat-card-val">${Math.round(totalUte).toLocaleString('sv-SE')}</div>
          <div class="stat-card-unit">kr</div>
          <div class="stat-card-lbl">Utestående inkl. moms</div>
          <div class="stat-card-accent stat-accent-orange"></div>
        </div>
        <div class="stat-card stat-card-blue">
          <div class="stat-card-icon">📋</div>
          <div class="stat-card-val">${Math.round(totalBudg).toLocaleString('sv-SE')}</div>
          <div class="stat-card-unit">kr</div>
          <div class="stat-card-lbl">Total budget</div>
          <div class="stat-card-accent stat-accent-blue"></div>
        </div>
        <div class="stat-card ${totalPct >= 15 ? 'stat-card-green' : totalPct >= 0 ? 'stat-card-cyan' : 'stat-card-orange'}">
          <div class="stat-card-icon">📈</div>
          <div class="stat-card-val">${totalPct.toFixed(1)}</div>
          <div class="stat-card-unit">%</div>
          <div class="stat-card-lbl">Utfall (budg. marginal)</div>
          <div class="stat-card-progress-wrap"><div class="stat-card-progress-fill" style="width:${Math.max(0,Math.min(totalPct,100))}%"></div></div>
          <div class="stat-card-accent ${totalPct >= 15 ? 'stat-accent-green' : totalPct >= 0 ? 'stat-accent-cyan' : 'stat-accent-orange'}"></div>
        </div>
        <div class="stat-card stat-card-muted">
          <div class="stat-card-icon">📁</div>
          <div class="stat-card-val">${antalProjekt}</div>
          <div class="stat-card-unit">st</div>
          <div class="stat-card-lbl">Projekt i perioden</div>
          <div class="stat-card-accent stat-accent-muted"></div>
        </div>
      </div>

      ${allManader.length > 1 ? `
      <!-- Månadshistorik chart -->
      <div class="stat-section">
        <div class="stat-section-title">Fakturering per månad</div>
        <div class="stat-chart-wrap"><canvas id="statManadChart"></canvas></div>
      </div>` : ''}

      <!-- Per projektledare -->
      <div class="stat-section">
        <div class="stat-section-title">Per projektledare</div>
        <div class="stat-pl-grid">
          ${plSorted.map(([pl,v],i) => {
            const pct = v.budg > 0 ? ((v.budg-v.budgKostn)/v.budg*100) : 0;
            const barW = Math.max(0, Math.min(pct, 100));
            const c = pct >= 15 ? 'rgba(16,185,129,.8)' : pct >= 0 ? plColors[i % plColors.length] : 'rgba(239,68,68,.8)';
            return `<div class="stat-pl-card">
              <div class="stat-pl-name">${escHtml(pl)}</div>
              <div class="stat-pl-count">${v.count} projekt</div>
              <div class="stat-pl-row">
                <span class="stat-pl-lbl">Fakturerat (intäkt)</span>
                <span class="stat-pl-val stat-cyan">${fmtKr(v.verkl)}</span>
              </div>
              <div class="stat-pl-row">
                <span class="stat-pl-lbl">Verklig kostnad</span>
                <span class="stat-pl-val stat-muted">${fmtKr(v.kostn)}</span>
              </div>
              <div class="stat-pl-row">
                <span class="stat-pl-lbl">Utestående</span>
                <span class="stat-pl-val stat-orange">${fmtKr(v.ute)}</span>
              </div>
              <div class="stat-pl-bar-wrap">
                <div class="stat-pl-bar-fill" style="width:${barW}%;background:${c}"></div>
              </div>
              <div class="stat-pl-pct" style="color:${c}">Utfall ${fmtPct(pct)} (budg. marginal)</div>
            </div>`;
          }).join('')}
        </div>
        <div class="stat-chart-wrap" style="height:${Math.max(200, plSorted.length*40+60)}px; margin-top:20px">
          <canvas id="statPlChart"></canvas>
        </div>
      </div>

      <!-- Per ärende -->
      <div class="stat-section">
        <div class="stat-section-title">Per ärende</div>
        <div class="stat-table-wrap">
          <table class="stat-table">
            <thead><tr>
              <th>Projektnamn</th>
              <th>Projektledare</th>
              <th class="stat-num">Fakturerat</th>
              <th class="stat-num">Budget</th>
              <th class="stat-num">Utestående</th>
              <th class="stat-num">Utfall %</th>
              <th class="stat-num">Färdigt %</th>
            </tr></thead>
            <tbody>
              ${rows.sort((a,b)=>b.verklIntakt-a.verklIntakt).map(r => {
                const pct = r.budgIntakt > 0 ? ((r.budgIntakt-(r.budgKostn||0))/r.budgIntakt*100) : 0;
                const pctCls = pct >= 15 ? 'stat-green' : pct >= 0 ? 'stat-cyan' : 'stat-orange';
                const fardCls = r.fardigt >= 90 ? 'stat-green' : r.fardigt >= 50 ? 'stat-cyan' : 'stat-muted';
                return `<tr>
                  <td class="stat-namn">${escHtml(r.projektnamn)}</td>
                  <td>${escHtml(r.projektledare)}</td>
                  <td class="stat-num stat-cyan">${fmtKr(r.verklIntakt)}</td>
                  <td class="stat-num stat-muted">${fmtKr(r.budgIntakt)}</td>
                  <td class="stat-num stat-orange">${fmtKr(r.utestående)}</td>
                  <td class="stat-num ${pctCls}">${fmtPct(pct)}</td>
                  <td class="stat-num ${fardCls}">${r.fardigt.toFixed(1)}%</td>
                </tr>`;
              }).join('')}
            </tbody>
            <tfoot><tr>
              <td colspan="2"><strong>TOTALT</strong></td>
              <td class="stat-num stat-cyan"><strong>${fmtKr(totalVerkl)}</strong></td>
              <td class="stat-num stat-muted"><strong>${fmtKr(totalBudg)}</strong></td>
              <td class="stat-num stat-orange"><strong>${fmtKr(totalUte)}</strong></td>
              <td class="stat-num"><strong>${fmtPct(totalPct)}</strong></td>
              <td class="stat-num"></td>
            </tr></tfoot>
          </table>
        </div>
      </div>
    </div>`;
  }

  function buildCharts(rows) {
    if (typeof Chart === 'undefined') return;
    const ttOpts = { backgroundColor:'#071428', borderColor:'rgba(124,58,237,.2)', borderWidth:1, titleColor:'#e8f4ff', bodyColor:'#c8e0f8' };
    Chart.defaults.color = '#4a6a8a';
    Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';

    // Månadshistorik
    const manadCtx = document.getElementById('statManadChart');
    if (manadCtx) {
      const allManaderAsc = [...new Set((StatState.allData||[]).map(r=>r.manad))].sort();
      const manadLabels = {'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'Maj','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Okt','11':'Nov','12':'Dec'};
      const mkLbl = ym => { const [y,m]=ym.split('-'); return `${manadLabels[m]||m} ${y}`; };
      const verklData = allManaderAsc.map(m => (StatState.allData||[]).filter(r=>r.manad===m).reduce((s,r)=>s+r.verklIntakt,0));
      const budgData  = allManaderAsc.map(m => (StatState.allData||[]).filter(r=>r.manad===m).reduce((s,r)=>s+r.budgIntakt,0));
      new Chart(manadCtx, {
        type:'bar',
        data:{ labels: allManaderAsc.map(mkLbl),
          datasets:[
            { label:'Fakturerat', data:verklData, backgroundColor:'rgba(124,58,237,.55)', borderColor:'rgba(124,58,237,.9)', borderWidth:1, borderRadius:4 },
            { label:'Budget',     data:budgData,  backgroundColor:'rgba(249,115,22,.3)', borderColor:'rgba(249,115,22,.6)', borderWidth:1, borderRadius:4 }
          ]},
        options:{ responsive:true, maintainAspectRatio:false,
          plugins:{ legend:{ position:'top', labels:{ color:'#c8e0f8', font:{size:11}, boxWidth:12 } }, tooltip:{...ttOpts} },
          scales:{
            x:{ grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#c8e0f8'}, border:{color:'rgba(124,58,237,.12)'} },
            y:{ grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a', callback:v=>Math.round(v).toLocaleString('sv-SE')+' kr'}, border:{color:'rgba(124,58,237,.12)'} }
          }
        }
      });
    }

    // Per projektledare - horisontellt grupperat
    const plCtx = document.getElementById('statPlChart');
    if (plCtx) {
      const plMap = {};
      rows.forEach(r => {
        const pl = r.projektledare||'Okänd';
        if (!plMap[pl]) plMap[pl]={verkl:0,budg:0,ute:0};
        plMap[pl].verkl+=r.verklIntakt; plMap[pl].budg+=r.budgIntakt; plMap[pl].ute+=r.utestående;
      });
      const plSorted = Object.entries(plMap).sort((a,b)=>b[1].verkl-a[1].verkl);
      new Chart(plCtx, {
        type:'bar',
        data:{ labels: plSorted.map(([n])=>n),
          datasets:[
            { label:'Fakturerat', data:plSorted.map(([,v])=>v.verkl), backgroundColor:'rgba(124,58,237,.55)', borderColor:'rgba(124,58,237,.9)', borderWidth:1, borderRadius:4 },
            { label:'Budget',     data:plSorted.map(([,v])=>v.budg),  backgroundColor:'rgba(249,115,22,.3)', borderColor:'rgba(249,115,22,.6)', borderWidth:1, borderRadius:4 },
            { label:'Utestående', data:plSorted.map(([,v])=>v.ute),   backgroundColor:'rgba(239,68,68,.4)',  borderColor:'rgba(239,68,68,.7)',   borderWidth:1, borderRadius:4 }
          ]},
        options:{ indexAxis:'y', responsive:true, maintainAspectRatio:false,
          plugins:{ legend:{ position:'top', labels:{ color:'#c8e0f8', font:{size:11}, boxWidth:12 } }, tooltip:{...ttOpts, callbacks:{ label: ctx => `${ctx.dataset.label}: ${Math.round(ctx.raw).toLocaleString('sv-SE')} kr` }} },
          scales:{
            x:{ grid:{color:'rgba(124,58,237,.07)'}, ticks:{color:'#4a6a8a', callback:v=>Math.round(v).toLocaleString('sv-SE')}, border:{color:'rgba(124,58,237,.12)'} },
            y:{ grid:{display:false}, ticks:{color:'#c8e0f8',font:{size:12,weight:'600'}}, border:{color:'rgba(124,58,237,.12)'} }
          }
        }
      });
    }
  }

  function rebuild() {
    const rows = getManadData();
    const manadLabels = {'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'Maj','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Okt','11':'Nov','12':'Dec'};
    function mkLbl(ym) { if (!ym) return ''; const [y,m]=ym.split('-'); return `${manadLabels[m]||m} ${y}`; }

    app.innerHTML = `
    <div class="stat-root">
      <div class="stat-header">
        <div>
          <div class="stat-header-title">Faktureringsstatistik</div>
          <div class="stat-header-sub">${valdManad ? mkLbl(valdManad) : 'Ingen data importerad'} · ${getManadData().length} projekt</div>
        </div>
        <div class="stat-toolbar">
          ${allManader.length > 0 ? `
          <select class="stat-manad-sel" id="statManadSel">
            ${allManader.map(m=>`<option value="${m}"${m===valdManad?' selected':''}>${mkLbl(m)}</option>`).join('')}
          </select>` : ''}
          <label class="btn btn-primary stat-import-btn" style="cursor:pointer">
            ⬆ Importera Excel
            <input type="file" id="statFileInput" accept=".xlsx,.xls" style="display:none">
          </label>
          ${valdManad ? `<button class="btn btn-danger btn-sm" id="statDelBtn">🗑 Ta bort ${mkLbl(valdManad)}</button>` : ''}
        </div>
      </div>

      ${allManader.length === 0 ? `
        <div class="stat-empty">
          <div class="stat-empty-icon">📊</div>
          <div class="stat-empty-title">Ingen data importerad</div>
          <div class="stat-empty-sub">Klicka på "Importera Excel" och välj din faktureringsrapport.<br>Du väljer vilken månad rapporten gäller vid importen.</div>
        </div>` : buildContent()}
    </div>`;

    // Bind events
    document.getElementById('statManadSel')?.addEventListener('change', e => { valdManad=e.target.value; rebuild(); });

    document.getElementById('statFileInput')?.addEventListener('change', async e => {
      const file = e.target.files[0]; if (!file) return;
      // Månadsväljare
      const now = new Date();
      const defaultManad = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
      const vald = prompt(`Vilken månad gäller den här rapporten?\nFormat: ÅÅÅÅ-MM (t.ex. ${defaultManad})`, defaultManad);
      if (!vald || !/^\d{4}-\d{2}$/.test(vald.trim())) { toast('Ogiltigt månadsformat — använd ÅÅÅÅ-MM', 'error'); return; }
      const manad = vald.trim();

      // Läs Excel med SheetJS
      try {
        const ab = await file.arrayBuffer();
        const wb = XLSX.read(ab, { type:'array' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const rawRows = XLSX.utils.sheet_to_json(ws, { defval:'' });

        const projekt = rawRows.map(r => {
          const pl = String(r['Projektledare']||'').trim();
          // Ta bort (SWEDCARL) suffix
          const plNamn = pl.replace(/\s*\([^)]+\)$/, '').trim();
          return {
            id:            String(r['Projektnummer']||'').trim(),
            projektnamn:   String(r['Projektnamn']||'').trim(),
            projektledare: plNamn,
            utestående:    parseFloat(r['Utestående inkl VAT']||r['Utestående inkl. VAT']||r['Utestående']||0)||0,
            verklIntakt:   parseFloat(r['Tot. verkl. intäkt']||r['Tot. verkl. inktakt']||0)||0,
            verklKostn:    parseFloat(r['Tot. verkl. kostn.']||r['Tot. verkl. kostn']||0)||0,
            budgIntakt:    parseFloat(r['Tot. budgeterad intäkt']||0)||0,
            budgKostn:     parseFloat(r['Tot. budgeterad kostn.']||r['Tot. budgeterad kostn']||0)||0,
            fardigt:       parseFloat(r['Färdigt (%)']||r['Fardigt (%)']||0)||0,
          };
        }).filter(p => p.id && p.id !== 'Projektnummer');

        if (projekt.length === 0) { toast('Inga projekt hittades i filen', 'error'); return; }

        await api('POST', '/fakturering/import', { manad, projekt });
        StatState.allData = null; // rensa cache
        await statLoadFromApi();
        valdManad = manad;
        toast(`${projekt.length} projekt importerade för ${manad} ✓`, 'success');
        rebuild();
        setTimeout(() => buildCharts(getManadData()), 50);
      } catch(err) { toast('Fel vid import: ' + err.message, 'error'); }
    });

    document.getElementById('statDelBtn')?.addEventListener('click', async () => {
      if (!valdManad) return;
      const ok = await confirm('Ta bort period', `Ta bort all data för ${mkLbl(valdManad)}?`, 'Ta bort');
      if (!ok) return;
      try {
        await api('DELETE', `/fakturering/${valdManad}`);
        StatState.allData = null;
        await statLoadFromApi();
        valdManad = allManader.filter(m=>m!==valdManad)[0] || null;
        toast('Period borttagen', 'success');
        rebuild();
      } catch(err) { toast('Fel: '+err.message, 'error'); }
    });

    if (allManader.length > 0) {
      setTimeout(() => buildCharts(getManadData()), 50);
    }
  }

  rebuild();
}

// ----------------------------------------------------------------
// BOOT
// ----------------------------------------------------------------
// ================================================================
// PROJEKTPLANERING – statusfält (Beredning + Tjällmo), Kabeltrummor
// ================================================================
const BEREDNING_FALT = [
  {key:'planerad_schakt', label:'Planerad schakt', typ:'datum'},
  {key:'bestallning_klar_datum', label:'Beställning klar datum', typ:'datum'},
  {key:'skapat_pwb', label:'Skapat i PWB', typ:'dropdown', alt:['Ja','Nej']},
  {key:'uppstart_beredning', label:'Uppstart beredning', typ:'dropdown', alt:['Ja','Nej']},
  {key:'ledningskoll_projektering', label:'Ledningskoll Projektering', typ:'text'},
  {key:'vaghallare_markagare', label:'Väghållare/Markägare OK', typ:'dropdown', alt:['Ja','Nej','Ej aktuellt']},
  {key:'trafikverket', label:'Trafikverket', typ:'text', alt:['Ej aktuellt','Behövs']},
  {key:'gravtillstand_kommun', label:'Grävtillstånd Kommun', typ:'dropdown', alt:['Ej aktuellt','Ska sökas','Beviljad','Behövs']},
  {key:'lansstyrelsen', label:'Länsstyrelsen', typ:'dropdown', alt:['Ej aktuellt','Ska sökas','Beviljad']},
  {key:'kalkyl_klar', label:'Kalkyl klar', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'budget_pbw', label:'Budget skapad i PBW', typ:'dropdown', alt:['Beredning','Påbörjad','Ja']},
  {key:'material_byggprotokoll', label:'Material / Byggprotokoll', typ:'dropdown', alt:['Påbörjad','Ej aktuellt','Ja']},
  {key:'ta_plan', label:'TA-plan framtagen', typ:'dropdown', alt:['Ej aktuellt','Extern','Påbörjad','Ja']},
  {key:'kalkyl_projektnavet', label:'Kalkyl i projektnavet', typ:'dropdown', alt:['Påbörjad','Inskickad','Tillstyrkt']},
  {key:'ledningskoll_utsattning', label:'Ledningskoll Utsättning', typ:'text', alt:['Inväntar utförande']},
  {key:'fset_klar', label:'F-set klar', typ:'dropdown', alt:['Påbörjad','Inskickad','Postad']},
  {key:'hsseq_plan', label:'HSSEQ Plan klar', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'flikars_15', label:'15-Flikars', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'bestallare_eon', label:'Beställare EON', typ:'text'},
  {key:'montage_start', label:'Montage start', typ:'text'},
  {key:'uppskattat_tid_falt', label:'Uppskattat tid i fält', typ:'text'},
  {key:'avbrott', label:'Avbrott', typ:'dropdown', alt:['Nej','Ja']},
  {key:'bestallning_klar', label:'Beställning klar', typ:'dropdown', alt:['Påbörjad','Klar']},
];
const TJALLMO_FALT = [
  {key:'planerad_schakt', label:'Planerad schakt', typ:'datum'},
  {key:'status_fakturering', label:'Status fakturering', typ:'dropdown', alt:['Påbörjad','Godkänd slutbesiktning','Fakturerad 90%','Slutfakturerad']},
  {key:'prio', label:'Prio', typ:'text'},
  {key:'kraver_montor', label:'Kräver montör', typ:'dropdown', alt:['Ja','Nej']},
  {key:'beredning_klar', label:'Beredning klar', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'trafikverket', label:'Trafikverket', typ:'text', alt:['Ej aktuellt','Behövs']},
  {key:'gravtillstand_kommun', label:'Grävtillstånd Kommun', typ:'dropdown', alt:['Ej aktuellt','Ska sökas','Beviljad','Behövs']},
  {key:'lansstyrelsen', label:'Länsstyrelsen', typ:'dropdown', alt:['Ej aktuellt','Ska sökas','Beviljad']},
  {key:'kabelbestallning', label:'Kabelbeställning', typ:'dropdown', alt:['Tas med av Tjällmo','Beställt på plats','Hämtas OneCo']},
  {key:'ta_plan', label:'TA-plan framtagen', typ:'dropdown', alt:['Ej aktuellt','Extern','Påbörjad','Ja']},
  {key:'materialbestallning', label:'Materialbeställning', typ:'dropdown', alt:['Hämtas OneCo','Beställt på plats','Beställt Tjällmo']},
  {key:'ledningskoll_utsattning', label:'Ledningskoll Utsättning', typ:'text'},
  {key:'gravlag', label:'Grävlag', typ:'dropdown', alt:['Linus Jarmyr','Johanna Kambrink','Rasmus Eklöf','Julia Svensson','Peder Eneman']},
  {key:'inmatning', label:'Inmätning', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'dagbok', label:'Dagbok', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'aterstallning', label:'Återställning', typ:'dropdown', alt:['Påbörjad','Klar']},
  {key:'montage_start', label:'Montage start', typ:'text'},
  {key:'uppskattat_tid_falt', label:'Uppskattat tid i fält', typ:'text'},
  {key:'avbrott', label:'Avbrott', typ:'dropdown', alt:['Nej','Ja']},
  {key:'bestallning_klar', label:'Beställning klar', typ:'dropdown', alt:['Påbörjad','Klar']},
];

function statusInputHtml(f, val) {
  val = val || '';
  if (f.typ === 'datum')
    return `<input type="date" class="form-control status-inp" data-key="${f.key}" value="${escHtml(val)}">`;
  if (f.typ === 'dropdown') {
    const opts = [...(f.alt || [])];
    if (val && !opts.includes(val)) opts.unshift(val);
    return `<select class="form-control status-inp" data-key="${f.key}">
      <option value="">–</option>
      ${opts.map(o => `<option ${o === val ? 'selected' : ''}>${escHtml(o)}</option>`).join('')}
    </select>`;
  }
  const dl = f.alt ? `list="dl_${f.key}"` : '';
  const datalist = f.alt ? `<datalist id="dl_${f.key}">${f.alt.map(o => `<option value="${escHtml(o)}">`).join('')}</datalist>` : '';
  return `<input type="text" class="form-control status-inp" data-key="${f.key}" value="${escHtml(val)}" ${dl} autocomplete="off">${datalist}`;
}

function statusFormHtml(falt, values, titel) {
  return `<div class="card mb-2">
    <div class="card-header"><span class="card-title">${escHtml(titel)}</span><span class="text-sm text-muted status-spar"></span></div>
    <div class="card-body">
      <div class="status-grid">
        ${falt.map(f => `<div class="status-cell">
          <label class="form-label">${escHtml(f.label)}</label>
          ${statusInputHtml(f, values[f.key])}
        </div>`).join('')}
      </div>
    </div>
  </div>`;
}

// Autospar för statusfält inom rootEl (skickar alla fält vid ändring)
function bindStatusAutospar(rootEl, pid) {
  let t = null;
  async function save() {
    const data = {};
    rootEl.querySelectorAll('.status-inp').forEach(el => { data[el.dataset.key] = el.value; });
    rootEl.querySelectorAll('.status-spar').forEach(i => { i.textContent = 'Sparar…'; i.className = 'text-sm text-muted status-spar'; });
    try {
      await api('PUT', `/projekt/${pid}/status`, data);
      rootEl.querySelectorAll('.status-spar').forEach(i => { i.textContent = 'Sparat ✓'; i.className = 'text-sm text-success status-spar'; });
    } catch (e) {
      rootEl.querySelectorAll('.status-spar').forEach(i => { i.textContent = 'Fel: ' + e.message; i.className = 'text-sm text-danger status-spar'; });
    }
  }
  rootEl.addEventListener('input', e => { if (!e.target.classList.contains('status-inp')) return; if (t) clearTimeout(t); t = setTimeout(save, 600); });
  rootEl.addEventListener('change', e => { if (!e.target.classList.contains('status-inp')) return; if (t) clearTimeout(t); save(); });
}

// Bygg HTML för status-fliken i projektdetaljen (Beredning + Tjällmo, utan dubbletter)
function projektStatusPaneHtml(status) {
  const beredKeys = new Set(BEREDNING_FALT.map(f => f.key));
  const tjallmoEgna = TJALLMO_FALT.filter(f => !beredKeys.has(f.key));
  return statusFormHtml(BEREDNING_FALT, status, 'Beredningsstatus') +
         statusFormHtml(tjallmoEgna, status, 'Tjällmo / fältstatus');
}

// ----------------------------------------------------------------
// VIEW: TJÄLLMO (fält-/UE-vy – samma projekt, fältstatusar)
// ----------------------------------------------------------------
const TJALLMO_KOLUMNER = [
  {key:'status_fakturering', label:'Fakturering'},
  {key:'beredning_klar', label:'Beredning'},
  {key:'gravlag', label:'Grävlag'},
  {key:'montage_start', label:'Montage'},
  {key:'aterstallning', label:'Återställ.'},
  {key:'bestallning_klar', label:'Best. klar'},
];

async function renderTjallmo(app) {
  if (!S.beredare.length) { try { S.beredare = (await api('GET', '/beredare')).beredare || []; } catch {} }
  let projekt = [], statusAlla = {};
  try {
    [projekt, statusAlla] = await Promise.all([
      api('GET', '/projekt').then(r => r.projekt || []),
      api('GET', '/projekt/status-alla').then(r => r.status || {}),
    ]);
  } catch (e) { toast(e.message, 'error'); }

  app.innerHTML = `
    <div class="page-header"><h1 class="page-title">Tjällmo – fältplanering</h1></div>
    <div class="filter-bar">
      <input type="search" class="form-control" id="tjSok" placeholder="🔍 Sök IB-nummer, benämning, beredare…">
      <select class="form-control" id="tjBer" style="max-width:200px">
        <option value="">Alla beredare</option>
        ${S.beredare.map(b => `<option ${S.minBeredare === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('')}
      </select>
    </div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr>
        <th>IB-nummer</th><th>Benämning</th><th>Beredare</th>
        ${TJALLMO_KOLUMNER.map(k => `<th>${escHtml(k.label)}</th>`).join('')}
      </tr></thead>
      <tbody id="tjBody"></tbody>
    </table></div></div>`;

  function rita() {
    const sok = document.getElementById('tjSok').value.trim().toLowerCase();
    const ber = document.getElementById('tjBer').value;
    const tbody = document.getElementById('tjBody');
    const rader = projekt.filter(p => {
      if (ber && p.beredare !== ber) return false;
      if (sok) {
        const hay = `${p.projektnummer} ${p.projektnamn} ${p.beredare}`.toLowerCase();
        if (!hay.includes(sok)) return false;
      }
      return true;
    });
    if (!rader.length) { tbody.innerHTML = `<tr><td colspan="${3 + TJALLMO_KOLUMNER.length}" class="muted text-center">Inga ärenden</td></tr>`; return; }
    tbody.innerHTML = rader.map(p => {
      const st = statusAlla[String(p.id)] || {};
      return `<tr style="cursor:pointer" data-id="${p.id}">
        <td><span class="mono" style="color:var(--cyan)">${escHtml(p.projektnummer)}</span></td>
        <td><strong>${escHtml(p.projektnamn)}</strong></td>
        <td>${escHtml(p.beredare || '–')}</td>
        ${TJALLMO_KOLUMNER.map(k => `<td class="text-sm">${escHtml(st[k.key] || '–')}</td>`).join('')}
      </tr>`;
    }).join('');
    tbody.querySelectorAll('tr[data-id]').forEach(tr =>
      tr.addEventListener('click', () => navigate('projekt-detail', { id: tr.dataset.id })));
  }
  document.getElementById('tjSok').addEventListener('input', rita);
  document.getElementById('tjBer').addEventListener('change', rita);
  rita();
}

// ----------------------------------------------------------------
// VIEW: KABELTRUMMOR
// ----------------------------------------------------------------
async function renderKabeltrummor(app) {
  let rader = [];
  try { rader = (await api('GET', '/kabeltrummor')).kabeltrummor || []; } catch (e) { toast(e.message, 'error'); }

  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Kabeltrummor</h1>
      <button class="btn btn-primary" id="btnNyKt">+ Ny rad</button>
    </div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>Projekt / IB-nummer</th><th>Kabeltyp</th><th class="right">Uttagen mängd</th><th class="right">Kvar på trummor</th><th>Notat</th><th>Åtgärder</th></tr></thead>
      <tbody id="ktBody"></tbody>
    </table></div></div>`;

  function rita() {
    const tbody = document.getElementById('ktBody');
    if (!rader.length) { tbody.innerHTML = `<tr><td colspan="6" class="muted text-center">Inga rader ännu. Klicka "+ Ny rad".</td></tr>`; return; }
    tbody.innerHTML = rader.map(r => `
      <tr>
        <td><strong>${escHtml(r.projekt_text || '–')}</strong></td>
        <td>${escHtml(r.kabeltyp || '–')}</td>
        <td class="num">${num(r.uttagen)}</td>
        <td class="num">${num(r.kvar)}</td>
        <td class="text-sm">${escHtml(r.notat || '')}</td>
        <td class="flex gap-1">
          <button class="btn btn-sm btn-outline" data-id="${r.id}" data-act="edit">Redigera</button>
          <button class="btn btn-sm btn-danger" data-id="${r.id}" data-act="del">Ta bort</button>
        </td>
      </tr>`).join('');
    tbody.querySelectorAll('button[data-act]').forEach(b => b.addEventListener('click', async () => {
      const r = rader.find(x => x.id == b.dataset.id);
      if (b.dataset.act === 'edit') modalKt(r);
      else {
        const ok = await confirm('Ta bort rad', `Ta bort kabeltrumma-raden för "${r.projekt_text}"?`);
        if (!ok) return;
        try { await api('DELETE', `/kabeltrummor/${r.id}`); rader = (await api('GET', '/kabeltrummor')).kabeltrummor || []; rita(); toast('Borttagen', 'success'); }
        catch (e) { toast(e.message, 'error'); }
      }
    }));
  }

  function modalKt(r) {
    Modal.open(r ? 'Redigera kabeltrumma' : 'Ny kabeltrumma', `
      <form id="ktForm">
        <div class="form-group"><label class="form-label">Projekt / IB-nummer <span class="req">*</span></label>
          <input name="projekt_text" class="form-control" value="${escHtml(r?.projekt_text || '')}" required></div>
        <div class="form-row cols-2">
          <div class="form-group"><label class="form-label">Kabeltyp</label>
            <input name="kabeltyp" class="form-control" list="ktTyper" value="${escHtml(r?.kabeltyp || '')}" placeholder="t.ex. 4G25">
            <datalist id="ktTyper"><option value="4G25"><option value="4G50"><option value="4G95"><option value="4G150"><option value="4G240"></datalist></div>
          <div class="form-group"><label class="form-label">Uttagen mängd</label>
            <input type="number" step="any" name="uttagen" class="form-control" value="${r?.uttagen ?? 0}"></div>
        </div>
        <div class="form-row cols-2">
          <div class="form-group"><label class="form-label">Kvar på trummor</label>
            <input type="number" step="any" name="kvar" class="form-control" value="${r?.kvar ?? 0}"></div>
          <div class="form-group"><label class="form-label">Notat</label>
            <input name="notat" class="form-control" value="${escHtml(r?.notat || '')}"></div>
        </div>
      </form>`,
      `<button class="btn btn-navy" id="sparaKt">Spara</button><button class="btn btn-secondary" id="avbrytKt">Avbryt</button>`
    );
    document.getElementById('avbrytKt').addEventListener('click', Modal.close);
    document.getElementById('sparaKt').addEventListener('click', async () => {
      const f = document.getElementById('ktForm');
      if (!f.reportValidity()) return;
      const body = Object.fromEntries(new FormData(f).entries());
      try {
        if (r) await api('PUT', `/kabeltrummor/${r.id}`, body);
        else   await api('POST', '/kabeltrummor', body);
        Modal.close();
        rader = (await api('GET', '/kabeltrummor')).kabeltrummor || [];
        rita(); toast('Sparad', 'success');
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  document.getElementById('btnNyKt').addEventListener('click', () => modalKt(null));
  rita();
}

async function boot() {
  // Kräv inloggning vid varje ny webbläsarsession (ny flik/fönster)
  if (!sessionStorage.getItem('logged_in')) {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    visaLoginSkarm();
    return;
  }

  // Kolla app-inloggning
  let loggedIn = false;
  let status = {};
  try {
    const r = await fetch('/api/auth/status', { credentials: 'same-origin' });
    status = await r.json();
    loggedIn = !!status.loggedin;
  } catch {}

  if (!loggedIn) { visaLoginSkarm(); return; }

  // Spara användarinfo + auto-filter på egna jobb
  S.user = status.anvandarnamn ? {
    anvandarnamn: status.anvandarnamn,
    namn:         status.namn,
    roll:         status.roll,
    beredare:     status.beredare,
  } : null;
  S.minBeredare = status.beredare || null;

  // Visa navbar och logga ut-knapp
  document.querySelector('.topnav').style.display = '';
  const navRight = document.getElementById('navRight');
  if (navRight && !navRight.querySelector('.btn-logout')) {
    if (S.user && S.user.namn) {
      const namnEl = document.createElement('span');
      namnEl.className = 'nav-user text-sm';
      namnEl.style.cssText = 'margin-right:8px;opacity:.85;white-space:nowrap';
      namnEl.textContent = `👤 ${S.user.namn}`;
      navRight.prepend(namnEl);
    }
    const logoutBtn = document.createElement('button');
    logoutBtn.className = 'btn btn-outline btn-sm btn-logout';
    logoutBtn.textContent = 'Logga ut';
    logoutBtn.addEventListener('click', async () => {
      sessionStorage.removeItem('logged_in');
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      visaLoginSkarm();
    });
    navRight.prepend(logoutBtn);
  }

  // Admin-status (från sessionen)
  if (status.admin) {
    S.admin = true;
    document.getElementById('adminBadge').classList.remove('hidden');
  } else {
    try {
      await api('GET', '/admin/check');
      S.admin = true;
      document.getElementById('adminBadge').classList.remove('hidden');
    } catch {}
  }

  const hash = location.hash.replace('#', '');
  const [view, ...rest] = hash.split('/');
  navigate(view || 'projekt', { id: rest[0] });
}

// ================================================================
// ANSLUTNINGSÄRENDEN
// ================================================================

const ANSL_SAMPLE = [
  {id:"351860",namn:"AM Ny 20A Västra spång 515",kund:"Privat",fas:"Drifttagning klar",berStart:"2026-01-05",berSlut:"2026-02-04",montStart:"2026-03-15",montSlut:"2026-03-17",driftDat:"2026-03-17",bestallningKlar:"2026-03-10",beredare:"Daniel Carlsson",blockering:null,notat:"Smidigt ärende"},
  {id:"351647",namn:"AM Ny 16A Stavshult 1:14",kund:"Privat",fas:"Drifttagning klar",berStart:"2025-11-27",berSlut:"2026-02-25",montStart:"2026-03-31",montSlut:"2026-04-13",driftDat:"2026-04-13",bestallningKlar:"2026-04-01",beredare:"Antonio Malm",blockering:null,notat:""},
  {id:"351554",namn:"AM DBO f22 N130593 utök >35A",kund:"Företag",fas:"Avslutat",berStart:"2025-11-21",berSlut:"2026-02-05",montStart:"2026-03-08",montSlut:"2026-03-09",driftDat:"2026-03-09",bestallningKlar:"2026-03-01",beredare:"Björn Nilsson",blockering:null,notat:""},
  {id:"351804",namn:"AM Ny SS25A, Svedjemarksg 8",kund:"Privat",fas:"Drifttagning klar",berStart:"2026-01-05",berSlut:"2026-03-10",montStart:"2026-04-02",montSlut:"2026-04-14",driftDat:"2026-04-14",bestallningKlar:"2026-04-05",beredare:"Daniel Carlsson",blockering:null,notat:""},
  {id:"351959",namn:"AM Återansluta Rolstorp 1139",kund:"Privat",fas:"Beredning",berStart:"2026-02-06",berSlut:"2026-04-21",montStart:"2026-05-18",montSlut:"2026-05-25",driftDat:null,bestallningKlar:"2026-05-15",beredare:"Jimmy Buch",blockering:"Avvaktar svar elnätsägare",notat:"Skickat påminnelse 3 ggr"},
  {id:"351977",namn:"AM ny 20A Saltviksv 8, Lödde",kund:"Privat",fas:"Beredning",berStart:"2026-01-13",berSlut:"2026-05-15",montStart:"2026-06-15",montSlut:"2026-06-18",driftDat:null,bestallningKlar:"2026-06-10",beredare:"Rasmus Grahn",blockering:null,notat:""},
  {id:"352017",namn:"AM-OBY-f15 nya sev.led.",kund:"Företag",fas:"Beredning",berStart:"2026-01-13",berSlut:"2026-04-28",montStart:"2026-06-01",montSlut:"2026-06-18",driftDat:null,bestallningKlar:"2026-05-28",beredare:"Antonio Malm",blockering:"Markavtal ej signerat",notat:"Ägare svår att nå"},
  {id:"352253",namn:"AM Ny 16A Åbyvägen 134200",kund:"Privat",fas:"Beredning",berStart:"2026-02-06",berSlut:"2026-05-13",montStart:"2026-05-25",montSlut:"2026-06-08",driftDat:null,bestallningKlar:"2026-06-01",beredare:"Daniel Carlsson",blockering:null,notat:""},
  {id:"351922",namn:"AM Nyan 160A+sol 55KW, Brittens Väg",kund:"Solkraft",fas:"Drifttagning klar",berStart:"2026-01-05",berSlut:"2026-03-09",montStart:"2026-04-17",montSlut:"2026-04-28",driftDat:"2026-04-28",bestallningKlar:"2026-04-20",beredare:"Björn Nilsson",blockering:null,notat:"Solinstallation"},
  {id:"352716",namn:"AM Nyansl 20A Eddavägen 15",kund:"Privat",fas:"Beredning",berStart:"2026-04-16",berSlut:"2026-05-06",montStart:"2026-06-22",montSlut:"2026-06-26",driftDat:null,bestallningKlar:"2026-06-18",beredare:"Jimmy Buch",blockering:null,notat:""},
  {id:"353227",namn:"AM-Ny 16A Ludaröd 614 Brösarp",kund:"Privat",fas:"Tidig fas",berStart:"2026-05-04",berSlut:"2026-06-01",montStart:"2026-06-08",montSlut:"2026-07-10",driftDat:null,bestallningKlar:"2026-07-01",beredare:"Rasmus Grahn",blockering:"Tekniskt underlag saknas",notat:""},
  {id:"353449",namn:"AM Ny 16A Fäladen 953",kund:"Privat",fas:"Tidig fas",berStart:"2026-05-12",berSlut:"2026-06-05",montStart:"2026-06-15",montSlut:"2026-07-03",driftDat:null,bestallningKlar:"2026-06-28",beredare:"Daniel Carlsson",blockering:null,notat:""},
  {id:"353373",namn:"AM Ny 25A Ettvägen 64 Asmundtorp",kund:"Privat",fas:"Tidig fas",berStart:"2026-05-13",berSlut:"2026-07-01",montStart:"2026-07-13",montSlut:"2026-07-17",driftDat:null,bestallningKlar:"2026-07-10",beredare:"Antonio Malm",blockering:null,notat:""},
  {id:"352549",namn:"AM BSN f25 BSN-266 utök. 600A",kund:"Industri",fas:"Beredning",berStart:"2026-03-20",berSlut:"2026-04-22",montStart:"2026-05-04",montSlut:"2026-05-29",driftDat:null,bestallningKlar:"2026-05-20",beredare:"Björn Nilsson",blockering:"Väntar på E.ON tekniskt beslut",notat:"Stor anslutning – prioritet"},
  {id:"353411",namn:"AM Ny 20A Högs skolväg 43",kund:"Offentlig",fas:"Tidig fas",berStart:"2026-05-18",berSlut:"2026-06-15",montStart:"2026-07-06",montSlut:"2026-07-31",driftDat:null,bestallningKlar:"2026-07-25",beredare:"Jimmy Buch",blockering:null,notat:""},
  {id:"351685",namn:"AM Ny 16A Skäggeris",kund:"Privat",fas:"Beredning",berStart:"2025-12-11",berSlut:"2026-04-07",montStart:"2026-05-01",montSlut:"2026-05-31",driftDat:null,bestallningKlar:"2026-05-25",beredare:"Rasmus Grahn",blockering:null,notat:""},
  {id:"353239",namn:"AM-Ny 20A Andrarum 2206 Tomelilla",kund:"Privat",fas:"Tidig fas",berStart:"2026-06-01",berSlut:"2026-07-31",montStart:"2026-08-31",montSlut:"2026-09-07",driftDat:null,bestallningKlar:"2026-09-01",beredare:"Daniel Carlsson",blockering:null,notat:""},
  {id:"352192",namn:"AM Ny 16A kamera, Kvistalånga",kund:"Offentlig",fas:"Beredning",berStart:"2026-02-06",berSlut:"2026-04-30",montStart:"2026-06-01",montSlut:"2026-08-28",driftDat:null,bestallningKlar:"2026-08-20",beredare:"Antonio Malm",blockering:"Tillstånd länsstyrelse inväntas",notat:"Naturreservat – lång handläggningstid"},
  {id:"352917",namn:"AM Ny 25A KAT1 Källstorp 5227",kund:"Privat",fas:"Tidig fas",berStart:"2026-04-19",berSlut:"2026-06-30",montStart:"2026-07-01",montSlut:"2026-07-31",driftDat:null,bestallningKlar:"2026-07-28",beredare:"Björn Nilsson",blockering:null,notat:""},
  {id:"353274",namn:"AM Ny 16A Råröd 3:1, Eslöv",kund:"Privat",fas:"Tidig fas",berStart:"2026-07-13",berSlut:"2026-08-28",montStart:"2026-10-05",montSlut:"2026-10-30",driftDat:null,bestallningKlar:"2026-10-25",beredare:"Jimmy Buch",blockering:null,notat:""},
];

const ANSL_FAS_ORDER = ["Tidig fas","Beredning","Montage","Drifttagning klar","Avslutat"];
const ANSL_FAS_C = {
  "Tidig fas":         "#4a6a8a",
  "Beredning":         "#3b82f6",
  "Montage":           "#f59e0b",
  "Drifttagning klar": "#7c3aed",
  "Avslutat":          "#10b981",
};
const ANSL_FAS_MAP = {
  "Bekräftad beställning":            "Tidig fas",
  "Aviserat uppstartsmöte beredning": "Tidig fas",
  "Anmält start av beredning":        "Beredning",
  "Uppstartsmöte beredning klart":    "Beredning",
  "Beredning inlämnad":               "Beredning",
  "Beredning tillstyrkt":             "Beredning",
  "Teknisk dokumentation överlämnad": "Montage",
  "Drifttagningsdatum godkänd":       "Drifttagning klar",
  "Besiktning aviserad":              "Drifttagning klar",
  "Projekt slutfört":                 "Avslutat",
};

const AnslState = {
  projekt:   null,
  view:      'oversikt',
  search:    '',
  filterFas: null,
  sortCol:   'montStart',
  sortDir:   1,
  calYear:   new Date().getFullYear(),
  calMonth:  new Date().getMonth(),
};

// ---------- helpers ----------
async function anslLoadFromApi() {
  if (AnslState.projekt !== null) return;
  try {
    const data = await api('GET', '/anslutning');
    AnslState.projekt = data.projekt || [];
  } catch(e) {
    AnslState.projekt = [];
    toast('Kunde inte hämta ärenden: ' + e.message, 'error');
  }
}
const anslPD  = s => s ? new Date(s) : null;
const anslFD  = s => {
  if (!s) return '–';
  const d = new Date(s);
  return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`;
};
const anslDD  = (a,b) => Math.round((b - a) / 86400000);
const anslLT  = p => { const s=anslPD(p.berStart),e=anslPD(p.driftDat); return s&&e?anslDD(s,e):null; };
const anslDTM = p => { const d=anslPD(p.montStart); return d?anslDD(new Date(),d):null; };
const anslRisk = p => {
  if (p.fas==='Avslutat'||p.fas==='Drifttagning klar') return false;
  if (p.driftDat) return false;
  const dtm = anslDTM(p);
  return (dtm!==null && dtm<21) || !!p.blockering;
};

// ---------- HTML building blocks ----------
function anslKpiHtml(label, value, sub, delta, accent) {
  const dc = delta > 0 ? 'color:#10b981' : delta < 0 ? 'color:#ef4444' : 'color:#4a6a8a';
  const ds = delta > 0 ? `+${delta}` : delta < 0 ? `${delta}` : '±0';
  const dEl = delta !== undefined
    ? `<div style="font-size:11px;font-weight:600;font-family:monospace;${dc}">${ds} vs föreg. mån</div>` : '';
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden;border-top:2px solid ${accent}">
      <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px">${label}</div>
      <div style="font-size:32px;font-weight:800;color:var(--text-strong);line-height:1;margin-bottom:4px">${value}</div>
      <div style="font-size:11px;color:var(--text-muted);font-family:monospace">${sub}</div>
      ${dEl}
    </div>`;
}

function anslPanelHtml(title, badge, content, badgeColor) {
  const badgeEl = badge
    ? `<span style="font-size:10px;font-family:monospace;padding:3px 8px;border-radius:4px;background:var(--surface-3);color:${badgeColor||'var(--text-muted)'}">${badge}</span>`
    : '';
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border)">
        <span style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)">${title}</span>
        ${badgeEl}
      </div>
      <div style="padding:16px 18px">${content}</div>
    </div>`;
}

function anslFasBarHtml(p) {
  const segs = ANSL_FAS_ORDER.map(f => {
    const n = p.filter(x=>x.fas===f).length;
    return n ? `<div style="flex:${n};background:${ANSL_FAS_C[f]};border-radius:2px" title="${f}: ${n}"></div>` : '';
  }).join('');
  const legend = ANSL_FAS_ORDER.map(f => {
    const n = p.filter(x=>x.fas===f).length;
    return `<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted)">
      <div style="width:8px;height:8px;border-radius:2px;background:${ANSL_FAS_C[f]}"></div>
      ${f}&nbsp;<span style="font-family:monospace;font-weight:500;color:var(--text)">${n}</span>
    </div>`;
  }).join('');
  return `
    <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;gap:2px;margin-bottom:14px">${segs}</div>
    <div style="display:flex;flex-wrap:wrap;gap:10px">${legend}</div>`;
}

function anslRiskListHtml(p) {
  const risks = p.filter(anslRisk);
  if (!risks.length) return `<div style="padding:32px;text-align:center;color:var(--text-muted);font-size:12px;font-family:monospace">Inga riskprojekt just nu ✓</div>`;
  const items = risks.map(r => {
    const dtm = anslDTM(r);
    const dot = r.blockering ? 'var(--red)' : 'var(--amber)';
    const dEl = dtm !== null
      ? `<div style="font-size:11px;font-family:monospace;font-weight:500;color:${dtm<14?'var(--red)':'var(--amber)'};flex-shrink:0">${dtm}d</div>` : '';
    return `
      <div style="display:flex;align-items:flex-start;gap:12px;padding:11px 0;border-bottom:1px solid var(--border)">
        <div style="width:6px;height:6px;border-radius:50%;background:${dot};flex-shrink:0;margin-top:5px"></div>
        <div style="flex:1;min-width:0">
          <div style="font-size:12px;font-weight:600;color:var(--text-strong);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px">${escHtml(r.namn)}</div>
          <div style="font-size:11px;color:var(--text-muted);font-family:monospace">${escHtml(r.blockering||(dtm!==null&&dtm<21?`Montage om ${dtm} dagar`:'Tidig varning'))}</div>
        </div>
        ${dEl}
      </div>`;
  }).join('');
  return `<div class="ansl-scroll" style="max-height:600px;padding-right:6px">${items}</div>`;
}

function anslBarChartHtml(p) {
  const now = new Date();
  const months = [];
  for (let i=6;i>=0;i--) {
    const d = new Date(now.getFullYear(), now.getMonth()-i, 1);
    const lbl = d.toLocaleDateString('sv-SE',{month:'short',year:'2-digit'});
    const cnt = p.filter(x => {
      if (!x.berStart) return false;
      const pd = new Date(x.berStart);
      return pd.getFullYear()===d.getFullYear() && pd.getMonth()===d.getMonth();
    }).length;
    months.push({lbl,cnt,cur:i===0});
  }
  const max = Math.max(...months.map(m=>m.cnt),1);
  return `<div style="display:flex;align-items:flex-end;gap:6px;height:80px">` +
    months.map((m,i) => `
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1">
        <div style="font-size:9px;font-family:monospace;color:var(--text-muted)">${m.cnt||''}</div>
        <div style="width:100%;height:${Math.max(4,Math.round(m.cnt/max*60))}px;border-radius:3px 3px 0 0;background:${m.cur?'var(--cyan)':i===5?'rgba(59,130,246,.5)':'var(--surface-3)'}"></div>
        <div style="font-size:9px;font-family:monospace;color:${m.cur?'var(--cyan)':'var(--text-muted)'};font-weight:${m.cur?600:400}">${m.lbl}</div>
      </div>`).join('') + `</div>`;
}

function anslMonsterHtml(p) {
  const done = p.filter(x=>x.fas==='Avslutat'||x.fas==='Drifttagning klar');
  const blocked = p.filter(x=>x.blockering);
  const bTypes = {};
  blocked.forEach(x=>{ const k=x.blockering.split(' ').slice(0,3).join(' '); bTypes[k]=(bTypes[k]||0)+1; });
  const topB = Object.entries(bTypes).sort((a,b)=>b[1]-a[1])[0];
  const withLT = done.filter(x=>anslLT(x));
  const avgLT = withLT.length ? Math.round(withLT.map(anslLT).reduce((a,b)=>a+b,0)/withLT.length) : null;
  const aktiva = p.filter(x=>x.fas!=='Avslutat');
  const items = [
    {icon:'⏱',lbl:'Genomsnittlig ledtid',sub:`Beredningsstart → drifttagning (${done.length} avslutade)`,val:avgLT?`${avgLT}d`:'–',col:'var(--cyan)'},
    {icon:'🔒',lbl:'Vanligaste blockeringen',sub:topB?`${topB[0]}…`:'Ingen data',val:topB?`${topB[1]}st`:'–',col:'var(--red)'},
    {icon:'⚠️',lbl:'Riskprojekt just nu',sub:'< 21d till montagestart eller blockerade',val:String(p.filter(anslRisk).length),col:'var(--amber)'},
    {icon:'📈',lbl:'Andel i beredning',sub:'Av alla aktiva ärenden',val:`${Math.round(p.filter(x=>x.fas==='Beredning').length/Math.max(aktiva.length,1)*100)}%`,col:'var(--blue)'},
  ];
  return items.map(it=>`
    <div style="display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid var(--border)">
      <div style="font-size:18px">${it.icon}</div>
      <div style="flex:1">
        <div style="font-size:12px;font-weight:600;color:var(--text-strong);margin-bottom:3px">${it.lbl}</div>
        <div style="font-size:11px;color:var(--text-muted);font-family:monospace">${it.sub}</div>
      </div>
      <div style="font-size:13px;font-family:monospace;font-weight:500;color:${it.col}">${it.val}</div>
    </div>`).join('');
}

// ---------- Ärenden-vy ----------
function anslArendenHtml(p) {
  const {search,filterFas,sortCol,sortDir} = AnslState;
  const td = p
    .filter(x => {
      if (filterFas && x.fas!==filterFas) return false;
      if (search) { const q=search.toLowerCase(); return x.id.toLowerCase().includes(q)||x.namn.toLowerCase().includes(q)||(x.blockering||'').toLowerCase().includes(q); }
      return true;
    })
    .sort((a,b) => { const av=a[sortCol]||'',bv=b[sortCol]||''; return av<bv?-sortDir:av>bv?sortDir:0; });
  const thI = c => sortCol===c?(sortDir===1?' ↑':' ↓'):'';
  const cols = [['id','IB-nr'],['namn','Projektbenämning'],['fas','Fas'],['berSlut','Beredning slut'],['montStart','Montage start'],['montSlut','Montage slut'],['blockering','Blockering'],['driftDat','Drifttagning']];
  const thStyle = 'padding:8px 12px;text-align:left;font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--text-muted);border-bottom:1px solid var(--border);white-space:nowrap;background:var(--surface-2);cursor:pointer;user-select:none';
  const tdBase = 'padding:9px 12px;vertical-align:middle;border-bottom:1px solid rgba(124,58,237,.06)';
  const filterBtns = ANSL_FAS_ORDER.map(f=>`
    <button class="ansl-ff" data-fas="${escHtml(f)}" style="font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;border:1px solid ${filterFas===f?'var(--cyan-d)':'var(--border)'};background:${filterFas===f?'rgba(124,58,237,.1)':'none'};color:${filterFas===f?'var(--cyan)':'var(--text-muted)'};font-weight:600;letter-spacing:.04em;white-space:nowrap">${f}</button>`).join('');
  const clearBtn = (search||filterFas) ? `<button id="ansl-fc" style="font-size:11px;padding:4px 8px;border-radius:4px;cursor:pointer;border:1px solid var(--border);background:none;color:var(--text-muted)">× Rensa</button>` : '';
  const rows = td.length===0
    ? `<tr><td colspan="8" style="padding:32px;text-align:center;color:var(--text-muted);font-family:monospace;font-size:12px">Inga ärenden matchar filtret</td></tr>`
    : td.map(x => {
        const risk = anslRisk(x);
        const fc = ANSL_FAS_C[x.fas]||'#4a6a8a';
        const fBadge = `<span style="display:inline-flex;align-items:center;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${fc}22;color:${fc};border:1px solid ${fc}33">${x.fas}</span>`;
        const blk = x.blockering
          ? `<span style="display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:4px;font-size:10px;font-family:monospace;background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2);max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escHtml(x.blockering)}">⚠ ${escHtml(x.blockering)}</span>`
          : `<span style="color:var(--text-muted);font-size:11px">–</span>`;
        return `<tr class="ansl-tr" data-pid="${escHtml(x.id)}" style="cursor:pointer;border-left:2px solid ${risk?'var(--red)':'transparent'}">
          <td style="${tdBase};font-family:monospace;font-size:11px;color:var(--text-muted)">${escHtml(x.id)}</td>
          <td style="${tdBase};font-weight:600;color:var(--text-strong);max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escHtml(x.namn)}">${escHtml(x.namn)}</td>
          <td style="${tdBase}">${fBadge}</td>
          <td style="${tdBase};font-family:monospace;font-size:11px;color:var(--text-muted)">${anslFD(x.berSlut)}</td>
          <td style="${tdBase};font-family:monospace;font-size:11px;color:var(--text-muted)">${anslFD(x.montStart)}</td>
          <td style="${tdBase};font-family:monospace;font-size:11px;color:var(--text-muted)">${anslFD(x.montSlut)}</td>
          <td style="${tdBase}">${blk}</td>
          <td style="${tdBase};font-family:monospace;font-size:11px;color:${x.driftDat?'var(--green)':'var(--text-muted)'}">${anslFD(x.driftDat)}</td>
        </tr>`;
      }).join('');
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden">
      <div style="display:flex;align-items:center;gap:8px;padding:0 18px;background:var(--surface-2);border-bottom:1px solid var(--border);flex-wrap:wrap">
        <span style="color:var(--text-muted);font-size:14px">⌕</span>
        <input id="ansl-search" value="${escHtml(search)}" placeholder="Sök IB-nr, namn, blockering…"
          style="flex:1;min-width:150px;background:none;border:none;color:var(--text);font-size:12px;font-family:monospace;padding:10px 0;outline:none">
        <div style="display:flex;gap:6px;flex-wrap:wrap;padding:6px 0">${filterBtns}${clearBtn}</div>
      </div>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead><tr>${cols.map(([c,l])=>`<th class="ansl-th" data-col="${c}" style="${thStyle}">${l}${thI(c)}</th>`).join('')}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div style="padding:8px 18px;font-size:11px;color:var(--text-muted);font-family:monospace;border-top:1px solid var(--border)">
        Visar ${td.length} av ${p.length} ärenden · Klicka på rad för detaljer
      </div>
    </div>`;
}

// ---------- Analys-vy ----------
function anslCalendarHtml(p, year, month) {
  const startDates = {};
  p.forEach(x => {
    if (x.montStart) {
      const d = x.montStart.slice(0,10);
      if (!startDates[d]) startDates[d] = [];
      startDates[d].push(x.namn);
    }
  });
  const MONTHS = ['Januari','Februari','Mars','April','Maj','Juni','Juli','Augusti','September','Oktober','November','December'];
  const DAYS   = ['Mån','Tis','Ons','Tor','Fre','Lör','Sön'];
  const today  = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month+1, 0).getDate();
  let startDow = firstDay.getDay() - 1;
  if (startDow < 0) startDow = 6;
  const headerRow  = DAYS.map(d=>`<div style="text-align:center;font-size:10px;font-weight:600;letter-spacing:.06em;color:var(--text-muted);padding:4px 0">${d}</div>`).join('');
  const emptyCells = Array(startDow).fill('<div></div>').join('');
  const dayCells   = Array.from({length:daysInMonth},(_,i)=>{
    const day = i+1;
    const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const starts  = startDates[dateStr];
    const isToday = dateStr === todayStr;
    const hasMont = starts && starts.length > 0;
    const bg      = hasMont ? `rgba(124,58,237,${starts.length>1?0.28:0.16})` : isToday ? 'rgba(124,58,237,0.07)' : 'transparent';
    const border  = (hasMont || isToday) ? '1px solid var(--cyan)' : '1px solid transparent';
    const color   = hasMont ? 'var(--cyan)' : isToday ? 'var(--cyan)' : 'var(--text)';
    const badge   = hasMont && starts.length > 1 ? `<div style="position:absolute;top:2px;right:3px;font-size:9px;font-family:monospace;color:var(--cyan);font-weight:700">${starts.length}</div>` : '';
    return `<div style="position:relative;aspect-ratio:1;display:flex;align-items:center;justify-content:center;background:${bg};border:${border};border-radius:6px;font-size:12px;font-weight:${hasMont?700:400};color:${color}">${day}${badge}</div>`;
  }).join('');
  return `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <button data-ansl-cal="prev" style="background:none;border:1px solid var(--border);border-radius:6px;padding:4px 12px;color:var(--text-muted);cursor:pointer;font-size:15px">‹</button>
      <span style="font-size:13px;font-weight:600;color:var(--text-strong)">${MONTHS[month]} ${year}</span>
      <button data-ansl-cal="next" style="background:none;border:1px solid var(--border);border-radius:6px;padding:4px 12px;color:var(--text-muted);cursor:pointer;font-size:15px">›</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">${headerRow}${emptyCells}${dayCells}</div>`;
}

function anslAnalysHtml(p) {
  const aktiva   = p.filter(x=>x.fas!=='Avslutat');
  const risker   = p.filter(anslRisk);
  const blockerade = p.filter(x=>x.blockering);
  const driftklara = p.filter(x=>x.fas==='Drifttagning klar'||x.fas==='Avslutat');
  const done     = p.filter(x=>x.fas==='Avslutat'||x.fas==='Drifttagning klar'||!!x.driftDat);
  const withLT   = done.filter(x=>anslLT(x));
  const avgLT    = withLT.length ? Math.round(withLT.map(anslLT).reduce((a,b)=>a+b,0)/withLT.length) : '–';

  const fasKpis = ANSL_FAS_ORDER.map(f=>{
    const n=p.filter(x=>x.fas===f).length;
    const r=p.filter(x=>x.fas===f&&anslRisk(x)).length;
    const c=ANSL_FAS_C[f];
    return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;border-top:2px solid ${c}">
      <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px">${f}</div>
      <div style="font-size:32px;font-weight:800;color:${c};line-height:1;margin-bottom:4px">${n}</div>
      <div style="font-size:11px;color:var(--text-muted);font-family:monospace">${r>0?`${r} i riskzon`:'Inga risker'}</div>
    </div>`;
  }).join('');

  const blkRows = blockerade.length===0
    ? `<div style="padding:32px;text-align:center;color:var(--text-muted);font-size:12px;font-family:monospace">Inga blockerade ärenden</div>`
    : blockerade.map(x=>`
        <div class="ansl-blk-row" data-pid="${escHtml(x.id)}" style="display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid var(--border);cursor:pointer">
          <div style="width:8px;height:8px;border-radius:50%;background:var(--red);flex-shrink:0"></div>
          <div style="flex:1">
            <div style="font-size:12px;font-weight:600;color:var(--text-strong);margin-bottom:3px">${escHtml(x.namn)}</div>
            <div style="font-size:11px;color:var(--text-muted);font-family:monospace">${escHtml(x.blockering)}</div>
          </div>
          <div style="font-size:11px;color:var(--text-muted);font-family:monospace">IB ${escHtml(x.id)}</div>
        </div>`).join('');

  const nyckeltal = [
    ['Totalt aktiva',aktiva.length],['I beredning',p.filter(x=>x.fas==='Beredning').length],
    ['Blockerade',blockerade.length],['Driftklara hittills',driftklara.length],
    ['Andel i riskzon',`${Math.round(risker.length/Math.max(aktiva.length,1)*100)}%`],
  ].map(([l,v])=>`
    <div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid rgba(124,58,237,.06);font-size:12px">
      <span style="color:var(--text-muted)">${l}</span>
      <span style="color:var(--text-strong);font-family:monospace;font-weight:500">${v}</span>
    </div>`).join('');

  return `
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">${fasKpis}</div>
    <div style="display:grid;grid-template-columns:1fr 320px;gap:16px">
      ${anslPanelHtml('Blockeringsanalys',null,blkRows)}
      <div style="display:flex;flex-direction:column;gap:16px">
        ${anslPanelHtml('Ledtidsanalys',null,`
          <div style="display:flex;flex-direction:column;align-items:center;padding:8px 0">
            <div style="font-size:42px;font-weight:800;color:var(--text-strong);line-height:1">${avgLT}</div>
            <div style="font-size:12px;color:var(--text-muted);font-family:monospace;margin-top:4px">dagar genomsnittlig ledtid</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:8px;text-align:center">Beredningsstart → drifttagning<br>${done.length} avslutade ärenden</div>
          </div>`)}
        ${anslPanelHtml('Nyckeltal',null,nyckeltal)}
      </div>
    </div>
    ${anslPanelHtml('Kalender – montagestart',null,anslCalendarHtml(p,AnslState.calYear,AnslState.calMonth))}`;
}

// ---------- Drawer (sidopanel) ----------
function anslDrawerHtml(p) {
  const lt  = anslLT(p);
  const dtm = anslDTM(p);
  const risk = anslRisk(p);
  const fc  = ANSL_FAS_C[p.fas]||'var(--cyan)';
  const s   = anslPD(p.berStart), e = anslPD(p.montSlut);
  const timelineHtml = s && e ? (()=>{
    const total = anslDD(s,e);
    const done  = Math.min(100,Math.max(0,Math.round(anslDD(s,new Date())/total*100)));
    const col   = p.fas==='Avslutat'||p.fas==='Drifttagning klar' ? 'var(--green)' : risk ? 'var(--red)' : 'var(--cyan)';
    return `<div style="margin:12px 0">
      <div style="height:4px;background:var(--surface-3);border-radius:2px;overflow:hidden">
        <div style="height:100%;width:${done}%;background:${col};border-radius:2px"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:10px;font-family:monospace;color:var(--text-muted)">
        <span>${anslFD(p.berStart)}</span><span style="color:var(--cyan)">${done}% av total tid</span><span>${anslFD(p.montSlut)}</span>
      </div>
    </div>`;
  })() : '';
  const datumsHtml = [['Beredning start',p.berStart],['Beredning slut',p.berSlut],['Montage start',p.montStart],['Montage slut',p.montSlut],['Drifttagning',p.driftDat]]
    .map(([l,v])=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(124,58,237,.06);font-size:12px"><span style="color:var(--text-muted)">${l}</span><span style="color:var(--text-strong);font-family:monospace;font-weight:500">${anslFD(v)}</span></div>`).join('');
  const dtmEl = dtm!==null ? `<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:12px"><span style="color:var(--text-muted)">Dagar till montage</span><span style="color:${dtm<14?'var(--red)':dtm<21?'var(--amber)':'var(--green)'};font-family:monospace;font-weight:500">${dtm}d</span></div>` : '';
  const ltEl  = lt!==null  ? `<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:12px"><span style="color:var(--text-muted)">Total ledtid</span><span style="color:var(--text-strong);font-family:monospace;font-weight:500">${lt} dagar</span></div>` : '';
  const fasOpts = ANSL_FAS_ORDER.map(f=>`<option value="${f}"${p.fas===f?' selected':''}>${f}</option>`).join('');
  const inp = 'width:100%;background:var(--surface-2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:monospace;font-size:11px;padding:10px;margin-top:6px;outline:none;box-sizing:border-box';
  const sectionHead = txt => `<div style="font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--text-muted);margin-bottom:10px;border-bottom:1px solid var(--border);padding-bottom:6px">${txt}</div>`;
  return `
    <div id="ansl-drawer-panel" style="width:min(420px,100vw);background:var(--surface);border-left:1px solid var(--border);height:100%;overflow-y:auto;padding:28px;position:relative;box-sizing:border-box;animation:ansl-slide-in .2s ease">
      <style>@keyframes ansl-slide-in{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}</style>
      <button id="ansl-drawer-close" style="position:absolute;top:20px;right:20px;background:var(--surface-2);border:1px solid var(--border);color:var(--text-muted);width:28px;height:28px;border-radius:6px;cursor:pointer;font-size:14px">✕</button>
      <div style="font-family:monospace;font-size:11px;color:var(--text-muted);margin-bottom:6px">IB ${escHtml(p.id)}</div>
      <div style="font-size:18px;font-weight:800;color:var(--text-strong);line-height:1.3;margin-bottom:16px;padding-right:40px">${escHtml(p.namn)}</div>
      <span style="display:inline-flex;align-items:center;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${fc}22;color:${fc};border:1px solid ${fc}44">${p.fas}</span>
      <div style="margin-top:20px">${sectionHead('Tidslinje')}${timelineHtml}</div>
      <div style="margin-top:20px">${sectionHead('Datum')}${datumsHtml}${dtmEl}${ltEl}</div>
      <div style="margin-top:20px">
        ${sectionHead('Uppdatera')}
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">Fas</div>
        <select id="ansl-d-fas" style="${inp}">${fasOpts}</select>
        <div style="font-size:11px;color:var(--text-muted);margin-top:10px;margin-bottom:2px">Blockering (lämna tomt om ingen)</div>
        <textarea id="ansl-d-blk" style="${inp};resize:vertical;min-height:60px" placeholder="Beskriv vad som blockerar…">${escHtml(p.blockering||'')}</textarea>
        <div style="font-size:11px;color:var(--text-muted);margin-top:10px;margin-bottom:2px">Notat</div>
        <textarea id="ansl-d-not" style="${inp};resize:vertical;min-height:60px" placeholder="Anteckningar…">${escHtml(p.notat||'')}</textarea>
        <button id="ansl-drawer-save" style="margin-top:12px;width:100%;padding:10px;border-radius:6px;background:var(--cyan);color:var(--bg);font-weight:700;font-size:12px;cursor:pointer;border:none;letter-spacing:.05em">Spara ändringar</button>
      </div>
    </div>`;
}

function anslShowDrawer(projektId, app) {
  document.getElementById('ansl-drawer-overlay')?.remove();
  const p = AnslState.projekt.find(x=>x.id===projektId);
  if (!p) return;
  const ov = document.createElement('div');
  ov.id = 'ansl-drawer-overlay';
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(4,13,30,.8);z-index:200;display:flex;justify-content:flex-end';
  ov.innerHTML = anslDrawerHtml(p);
  document.body.appendChild(ov);
  ov.addEventListener('click', e => { if (e.target===ov) ov.remove(); });
  ov.querySelector('#ansl-drawer-close').addEventListener('click', ()=>ov.remove());
  ov.querySelector('#ansl-drawer-save').addEventListener('click', async ()=>{
    const fas = ov.querySelector('#ansl-d-fas').value;
    const blk = ov.querySelector('#ansl-d-blk').value.trim() || null;
    const not = ov.querySelector('#ansl-d-not').value.trim();
    const idx = AnslState.projekt.findIndex(x=>x.id===projektId);
    try {
      await api('PUT', '/anslutning/' + encodeURIComponent(projektId), {fas, blockering: blk, notat: not});
      if (idx>-1) { AnslState.projekt[idx]={...AnslState.projekt[idx],fas,blockering:blk,notat:not}; }
      ov.remove();
      anslRenderContent(app);
    } catch(e) {
      toast('Kunde inte spara: ' + e.message, 'error');
    }
  });
}

// ---------- Excel import ----------
function anslHandleFile(e, app) {
  const file = e.target.files[0];
  if (!file) return;
  if (typeof XLSX === 'undefined') { toast('SheetJS saknas – kontrollera internetanslutningen.','error'); return; }
  const reader = new FileReader();
  reader.onload = async ev => {
    try {
      const wb = XLSX.read(ev.target.result,{type:'binary',cellDates:true});
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws,{defval:null});
      const fmt = v => {
        if (!v) return null;
        if (v instanceof Date) return v.toISOString().slice(0,10);
        if (typeof v==='string'&&v.match(/\d{4}-\d{2}-\d{2}/)) return v.slice(0,10);
        return null;
      };
      const PL_SIGN_MAP = {
        'DACA':'Daniel Carlsson','BJNI':'Björn Nilsson',
        'JIBU':'Jimmy Buch','ANMA':'Antonio Malm','RAGR':'Rasmus Grahn'
      };
      const mapped = rows.map((r,i)=>({
        id:              String(r['IB nr']||r['IB_nr']||r['id']||`IMP-${i}`),
        namn:            r['Projektbenamning']||r['Projektbenämning']||r['namn']||'Okänt',
        kund:            r['Kund']||r['kund']||'–',
        fas:             ANSL_FAS_MAP[(r['Arbetsflöde']||r['Arbetsflode']||r['fas']||'').toString().trim()] || 'Tidig fas',
        berStart:        fmt(r['Beredning Start']||r['berStart']),
        berSlut:         fmt(r['Beredning Slut']||r['berSlut']),
        montStart:       fmt(r['Montage Start']||r['montStart']),
        montSlut:        fmt(r['Montage Slut']||r['montSlut']),
        driftDat:        fmt(r['Drift.datum']||r['driftDat']),
        bestallningKlar: fmt(r['Bestallning klar']||r['Beställning klar']||r['bestallningKlar']),
        beredare:        PL_SIGN_MAP[(r['PL Sign']||r['PL sign']||r['PL_sign']||'').toString().trim().toUpperCase()] || (r['beredare']||null),
        blockering:      r['blockering']||null,
        notat:           r['notat']||'',
      }));
      await api('POST', '/anslutning/import', mapped);
      AnslState.projekt = mapped;
      toast(`${mapped.length} ärenden importerade`,'success');
      renderAnslutning(app);
    } catch(err) { toast('Kunde inte importera filen: '+err.message,'error'); }
  };
  reader.readAsBinaryString(file);
  e.target.value='';
}

// ---------- Huvud-renderer ----------
async function renderAnslutning(app) {
  document.getElementById('ansl-drawer-overlay')?.remove();
  const tabs = [['oversikt','Översikt'],['arenden','Ärenden'],['analys','Analys']];
  app.innerHTML = `
    <div style="background:var(--bg);min-height:100%;color:var(--text);font-family:var(--font)">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap">
        <div style="display:flex;gap:2px">
          ${tabs.map(([id,lbl])=>`
            <button data-ansl-tab="${id}" style="padding:12px 16px;font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;cursor:pointer;background:none;border:none;border-bottom:2px solid ${AnslState.view===id?'var(--cyan)':'transparent'};color:${AnslState.view===id?'var(--cyan)':'var(--text-muted)'};transition:all .15s">${lbl}</button>`).join('')}
        </div>
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0">
          <span id="ansl-count" style="font-size:11px;color:var(--text-muted);font-family:monospace">Laddar...</span>
          <button id="ansl-import-btn" style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;border:1px solid var(--cyan-d);background:transparent;color:var(--cyan);font-size:11px;font-weight:600;cursor:pointer;letter-spacing:.03em">↑ Importera Excel</button>
        </div>
      </div>
      <div id="ansl-content" style="padding:24px;display:flex;flex-direction:column;gap:20px">
        <div style="text-align:center;padding:40px;color:var(--text-muted);font-size:13px">Laddar ärenden...</div>
      </div>
      <input type="file" id="ansl-file-input" accept=".xlsx,.xls" style="display:none">
    </div>`;

  app.querySelectorAll('[data-ansl-tab]').forEach(btn=>{
    btn.addEventListener('click',()=>{ AnslState.view=btn.dataset.anslTab; AnslState.search=''; renderAnslutning(app); });
  });
  app.querySelector('#ansl-import-btn').addEventListener('click',()=>app.querySelector('#ansl-file-input').click());
  app.querySelector('#ansl-file-input').addEventListener('change',e=>anslHandleFile(e,app));

  await anslLoadFromApi();

  const countEl = app.querySelector('#ansl-count');
  if (countEl) countEl.textContent = `${AnslState.projekt.length} ärenden`;
  anslRenderContent(app);
}

function anslRenderContent(app) {
  const el = document.getElementById('ansl-content');
  if (!el) return;
  const p = AnslState.projekt;
  switch(AnslState.view) {
    case 'oversikt': {
      const aktiva=p.filter(x=>x.fas!=='Avslutat');
      const risker=p.filter(anslRisk);
      const blk=p.filter(x=>x.blockering);
      const done=p.filter(x=>x.fas==='Avslutat'||x.fas==='Drifttagning klar');
      const withLT=done.filter(x=>anslLT(x));
      const avgLT=withLT.length?Math.round(withLT.map(anslLT).reduce((a,b)=>a+b,0)/withLT.length):'–';
      el.innerHTML=`
        ${anslPanelHtml('Fas-fördelning',`${p.length} ärenden`,anslFasBarHtml(p))}
        <div style="display:grid;grid-template-columns:1fr min(340px,100%);gap:16px">
          ${anslPanelHtml('Riskärenden — kräver action',`${risker.length} st`,anslRiskListHtml(p),'var(--red)')}
          <div style="display:flex;flex-direction:column;gap:16px">
            ${anslPanelHtml('Mönsteranalys',null,anslMonsterHtml(p))}
          </div>
        </div>`;
      break;
    }
    case 'arenden': {
      el.innerHTML = anslArendenHtml(p);
      const si = el.querySelector('#ansl-search');
      si.addEventListener('input',()=>{
        AnslState.search=si.value;
        el.innerHTML=anslArendenHtml(p);
        const ni=el.querySelector('#ansl-search');
        if(ni){ni.focus();ni.setSelectionRange(ni.value.length,ni.value.length);}
        anslArendenInit(el,p,app);
      });
      anslArendenInit(el,p,app);
      break;
    }
    case 'analys': {
      el.innerHTML = anslAnalysHtml(p);
      el.querySelectorAll('.ansl-blk-row').forEach(r=>r.addEventListener('click',()=>anslShowDrawer(r.dataset.pid,app)));
      el.querySelectorAll('[data-ansl-cal]').forEach(btn=>btn.addEventListener('click',()=>{
        if (btn.dataset.anslCal==='prev') {
          AnslState.calMonth--;
          if (AnslState.calMonth < 0) { AnslState.calMonth=11; AnslState.calYear--; }
        } else {
          AnslState.calMonth++;
          if (AnslState.calMonth > 11) { AnslState.calMonth=0; AnslState.calYear++; }
        }
        anslRenderContent(app);
      }));
      break;
    }
  }
}

function anslArendenInit(el, p, app) {
  el.querySelectorAll('.ansl-ff').forEach(btn=>{
    btn.addEventListener('click',()=>{
      AnslState.filterFas = AnslState.filterFas===btn.dataset.fas ? null : btn.dataset.fas;
      el.innerHTML=anslArendenHtml(p);
      const si=el.querySelector('#ansl-search');
      si.addEventListener('input',()=>{AnslState.search=si.value;el.innerHTML=anslArendenHtml(p);anslArendenInit(el,p,app);});
      anslArendenInit(el,p,app);
    });
  });
  const fc=el.querySelector('#ansl-fc');
  if(fc) fc.addEventListener('click',()=>{AnslState.search='';AnslState.filterFas=null;el.innerHTML=anslArendenHtml(p);anslArendenInit(el,p,app);});
  el.querySelectorAll('.ansl-th').forEach(th=>{
    th.addEventListener('click',()=>{
      if(AnslState.sortCol===th.dataset.col) AnslState.sortDir*=-1;
      else {AnslState.sortCol=th.dataset.col;AnslState.sortDir=1;}
      el.innerHTML=anslArendenHtml(p);
      const si=el.querySelector('#ansl-search');
      si.addEventListener('input',()=>{AnslState.search=si.value;el.innerHTML=anslArendenHtml(p);anslArendenInit(el,p,app);});
      anslArendenInit(el,p,app);
    });
  });
  el.querySelectorAll('.ansl-tr').forEach(tr=>tr.addEventListener('click',()=>anslShowDrawer(tr.dataset.pid,app)));
}

// ================================================================
// TIDPLAN — Gantt-vy
// ================================================================
const TP_MILESTONES = [
  { key:'berStart',        label:'Beredning start',  color:'#3B8EEA' },
  { key:'berSlut',         label:'Beredning klar',   color:'#9B59B6' },
  { key:'montStart',       label:'Montage start',    color:'#F4A318' },
  { key:'driftDat',        label:'Driftsatt',         color:'#2ECC8E' },
  { key:'bestallningKlar', label:'Beställning klar', color:'#E74C3C' },
];

async function renderTidplan(app) {
  await anslLoadFromApi();
  const allData = AnslState.projekt !== null ? AnslState.projekt : ANSL_SAMPLE;

  const TPS = { search:'', filter:'alla', filterBeredare:'alla', period:'halvar', dagBredd:18 };

  // ---- date helpers ----
  function daysBetween(a, b) { return Math.round((b - a) / 86400000); }
  function xPos(dateStr, rangeStart) {
    if (!dateStr) return null;
    return daysBetween(rangeStart, new Date(dateStr)) * TPS.dagBredd;
  }
  function getRange() {
    const now = new Date();
    let start, end;
    if (TPS.period === 'kvartal') {
      start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      end   = new Date(now.getFullYear(), now.getMonth() + 3, 0);
    } else if (TPS.period === 'helaar') {
      start = new Date(now.getFullYear(), 0, 1);
      end   = new Date(now.getFullYear(), 11, 31);
    } else {
      start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      end   = new Date(now.getFullYear(), now.getMonth() + 6, 0);
    }
    return { start, end };
  }
  function applyPeriodZoom() {
    const w = (document.getElementById('tpGanttArea') || { clientWidth: window.innerWidth - 280 }).clientWidth;
    const days = TPS.period === 'kvartal' ? 90 : TPS.period === 'helaar' ? 365 : 180;
    TPS.dagBredd = Math.max(4, Math.min(40, (w || window.innerWidth - 280) / days));
  }

  // ---- filter / sort ----
  function getFiltered() {
    let d = allData;
    if (TPS.search) { const q = TPS.search.toLowerCase(); d = d.filter(p => p.namn.toLowerCase().includes(q) || (p.id||'').toLowerCase().includes(q)); }
    if (TPS.filter === 'aktiva') d = d.filter(p => p.fas !== 'Avslutat' && !p.driftDat);
    else if (TPS.filter === 'klara') d = d.filter(p => p.fas === 'Avslutat' || p.fas === 'Drifttagning klar' || !!p.driftDat);
    if (TPS.filterBeredare !== 'alla') d = d.filter(p => p.beredare === TPS.filterBeredare);
    return [...d].sort((a, b) => {
      if (a.montStart && b.montStart) return a.montStart.localeCompare(b.montStart);
      if (a.montStart) return -1; if (b.montStart) return 1;
      if (a.berStart  && b.berStart)  return a.berStart.localeCompare(b.berStart);
      return 0;
    });
  }

  // ---- month header ----
  function buildMonths(rs, re) {
    const names = ['JAN','FEB','MAR','APR','MAJ','JUN','JUL','AUG','SEP','OKT','NOV','DEC'];
    const today = new Date(); let html = '';
    let cur = new Date(rs.getFullYear(), rs.getMonth(), 1);
    while (cur <= re) {
      const next = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
      const ms   = new Date(Math.max(cur, rs));
      const me   = new Date(Math.min(next - 1, re));
      const days = daysBetween(ms, me) + 1;
      const off  = daysBetween(rs, ms);
      const isCur = cur.getMonth() === today.getMonth() && cur.getFullYear() === today.getFullYear();
      html += `<div class="tp-month-cell${isCur?' tp-month-cur':''}" style="width:${days*TPS.dagBredd}px;left:${off*TPS.dagBredd}px">${names[cur.getMonth()]} ${cur.getFullYear()}</div>`;
      cur = next;
    }
    return html;
  }

  // ---- week lines ----
  function buildWeekLines(rs, re, totalWidth) {
    let html = '', d = new Date(rs);
    while (d.getDay() !== 1) d.setDate(d.getDate() + 1);
    while (d <= re) {
      const x = daysBetween(rs, d) * TPS.dagBredd;
      if (x >= 0 && x <= totalWidth)
        html += `<div class="tp-week-line" style="left:${x}px"></div>`;
      d.setDate(d.getDate() + 7);
    }
    return html;
  }

  // ---- main build ----
  function buildUI() {
    const { start: rs, end: re } = getRange();
    const totalDays  = daysBetween(rs, re) + 1;
    const totalWidth = totalDays * TPS.dagBredd;
    const today      = new Date();
    const todayX     = daysBetween(rs, today) * TPS.dagBredd;
    const filtered   = getFiltered();

    let leftHtml = '', ganttHtml = '';

    filtered.forEach((p, i) => {
      const delay  = Math.min(i * 30, 600);
      const altCls = i % 2 === 1 ? ' tp-alt' : '';

      leftHtml += `<div class="tp-left-row${altCls}" data-pid="${escHtml(p.id)}" style="animation-delay:${delay}ms">
        <div class="tp-ibnr">${escHtml(p.id||'')}</div>
        <div class="tp-pnamn" title="${escHtml(p.namn)}">${escHtml(p.namn)}</div>
      </div>`;

      // Background bar
      let barHtml = '';
      const barS = p.berStart || p.montStart;
      const barE = p.bestallningKlar || p.driftDat || p.montSlut || p.montStart;
      if (barS && barE && barS <= barE) {
        const bx = xPos(barS, rs), ex = xPos(barE, rs);
        const bw = Math.max((ex - bx) + TPS.dagBredd, 4);
        barHtml = `<div class="tp-bar" style="left:${bx}px;width:${bw}px;animation-delay:${Math.min(i*20,400)}ms"></div>`;
      } else if (barS) {
        const bx = xPos(barS, rs);
        barHtml = `<div class="tp-bar" style="left:${bx}px;width:${TPS.dagBredd*14}px;opacity:0.3;animation-delay:${Math.min(i*20,400)}ms"></div>`;
      }

      // Milestones
      let msHtml = '';
      TP_MILESTONES.forEach((ms, mi) => {
        if (!p[ms.key]) return;
        const d      = new Date(p[ms.key]);
        const mx     = xPos(p[ms.key], rs);
        if (mx === null) return;
        const isPast = d < today;
        const alwaysFilled = ms.key === 'bestallningKlar';
        const filled = isPast || alwaysFilled;
        const msDelay = Math.min(i * 40 + mi * 60 + 200, 900);
        const showDate = TPS.dagBredd >= 6;
        msHtml += `<div class="tp-milestone" style="left:${mx}px;animation-delay:${msDelay}ms">
          <div class="tp-diamond" style="background:${filled?ms.color:'transparent'};border-color:${ms.color};${filled?`box-shadow:0 0 8px ${ms.color}88`:'opacity:.7'}"></div>
          <div class="tp-ms-vline" style="background:${ms.color}60"></div>
          ${showDate?`<div class="tp-ms-date" style="color:${ms.color}">${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}</div>`:''}
        </div>`;
      });

      ganttHtml += `<div class="tp-gantt-row${altCls}" data-pid="${escHtml(p.id)}" style="animation-delay:${delay}ms">
        ${barHtml}${msHtml}
      </div>`;
    });

    const ganttHeight = filtered.length * 44;
    const todayVisible = todayX >= 0 && todayX <= totalWidth;
    const todayHtml = todayVisible ? `<div class="tp-today-line" style="left:${todayX}px;height:${ganttHeight}px">
      <div class="tp-today-tri"></div>
      <div class="tp-today-lbl">IDAG</div>
      <div class="tp-today-bar"></div>
    </div>` : '';

    const fBtns = [['alla','Alla'],['aktiva','Aktiva'],['klara','Klara']];
    const pBtns = [['kvartal','Kvartal'],['halvar','Halvår'],['helaar','Helår']];
    const allBeredare = [...new Set(allData.filter(p=>p.beredare).map(p=>p.beredare))].sort();

    app.innerHTML = `
      <div class="tp-root">
        <div class="tp-toolbar">
          <div class="tp-tb-left">
            <div class="tp-search-wrap">
              <span class="tp-search-icon">⌕</span>
              <input class="tp-search" id="tpSearch" placeholder="Sök projekt…" value="${escHtml(TPS.search)}">
            </div>
            <div class="tp-pills">
              ${fBtns.map(([v,l])=>`<button class="tp-pill${TPS.filter===v?' tp-pill-on':''}" data-filter="${v}">${l}</button>`).join('')}
            </div>
            <div class="tp-pills">
              ${pBtns.map(([v,l])=>`<button class="tp-pill${TPS.period===v?' tp-pill-on':''}" data-period="${v}">${l}</button>`).join('')}
            </div>
            <div class="tp-ber-wrap">
              <span class="tp-ber-lbl">👷</span>
              <select class="tp-ber-select" id="tpBerSelect">
                <option value="alla">Alla beredare</option>
                ${allBeredare.map(b=>`<option value="${escHtml(b)}" ${TPS.filterBeredare===b?'selected':''}>${escHtml(b)}</option>`).join('')}
              </select>
            </div>
          </div>
          <div class="tp-tb-right">
            <span class="tp-proj-count">${filtered.length} projekt</span>
            <button class="tp-zoom-btn" id="tpZoomOut">−</button>
            <button class="tp-zoom-btn" id="tpZoomIn">+</button>
            <button class="tp-zoom-btn" id="tpZoomReset" title="Återställ">↺</button>
          </div>
        </div>

        <div class="tp-body" id="tpBody">
          <div class="tp-left" id="tpLeft">
            <div class="tp-left-hdr">PROJEKT</div>
            <div class="tp-left-list" id="tpLeftList">${leftHtml}</div>
          </div>
          <div class="tp-gantt-area" id="tpGanttArea">
            <div class="tp-months" style="width:${totalWidth}px">${buildMonths(rs, re)}</div>
            <div class="tp-gantt-rows" id="tpGanttRows" style="width:${totalWidth}px">
              ${buildWeekLines(rs, re, totalWidth)}
              ${ganttHtml}
              ${todayHtml}
              ${filtered.length===0?'<div class="tp-empty">Inga projekt — importera en Excel-fil i Analysfliken</div>':''}
            </div>
          </div>
        </div>

        <div class="tp-legend">
          <div class="tp-leg-left">
            ${TP_MILESTONES.map(ms=>`<span class="tp-leg-item"><span class="tp-leg-dia" style="background:${ms.color}"></span>${ms.label}</span>`).join('')}
          </div>
          <div class="tp-leg-right">◆ = passerat &nbsp;◇ = kommande</div>
        </div>
      </div>`;

    bindTpEvents(todayX);
  }

  function scrollToToday(todayX) {
    const ga = document.getElementById('tpGanttArea');
    if (!ga) return;
    ga.scrollLeft = Math.max(0, todayX - ga.clientWidth * 0.25);
  }

  function rebuild() {
    const ga = document.getElementById('tpGanttArea');
    const sl = ga ? ga.scrollLeft : 0;
    const st = ga ? ga.scrollTop  : 0;
    buildUI();
    const nga = document.getElementById('tpGanttArea');
    if (nga) { nga.scrollLeft = sl; nga.scrollTop = st; }
  }

  // ---- tooltip ----
  let tpTooltip = null;
  function showTpTooltip(pid, e) {
    const p = allData.find(x => x.id === pid); if (!p) return;
    hideTpTooltip();
    tpTooltip = document.createElement('div');
    tpTooltip.className = 'tp-tooltip';
    tpTooltip.innerHTML = `
      <div class="tp-tt-name">${escHtml(p.namn)}</div>
      <div class="tp-tt-id">${escHtml(p.id||'')}</div>
      <div class="tp-tt-ms">${TP_MILESTONES.map(ms => {
        if (!p[ms.key]) return '';
        const d = new Date(p[ms.key]);
        return `<div class="tp-tt-row">
          <span class="tp-tt-dia" style="background:${ms.color}"></span>
          <span class="tp-tt-lbl">${ms.label}</span>
          <span class="tp-tt-dat" style="color:${ms.color}">${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}</span>
        </div>`;
      }).join('')}</div>`;
    document.body.appendChild(tpTooltip);
    moveTpTooltip(e);
  }
  function moveTpTooltip(e) {
    if (!tpTooltip) return;
    let x = e.clientX + 16, y = e.clientY + 16;
    if (x + 270 > window.innerWidth)  x = e.clientX - 270 - 8;
    if (y + 220 > window.innerHeight) y = e.clientY - 220 - 8;
    tpTooltip.style.left = x + 'px'; tpTooltip.style.top = y + 'px';
  }
  function hideTpTooltip() { if (tpTooltip) { tpTooltip.remove(); tpTooltip = null; } }

  // ---- drawer ----
  function openTpDrawer(pid) {
    const p = allData.find(x => x.id === pid); if (!p) return;
    hideTpTooltip();
    const today = new Date();
    const upcoming = TP_MILESTONES
      .filter(ms => p[ms.key] && new Date(p[ms.key]) >= today)
      .sort((a, b) => p[a.key].localeCompare(p[b.key]))[0];

    const nextMsHtml = upcoming ? (() => {
      const d = new Date(p[upcoming.key]);
      const days = Math.round((d - today) / 86400000);
      return `<div class="tp-drawer-section">
        <div class="tp-drawer-sec-lbl">NÄSTA MILSTOLPE</div>
        <div class="tp-drawer-nextms">
          <div class="tp-drawer-nextms-name" style="color:${upcoming.color}">${upcoming.label}</div>
          <div class="tp-drawer-nextms-days" style="color:${upcoming.color}">${days}d</div>
          <div class="tp-drawer-nextms-date">${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}</div>
        </div>
      </div>`;
    })() : '';

    const milsHtml = TP_MILESTONES.map(ms => {
      if (!p[ms.key]) return `<div class="tp-drawer-ms-row tp-drawer-ms-empty">
        <span style="color:${ms.color};opacity:.3">◇</span><span style="opacity:.4">${ms.label}</span><span style="opacity:.3">–</span>
      </div>`;
      const d = new Date(p[ms.key]); const isPast = d < today;
      const days = Math.round((d - today) / 86400000);
      const pill = isPast
        ? `<span class="tp-drawer-pill" style="background:${ms.color}22;color:${ms.color}">✓</span>`
        : `<span class="tp-drawer-pill" style="background:#1E2D40;color:#4A6077">${days}d</span>`;
      return `<div class="tp-drawer-ms-row">
        <span style="color:${ms.color}">${isPast?'◆':'◇'}</span>
        <span>${ms.label}</span>
        <span style="font-family:'DM Mono',monospace;font-size:11px">${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}</span>
        ${pill}
      </div>`;
    }).join('');

    const fasColors = {'Tidig fas':'#7A9BB5','Beredning':'#3B8EEA','Sen fas':'#3B8EEA','Byggstart':'#F4A318','Montage':'#F4A318','Drifttagning klar':'#2ECC8E','Avslutat':'#4A6077'};
    const fc = fasColors[p.fas] || '#4A6077';
    const overlay = document.createElement('div');
    overlay.className = 'tp-overlay';
    overlay.innerHTML = `
      <div class="tp-drawer">
        <button class="tp-drawer-close" id="tpDrawerClose">✕</button>
        <div class="tp-drawer-ibnr">${escHtml(p.id||'')}</div>
        <div class="tp-drawer-title">${escHtml(p.namn)}</div>
        <div class="tp-drawer-fas-badge" style="background:${fc}22;color:${fc};border:1px solid ${fc}44">${escHtml(p.fas||'')}</div>
        ${nextMsHtml}
        <div class="tp-drawer-section">
          <div class="tp-drawer-sec-lbl">MILSTOLPAR</div>${milsHtml}
        </div>
        ${p.blockering?`<div class="tp-drawer-section">
          <div class="tp-drawer-sec-lbl">BLOCKERING</div>
          <div class="tp-drawer-blockering">${escHtml(p.blockering)}</div>
        </div>`:''}
        <div class="tp-drawer-section">
          <div class="tp-drawer-sec-lbl">NOTAT</div>
          <textarea class="tp-drawer-notat" id="tpDrawerNotat" placeholder="Lägg till notat…">${escHtml(p.notat||'')}</textarea>
          <button class="tp-drawer-save" id="tpDrawerSave">Spara notat</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const closeOverlay = () => { overlay.style.opacity='0'; overlay.style.transition='opacity .2s'; setTimeout(()=>overlay.remove(),200); };
    overlay.addEventListener('click', e => { if (e.target===overlay) closeOverlay(); });
    document.getElementById('tpDrawerClose')?.addEventListener('click', closeOverlay);
    document.getElementById('tpDrawerSave')?.addEventListener('click', async () => {
      const notat = document.getElementById('tpDrawerNotat')?.value || '';
      try {
        await api('PUT', `/anslutning/${p.id}`, { notat });
        const proj = AnslState.projekt?.find(x => x.id === p.id);
        if (proj) proj.notat = notat;
        p.notat = notat;
        toast('Notat sparat', 'success');
      } catch(err) { toast('Fel: ' + err.message, 'error'); }
    });
  }

  // ---- bind events ----
  function bindTpEvents(todayX) {
    document.getElementById('tpSearch')?.addEventListener('input', e => { TPS.search = e.target.value; rebuild(); });
    app.querySelectorAll('[data-filter]').forEach(b => b.addEventListener('click', () => { TPS.filter = b.dataset.filter; rebuild(); }));
    app.querySelectorAll('[data-period]').forEach(b => b.addEventListener('click', () => { TPS.period = b.dataset.period; applyPeriodZoom(); rebuild(); }));
    document.getElementById('tpBerSelect')?.addEventListener('change', e => { TPS.filterBeredare = e.target.value; rebuild(); });
    document.getElementById('tpZoomIn')?.addEventListener('click',    () => { TPS.dagBredd = Math.min(40, TPS.dagBredd * 1.25); rebuild(); });
    document.getElementById('tpZoomOut')?.addEventListener('click',   () => { TPS.dagBredd = Math.max(4,  TPS.dagBredd * 0.8);  rebuild(); });
    document.getElementById('tpZoomReset')?.addEventListener('click', () => { TPS.period='halvar'; TPS.dagBredd=18; rebuild(); requestAnimationFrame(()=>scrollToToday(daysBetween(getRange().start,new Date())*TPS.dagBredd)); });
    const ga = document.getElementById('tpGanttArea');
    const ll = document.getElementById('tpLeftList');
    if (ga && ll) ga.addEventListener('scroll', () => { ll.scrollTop = ga.scrollTop; });
    app.querySelectorAll('.tp-left-row, .tp-gantt-row').forEach(row => row.addEventListener('click', () => openTpDrawer(row.dataset.pid)));
    app.querySelectorAll('.tp-gantt-row').forEach(row => {
      row.addEventListener('mouseenter', e => showTpTooltip(row.dataset.pid, e));
      row.addEventListener('mouseleave', hideTpTooltip);
      row.addEventListener('mousemove',  moveTpTooltip);
    });
    scrollToToday(todayX);
  }

  buildUI();
}

boot();
