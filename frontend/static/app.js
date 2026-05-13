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
  switch (view) {
    case 'projekt':         renderProjekt(app); break;
    case 'projekt-detail':  renderProjektDetail(app, params.id); break;
    case 'artiklar':        renderArtiklar(app); break;
    case 'konstruktioner':  renderKonstruktioner(app); break;
    case 'admin':           renderAdmin(app); break;
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
const FAS_TROSKEL = { 'Beredning': 30, 'Projektledning': 21, 'Utförda': 14 };
const FAS_CSS = {
  'Beredning': 'badge-beredning', 'Projektledning': 'badge-offert', 'Utförda': 'badge-klart',
};

function badgeFas(fas) {
  if (!fas) return '<span class="text-muted" style="font-size:12px">Ingen fas</span>';
  return `<span class="badge ${FAS_CSS[fas] || ''}">${escHtml(fas)}</span>`;
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
// VIEW: PROJEKT (dashboard + lista)
// ----------------------------------------------------------------
async function renderProjekt(app) {
  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Projektöversikt</h1>
      <button class="btn btn-navy" id="btnNyttProjekt">+ Nytt projekt</button>
    </div>
    <div id="fasDashboard" class="fas-dashboard"></div>
    <div class="filter-bar">
      <input type="search" class="form-control" id="sokProjekt" placeholder="Sök projekt…">
      <select class="form-control" id="filtBeredare">
        <option value="">Alla beredare</option>
      </select>
      <button class="btn btn-outline btn-sm" id="btnRensaFas" style="display:none">✕ Rensa fasfilter</button>
    </div>
    <div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Projektnr</th><th>Projektnamn</th><th>Kund</th>
            <th>Fas</th><th>Dagar i fas</th><th>Beredare</th><th>Åtgärder</th>
          </tr></thead>
          <tbody id="projektBody"></tbody>
        </table>
      </div>
    </div>`;

  let aktivFasFilter = '';

  await laddaBeredare();
  const filtBer = document.getElementById('filtBeredare');
  S.beredare.forEach(b => { filtBer.innerHTML += `<option>${escHtml(b.namn)}</option>`; });

  // Fas-dashboard
  let fasStatistik = {};
  try {
    const fs = await api('GET', '/projekt/fas-statistik');
    fasStatistik = fs.fas_statistik || {};
  } catch {}
  const fasDash = document.getElementById('fasDashboard');
  fasDash.innerHTML = FASER.map(fas => `
    <div class="fas-kort" data-fas="${escHtml(fas)}">
      <div class="fas-kort-antal">${fasStatistik[fas] ?? 0}</div>
      <div class="fas-kort-namn">${escHtml(fas)}</div>
    </div>`).join('');
  fasDash.querySelectorAll('.fas-kort').forEach(k => {
    k.addEventListener('click', () => {
      const fas = k.dataset.fas;
      if (aktivFasFilter === fas) {
        aktivFasFilter = '';
        fasDash.querySelectorAll('.fas-kort').forEach(x => x.classList.remove('aktiv-filter'));
        document.getElementById('btnRensaFas').style.display = 'none';
      } else {
        aktivFasFilter = fas;
        fasDash.querySelectorAll('.fas-kort').forEach(x => x.classList.toggle('aktiv-filter', x.dataset.fas === fas));
        document.getElementById('btnRensaFas').style.display = '';
      }
      renderProjektRader();
    });
  });
  document.getElementById('btnRensaFas').addEventListener('click', () => {
    aktivFasFilter = '';
    fasDash.querySelectorAll('.fas-kort').forEach(x => x.classList.remove('aktiv-filter'));
    document.getElementById('btnRensaFas').style.display = 'none';
    renderProjektRader();
  });

  await laddaProjekt();
  renderProjektRader();

  document.getElementById('sokProjekt').addEventListener('input', renderProjektRader);
  document.getElementById('filtBeredare').addEventListener('change', renderProjektRader);
  document.getElementById('btnNyttProjekt').addEventListener('click', () => modalNyttProjekt());

  function renderProjektRader() {
    const sok = document.getElementById('sokProjekt').value.toLowerCase();
    const ber = document.getElementById('filtBeredare').value;
    let lista = S.projekt.filter(p => {
      if (aktivFasFilter && p.fas !== aktivFasFilter) return false;
      if (ber && p.beredare !== ber) return false;
      if (sok && !(`${p.projektnummer} ${p.projektnamn} ${p.beredare} ${p.kund||''}`).toLowerCase().includes(sok)) return false;
      return true;
    });
    const tbody = document.getElementById('projektBody');
    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="muted text-center">Inga projekt hittades</td></tr>`;
      return;
    }
    tbody.innerHTML = lista.map(p => {
      const dagar = dagarIFas(p.fas_startdatum);
      const flagg = rodFlaggHtml(p.fas, dagar);
      const dagarTxt = dagar !== null ? `${dagar}d ${flagg}` : '–';
      return `<tr>
        <td class="mono">${escHtml(p.projektnummer)}</td>
        <td><strong>${escHtml(p.projektnamn)}</strong></td>
        <td>${escHtml(p.kund || '–')}</td>
        <td>${badgeFas(p.fas)}</td>
        <td>${dagarTxt}</td>
        <td>${escHtml(p.beredare)}</td>
        <td class="flex gap-1">
          <button class="btn btn-sm btn-navy" data-id="${p.id}" data-action="oppna">Öppna</button>
          <button class="btn btn-sm btn-outline" data-id="${p.id}" data-action="redigera">Redigera</button>
          <button class="btn btn-sm btn-danger" data-id="${p.id}" data-action="radera">✕</button>
        </td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('button[data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        const action = btn.dataset.action;
        if (action === 'oppna') {
          navigate('projekt-detail', { id });
        } else if (action === 'redigera') {
          const p = S.projekt.find(x => x.id == id);
          modalRedigeraProjekt(p);
        } else if (action === 'radera') {
          const p = S.projekt.find(x => x.id == id);
          const ok = await confirm('Ta bort projekt', `Ta bort "${p.projektnamn}"? Alla byggprotokoll tas också bort.`);
          if (!ok) return;
          try {
            await api('DELETE', `/projekt/${id}`);
            toast('Projekt borttaget', 'success');
            await laddaProjekt();
            renderProjektRader();
          } catch (e) { toast(e.message, 'error'); }
        }
      });
    });
  }
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

async function modalProjektForm(existing, data = {}, onSuccess = null) {
  await laddaBeredare();
  const nasta = existing ? '' : ((await api('GET', '/projekt/nasta-nummer')).projektnummer || '');
  const berOptions = S.beredare.map(b =>
    `<option ${data.beredare === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('');
  const fasOptions = ['', ...FASER].map(f =>
    `<option value="${f}" ${(data.fas||'')=== f ? 'selected' : ''}>${f || '– ingen fas –'}</option>`).join('');

  Modal.open(
    existing ? 'Redigera projekt' : 'Nytt projekt',
    `<form id="projektForm">
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Projektnummer <span class="req">*</span></label>
          <input name="projektnummer" class="form-control" value="${escHtml(data.projektnummer || nasta)}" ${existing ? '' : 'required'}>
        </div>
        <div class="form-group">
          <label class="form-label">Fas</label>
          <select name="fas" class="form-control">${fasOptions}</select>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Projektnamn <span class="req">*</span></label>
        <input name="projektnamn" class="form-control" value="${escHtml(data.projektnamn||'')}" required>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Kund</label>
          <input name="kund" class="form-control" value="${escHtml(data.kund||'')}">
        </div>
        <div class="form-group">
          <label class="form-label">Anslutningspunkt</label>
          <input name="anslutningspunkt" class="form-control" value="${escHtml(data.anslutningspunkt||'')}">
        </div>
      </div>
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Beredare <span class="req">*</span></label>
          <select name="beredare" class="form-control" required>
            <option value="">– välj –</option>${berOptions}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Startdatum</label>
          <input type="date" name="startdatum" class="form-control" value="${data.startdatum||''}">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Anteckningar</label>
        <textarea name="anteckningar" class="form-control">${escHtml(data.anteckningar||'')}</textarea>
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
    const fd = new FormData(f);
    const body = Object.fromEntries(fd.entries());
    try {
      let result;
      if (existing) {
        result = await api('PUT', `/projekt/${existing.id}`, body);
        toast('Projekt sparat', 'success');
      } else {
        result = await api('POST', '/projekt', body);
        toast('Projekt skapat', 'success');
      }
      Modal.close();
      if (onSuccess) {
        await onSuccess(result);
      } else {
        navigate('projekt');
      }
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// VIEW: PROJEKT DETAIL
// ----------------------------------------------------------------
async function renderProjektDetail(app, id) {
  app.innerHTML = `<div class="text-muted">Laddar…</div>`;
  let p, fasData, tillstandLista, aktiviteter, protokoll;
  try {
    [p, fasData, tillstandLista, aktiviteter, protokoll] = await Promise.all([
      api('GET', `/projekt/${id}`).then(r => r.projekt),
      api('GET', `/projekt/${id}/fas`).catch(() => ({ fas: null, historik: [] })),
      api('GET', `/projekt/${id}/tillstand`).then(r => r.tillstand || []).catch(() => []),
      api('GET', `/projekt/${id}/aktiviteter`).then(r => r.aktiviteter || []).catch(() => []),
      api('GET', `/byggprotokoll?projekt_id=${id}`).then(r => r.byggprotokoll || []).catch(() => []),
    ]);
  } catch (e) {
    app.innerHTML = `<p class="text-red">Kunde inte ladda projekt: ${e.message}</p>`;
    return;
  }
  if (!S.mallar.length) {
    try { S.mallar = (await api('GET', '/mallar')).mallar || []; } catch {}
  }

  const fasHistorik = fasData.historik || [];
  const aktuellFas = p.fas || null;

  function fasTidslinjeHtml() {
    return `<div class="fas-tidslinje" id="fasTidslinje">` +
      FASER.map((fas, i) => {
        const hrad = fasHistorik.find(h => h.fas === fas);
        const arAktiv = fas === aktuellFas;
        const arKlar  = fasHistorik.some(h => h.fas === fas && h.slutdatum);
        let cls = arAktiv ? 'aktiv' : arKlar ? 'klar' : '';
        const datumTxt = hrad ? `<span class="fas-steg-datum">${hrad.startdatum || ''}</span>` : '';
        return `<div class="fas-steg ${cls}" data-fas="${escHtml(fas)}" title="Klicka för att sätta fas: ${escHtml(fas)}">
          <span class="fas-steg-nr">${i + 1}.</span>${escHtml(fas)}${datumTxt}
        </div>`;
      }).join('') +
    `</div>`;
  }

  function tillstandHtml(lista) {
    if (!lista.length) return `<p class="text-muted" style="padding:12px;font-size:13px">Inga tillstånd registrerade</p>`;
    const badgeTill = { 'Inväntas': 'badge-inväntas', 'Mottaget': 'badge-mottaget', 'Ej krävs': 'badge-ej-kravs' };
    return `<ul class="tillstand-lista">` + lista.map(t => `
      <li class="tillstand-rad" data-tid="${t.id}">
        <span class="tillstand-namn">${escHtml(t.namn)}</span>
        ${t.datum ? `<span class="tillstand-datum">${t.datum}</span>` : ''}
        <span class="badge ${badgeTill[t.status] || ''}">${escHtml(t.status)}</span>
        <button class="btn btn-sm btn-outline" data-tid="${t.id}" data-action="edit-till">✎</button>
        <button class="btn btn-sm btn-danger" data-tid="${t.id}" data-action="del-till">✕</button>
      </li>`).join('') + `</ul>`;
  }

  function aktivitetIkon(typ) {
    return { 'fas-byte': '🔄', 'anteckning': '📝' }[typ] || '•';
  }

  function aktivitetHtml(lista) {
    if (!lista.length) return `<p class="text-muted" style="padding:12px;font-size:13px">Inga aktiviteter ännu</p>`;
    return `<ul class="aktivitets-lista">` + lista.map(a => `
      <li class="aktivitets-rad">
        <span class="aktivitets-tid">${(a.tidpunkt||'').slice(0,16)}</span>
        <span class="aktivitets-ikon">${aktivitetIkon(a.typ)}</span>
        <span class="aktivitets-text">${escHtml(a.beskrivning)}</span>
      </li>`).join('') + `</ul>`;
  }

  app.innerHTML = `
    <div class="page-header">
      <div class="flex items-center gap-2" style="flex-wrap:wrap;gap:8px">
        <button class="btn btn-outline btn-sm" id="btnBack">← Tillbaka</button>
        <h1 class="page-title">${escHtml(p.projektnummer)} – ${escHtml(p.projektnamn)}</h1>
        ${badgeFas(aktuellFas)}
      </div>
      <div class="flex gap-1" style="flex-wrap:wrap">
        <button class="btn btn-outline btn-sm" id="btnEditProjekt">Redigera</button>
        <button class="btn btn-navy btn-sm" id="btnGaTillByggprotokoll">Byggprotokoll / Materiallista →</button>
        <a class="btn btn-secondary btn-sm" href="/api/projekt/${id}/materiallista/pdf" target="_blank">⬇ PDF</a>
        <a class="btn btn-outline btn-sm" href="/api/projekt/${id}/materiallista/excel" target="_blank">⬇ Excel</a>
      </div>
    </div>

    <div class="detail-layout">
      <!-- VÄNSTER: Grundinfo -->
      <div>
        <div class="card mb-2">
          <div class="card-header"><span class="card-title">Projektinfo</span></div>
          <div class="card-body">
            <dl class="info-dl">
              <dt>Projektnummer</dt><dd class="mono">${escHtml(p.projektnummer)}</dd>
              <dt>Kund</dt><dd>${escHtml(p.kund || '–')}</dd>
              <dt>Anslutningspunkt</dt><dd>${escHtml(p.anslutningspunkt || '–')}</dd>
              <dt>Beredare</dt><dd>${escHtml(p.beredare)}</dd>
              <dt>Status</dt><dd>${badge(p.status)}</dd>
              <dt>Startdatum</dt><dd>${p.startdatum || '–'}</dd>
              <dt>Skapad</dt><dd>${(p.skapad||'').slice(0,16)}</dd>
            </dl>
            ${p.anteckningar ? `<p class="mt-2 text-sm text-muted">${escHtml(p.anteckningar)}</p>` : ''}
          </div>
        </div>
      </div>

      <!-- HÖGER: Fas, Tillstånd, Aktiviteter -->
      <div>
        <!-- FAS-TIDSLINJE -->
        <div class="card mb-2">
          <div class="card-header">
            <span class="card-title">Fas</span>
            <span class="text-sm text-muted">Klicka för att byta fas</span>
          </div>
          <div class="card-body" style="padding:12px">
            ${fasTidslinjeHtml()}
          </div>
        </div>

        <!-- TILLSTÅND -->
        <div class="card mb-2">
          <div class="card-header">
            <span class="card-title">Tillstånd</span>
            <button class="btn btn-navy btn-sm" id="btnNyttTillstand">+ Lägg till</button>
          </div>
          <div id="tillstandKontainer">${tillstandHtml(tillstandLista)}</div>
        </div>

        <!-- AKTIVITETSLOGG -->
        <div class="card mb-2">
          <div class="card-header">
            <span class="card-title">Aktivitetslogg</span>
            <button class="btn btn-outline btn-sm" id="btnNyAktivitet">+ Anteckning</button>
          </div>
          <div id="aktivitetKontainer">${aktivitetHtml(aktiviteter)}</div>
        </div>

        <!-- BYGGPROTOKOLL -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Byggprotokoll (${protokoll.length})</span>
            <button class="btn btn-navy btn-sm" id="btnNyttProtokoll">+ Nytt protokoll</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Mall</th><th>Status</th><th>Skapad</th><th>Åtgärder</th></tr></thead>
              <tbody id="protokollBody"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>`;

  // ── Tillbaka ──
  document.getElementById('btnBack').addEventListener('click', () => navigate('projekt'));

  // ── Redigera projekt ──
  document.getElementById('btnEditProjekt').addEventListener('click', () =>
    modalRedigeraProjekt(p));

  // ── Gå till Byggprotokoll/Materiallista-fliken ──
  document.getElementById('btnGaTillByggprotokoll').addEventListener('click', () => {
    S.valtProjektKonstr = String(id);
    navigate('konstruktioner');
  });

  // ── Nytt protokoll ──
  document.getElementById('btnNyttProtokoll').addEventListener('click', () =>
    modalNyttProtokoll(id, () => renderProjektDetail(app, id)));

  // ── Fas-tidslinje klick ──
  document.getElementById('fasTidslinje').querySelectorAll('.fas-steg').forEach(el => {
    el.addEventListener('click', async () => {
      const nyFas = el.dataset.fas;
      if (nyFas === aktuellFas) return;
      try {
        await api('POST', `/projekt/${id}/fas`, { fas: nyFas });
        toast(`Fas satt: ${nyFas}`, 'success');
        renderProjektDetail(app, id);
      } catch (e) { toast(e.message, 'error'); }
    });
  });

  // ── Nytt tillstånd ──
  document.getElementById('btnNyttTillstand').addEventListener('click', () =>
    modalTillstandForm(id, null, () => renderProjektDetail(app, id)));

  // ── Tillstånd åtgärder (edit/delete) ──
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
        toast('Tillstånd borttaget', 'success');
        renderProjektDetail(app, id);
      } catch (e) { toast(e.message, 'error'); }
    }
  });

  // ── Ny aktivitet ──
  document.getElementById('btnNyAktivitet').addEventListener('click', () =>
    modalNyAktivitet(id, () => renderProjektDetail(app, id)));

  // ── Byggprotokoll-lista ──
  function renderProtokollRader() {
    const tbody = document.getElementById('protokollBody');
    if (!protokoll.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="muted text-center">Inga protokoll ännu</td></tr>`;
      return;
    }
    tbody.innerHTML = protokoll.map(bp => `
      <tr>
        <td>${escHtml(bp.mall_namn)}</td>
        <td>${badge(bp.status)}</td>
        <td>${(bp.skapad||'').slice(0,16)}</td>
        <td class="flex gap-1">
          <button class="btn btn-sm btn-navy" data-id="${bp.id}" data-action="oppna">Öppna</button>
          <a class="btn btn-sm btn-secondary" href="/api/byggprotokoll/${bp.id}/pdf" target="_blank">PDF</a>
          <button class="btn btn-sm btn-danger" data-id="${bp.id}" data-action="radera">✕</button>
        </td>
      </tr>`).join('');
    tbody.querySelectorAll('button[data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const bpid = btn.dataset.id;
        if (btn.dataset.action === 'oppna') {
          modalVisaProtokoll(bpid, id, protokoll, renderProtokollRader);
        } else if (btn.dataset.action === 'radera') {
          const ok = await confirm('Ta bort protokoll', 'Ta bort detta byggprotokoll?');
          if (!ok) return;
          try {
            await api('DELETE', `/byggprotokoll/${bpid}`);
            protokoll = protokoll.filter(x => x.id != bpid);
            toast('Protokoll borttaget', 'success');
            renderProtokollRader();
          } catch (e) { toast(e.message, 'error'); }
        }
      });
    });
  }
  renderProtokollRader();
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
     <div id="inlineRadForm" style="display:none;background:#f5f3ff;border:1px solid #c4b5fd;border-radius:6px;padding:12px;margin-top:8px">
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
      <div class="flex gap-2 items-center">
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
    const sel = document.getElementById('projektValjare');
    // Behåll bara default-option, rensa resten
    while (sel.options.length > 1) sel.remove(1);
    allaProjekt.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.projektnummer} – ${p.projektnamn}`;
      sel.appendChild(opt);
    });
    if (valjId) sel.value = valjId;
  }

  await laddaProjektDropdown(S.valtProjektKonstr);

  const sel = document.getElementById('projektValjare');

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
    modalProjektForm(null, {}, async (result) => {
      const nyprojekt = result.projekt;
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
          <a class="btn btn-secondary" href="/api/konstruktioner/materiallista/pdf?projekt_id=${projektId}" target="_blank">⬇ Materiallista PDF</a>
          <a class="btn btn-outline" href="/api/konstruktioner/materiallista/excel?projekt_id=${projektId}" target="_blank">⬇ Materiallista Excel</a>
          <button class="btn btn-navy" id="btnNyKonstr">+ Ny konstruktion</button>
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
    const färg = kvar < 0 ? '#dc2626' : kvar <= 2 ? '#d97706' : '#7c3aed';
    return `
      <div style="background:#f5f3ff;border:1px solid #c4b5fd;border-radius:6px;padding:10px 14px;margin-bottom:10px">
        <div style="font-weight:600;color:#2e1065;margin-bottom:6px;font-size:13px">Moduler – ${escHtml(k.namn)}</div>
        <div style="display:flex;gap:16px;font-size:12px;margin-bottom:6px">
          <span>Kapacitet: <strong>${kapacitet}</strong></span>
          <span>Använt: <strong>${anvant}</strong></span>
          <span style="color:${färg}">Kvar: <strong>${kvar}</strong></span>
        </div>
        <div style="background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden">
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

  function byggModalBody() {
    return `
      <div class="flex gap-2 items-center mb-2 flex-wrap">
        ${badgeTyp(k.typ)}
        ${k.byggnr ? `<span class="text-muted text-sm">Byggnr: <strong>${escHtml(k.byggnr)}</strong></span>` : ''}
        ${k.fri_id ? `<span class="text-muted text-sm">ID: <strong>${escHtml(k.fri_id)}</strong></span>` : ''}
        <select id="konstrStatus" class="form-control" style="width:140px">${statusOpts}</select>
        <span class="ml-auto text-sm text-muted">Skapad: ${(k.skapad || '').slice(0, 10)}</span>
      </div>
      ${k.anmarkning ? `<p class="text-sm text-muted mb-2" style="background:#f5f3ff;padding:6px 10px;border-radius:4px">${escHtml(k.anmarkning)}</p>` : ''}
      <div id="konstrModulIndikator">${modulIndikatorHtml(rader)}</div>
      <div id="konstrRadWrapper">${radTabellHtml(rader)}</div>
      <div class="mt-2 flex gap-1 items-center">
        <button class="btn btn-outline btn-sm" id="btnKonstrLaggTillRad">+ Lägg till rad</button>
      </div>
      <div id="konstrInlineForm" style="display:none;background:#f5f3ff;border:1px solid #c4b5fd;border-radius:6px;padding:12px;margin-top:8px">
        <div class="form-row cols-2" style="margin-bottom:6px">
          <div class="form-group" style="margin:0">
            <label class="form-label">Kategori</label>
            <select id="konstrInlineKat" class="form-control">
              <option value="">– alla –</option>
              ${S.kategorier.map(k2 => `<option value="${k2.id}">${escHtml(k2.namn)}</option>`).join('')}
            </select>
          </div>
          <div class="form-group" style="margin:0">
            <label class="form-label">Artikel</label>
            <select id="konstrInlineArt" class="form-control"><option value="">Laddar...</option></select>
          </div>
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
    `<button class="btn btn-success" id="sparaKonstrModal">Spara</button>
     <a class="btn btn-secondary" href="/api/konstruktioner/${kid}/pdf" target="_blank">⬇ PDF</a>
     <button class="btn btn-outline" id="avbrytKonstrModal">Stäng</button>`
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
    radBody.addEventListener('input', () => { syncRader(); uppdateraModulIndikator(); });
    radBody.addEventListener('click', e => {
      const btn = e.target.closest('button[data-del]');
      if (!btn) return;
      syncRader();
      rader.splice(parseInt(btn.dataset.del), 1);
      renderRadWrapper();
    });
  }

  bindRadEvents();

  // Inline lägg till rad
  async function laddaKonstrArtiklar() {
    const katId = document.getElementById('konstrInlineKat').value;
    const sel   = document.getElementById('konstrInlineArt');
    sel.innerHTML = '<option value="">Laddar...</option>';
    try {
      const url  = katId ? `/artiklar?kategori_id=${katId}` : '/artiklar';
      const arts = (await api('GET', url)).artiklar || [];
      sel.innerHTML = '<option value="">– välj artikel –</option>' +
        arts.map(a => `<option value="${a.id}"
            data-enhet="${escHtml(a.enhet || '')}"
            data-kat="${escHtml(a.kategori_namn || '')}"
            data-moduler="${a.moduler || 0}">
          ${escHtml(a.artikelnamn)}</option>`).join('');
    } catch { sel.innerHTML = '<option value="">Fel vid laddning</option>'; }
  }

  document.getElementById('btnKonstrLaggTillRad').addEventListener('click', async () => {
    const form    = document.getElementById('konstrInlineForm');
    const visible = form.style.display !== 'none';
    form.style.display = visible ? 'none' : '';
    if (!visible) await laddaKonstrArtiklar();
  });

  document.getElementById('konstrInlineStang').addEventListener('click', () => {
    document.getElementById('konstrInlineForm').style.display = 'none';
  });

  document.getElementById('konstrInlineKat').addEventListener('change', laddaKonstrArtiklar);

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
      artikelnamn: opt.textContent.trim(),
      enhet:       opt.dataset.enhet || '',
      antal,
      moduler,
      anteckning:  ant,
    });
    renderRadWrapper();
    document.getElementById('konstrInlineAntal').value = '1';
    document.getElementById('konstrInlineAnt').value   = '';
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
    });
  }

  document.getElementById('avbrytKonstrModal').addEventListener('click', Modal.close);

  document.getElementById('sparaKonstrModal').addEventListener('click', async () => {
    syncRader();
    const egkData = [];
    document.querySelectorAll('#konstrEgkList .egk-item[data-egk-id]').forEach(item => {
      egkData.push({
        id:          parseInt(item.dataset.egkId),
        utford:      item.querySelector('.egk-utford').checked ? 1 : 0,
        ej_relevant: item.querySelector('.egk-ej-rel').checked ? 1 : 0,
      });
    });
    const nyStatus    = document.getElementById('konstrStatus').value;
    const nyAnmarkning = document.getElementById('konstrAnt').value;
    try {
      await api('PUT', `/konstruktioner/${kid}`, {
        status:     nyStatus,
        anmarkning: nyAnmarkning,
        rader,
        egenkontroll: egkData,
      });
      toast('Konstruktion sparad', 'success');
      Modal.close();
      onDone && await onDone();
    } catch (e) { toast(e.message, 'error'); }
  });
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
        <thead><tr><th>Artikelnamn</th><th>Kategori</th><th>Enhet</th><th>Aktiv</th><th>Åtgärder</th></tr></thead>
        <tbody id="admArtBody"></tbody>
      </table>
    </div>`;

  function render(lista) {
    const sok = document.getElementById('sokAdmArt').value.toLowerCase();
    const filtered = lista.filter(a => !sok || a.artikelnamn.toLowerCase().includes(sok));
    document.getElementById('admArtBody').innerHTML = filtered.map(a => `
      <tr>
        <td>${escHtml(a.artikelnamn)}</td>
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
    body.aktiv = document.getElementById('artAktiv').checked ? 1 : 0;
    try {
      if (art) await api('PUT', `/admin/artiklar/${art.id}`, body);
      else     await api('POST', '/admin/artiklar', body);
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
        <h1 class="login-title">Lågspänningsberedning</h1>
        <p class="login-sub">Ange lösenord för att fortsätta</p>
        <form id="loginForm" class="login-form">
          <div class="form-group">
            <input type="password" id="loginPw" class="form-control login-input"
                   placeholder="Lösenord" autofocus required>
          </div>
          <div id="loginFel" class="login-fel hidden">Fel lösenord. Försök igen.</div>
          <button type="submit" class="btn btn-navy login-btn">Logga in</button>
        </form>
      </div>
    </div>`;

  document.getElementById('loginForm').addEventListener('submit', async e => {
    e.preventDefault();
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
        body: JSON.stringify({ losenord: pw }),
      });
      if (!r.ok) throw new Error('fel');
      sessionStorage.setItem('logged_in', '1');
      document.querySelector('.topnav').style.display = '';
      await boot();
    } catch {
      felDiv.classList.remove('hidden');
      document.getElementById('loginPw').value = '';
      document.getElementById('loginPw').focus();
      btn.disabled = false;
      btn.textContent = 'Logga in';
    }
  });
}

// ----------------------------------------------------------------
// BOOT
// ----------------------------------------------------------------
async function boot() {
  // Kräv inloggning vid varje ny webbläsarsession (ny flik/fönster)
  if (!sessionStorage.getItem('logged_in')) {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    visaLoginSkarm();
    return;
  }

  // Kolla app-inloggning
  let loggedIn = false;
  try {
    const r = await fetch('/api/auth/status', { credentials: 'same-origin' });
    const s = await r.json();
    loggedIn = !!s.loggedin;
  } catch {}

  if (!loggedIn) { visaLoginSkarm(); return; }

  // Visa navbar och logga ut-knapp
  document.querySelector('.topnav').style.display = '';
  const navRight = document.getElementById('navRight');
  if (navRight && !navRight.querySelector('.btn-logout')) {
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

  // Kolla admin-session
  try {
    await api('GET', '/admin/check');
    S.admin = true;
    document.getElementById('adminBadge').classList.remove('hidden');
  } catch {}

  const hash = location.hash.replace('#', '');
  const [view, ...rest] = hash.split('/');
  navigate(view || 'projekt', { id: rest[0] });
}

boot();
