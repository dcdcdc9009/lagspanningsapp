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
  open(title, bodyHTML, footerHTML = '') {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML   = bodyHTML;
    document.getElementById('modalFooter').innerHTML = footerHTML;
    document.getElementById('modal').classList.remove('hidden');
  },
  close() { document.getElementById('modal').classList.add('hidden'); },
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
    case 'projekt':    renderProjekt(app); break;
    case 'projekt-detail': renderProjektDetail(app, params.id); break;
    case 'artiklar':   renderArtiklar(app); break;
    case 'admin':      renderAdmin(app); break;
    default:           renderProjekt(app);
  }
}

// ----------------------------------------------------------------
// HELPERS
// ----------------------------------------------------------------
function badge(status) {
  const map = {
    'Planerat': 'badge-planerat', 'Pågående': 'badge-pagaende', 'Klart': 'badge-klart',
    'Utkast': 'badge-utkast', 'Granskat': 'badge-granskat', 'Godkänt': 'badge-godkant',
  };
  return `<span class="badge ${map[status] || ''}">${status}</span>`;
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
// VIEW: PROJEKT (list)
// ----------------------------------------------------------------
async function renderProjekt(app) {
  app.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Projekt</h1>
      <button class="btn btn-navy" id="btnNyttProjekt">+ Nytt projekt</button>
    </div>
    <div id="statGrid" class="stat-grid"></div>
    <div class="filter-bar">
      <input type="search" class="form-control" id="sokProjekt" placeholder="Sök projekt…">
      <select class="form-control" id="filtStatus">
        <option value="">Alla statusar</option>
        <option>Planerat</option><option>Pågående</option><option>Klart</option>
      </select>
      <select class="form-control" id="filtBeredare">
        <option value="">Alla beredare</option>
      </select>
    </div>
    <div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Projektnummer</th><th>Projektnamn</th><th>Beredare</th>
            <th>Status</th><th>Startdatum</th><th>Åtgärder</th>
          </tr></thead>
          <tbody id="projektBody"></tbody>
        </table>
      </div>
    </div>`;

  // Load stats
  try {
    const stat = await api('GET', '/projekt/statistik');
    document.getElementById('statGrid').innerHTML = `
      <div class="stat-card"><div class="stat-value">${stat.totalt}</div><div class="stat-label">Totalt</div></div>
      <div class="stat-card"><div class="stat-value">${stat.planerat}</div><div class="stat-label">Planerat</div></div>
      <div class="stat-card"><div class="stat-value">${stat.pagaende}</div><div class="stat-label">Pågående</div></div>
      <div class="stat-card"><div class="stat-value">${stat.klart}</div><div class="stat-label">Klart</div></div>`;
  } catch {}

  // Load beredare filter
  await laddaBeredare();
  const filtBer = document.getElementById('filtBeredare');
  S.beredare.forEach(b => {
    filtBer.innerHTML += `<option>${escHtml(b.namn)}</option>`;
  });

  await laddaProjekt();
  renderProjektRader();

  document.getElementById('sokProjekt').addEventListener('input', renderProjektRader);
  document.getElementById('filtStatus').addEventListener('change', renderProjektRader);
  document.getElementById('filtBeredare').addEventListener('change', renderProjektRader);
  document.getElementById('btnNyttProjekt').addEventListener('click', () => modalNyttProjekt());
}

async function laddaProjekt() {
  S.projekt = (await api('GET', '/projekt')).projekt || [];
}

function renderProjektRader() {
  const sok    = document.getElementById('sokProjekt').value.toLowerCase();
  const status = document.getElementById('filtStatus').value;
  const ber    = document.getElementById('filtBeredare').value;

  let lista = S.projekt.filter(p => {
    if (status && p.status !== status) return false;
    if (ber    && p.beredare !== ber)  return false;
    if (sok && !(`${p.projektnummer} ${p.projektnamn} ${p.beredare}`).toLowerCase().includes(sok)) return false;
    return true;
  });

  const tbody = document.getElementById('projektBody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="muted text-center">Inga projekt hittades</td></tr>`;
    return;
  }
  tbody.innerHTML = lista.map(p => `
    <tr>
      <td class="mono">${escHtml(p.projektnummer)}</td>
      <td><strong>${escHtml(p.projektnamn)}</strong></td>
      <td>${escHtml(p.beredare)}</td>
      <td>${badge(p.status)}</td>
      <td>${p.startdatum || '–'}</td>
      <td class="flex gap-1">
        <button class="btn btn-sm btn-navy" data-id="${p.id}" data-action="oppna">Öppna</button>
        <button class="btn btn-sm btn-outline" data-id="${p.id}" data-action="redigera">Redigera</button>
        <button class="btn btn-sm btn-danger" data-id="${p.id}" data-action="radera">Ta bort</button>
      </td>
    </tr>`).join('');

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

async function modalProjektForm(existing, data = {}) {
  await laddaBeredare();
  const nasta = existing ? '' : ((await api('GET', '/projekt/nasta-nummer')).projektnummer || '');
  const berOptions = S.beredare.map(b =>
    `<option ${data.beredare === b.namn ? 'selected' : ''}>${escHtml(b.namn)}</option>`).join('');

  Modal.open(
    existing ? 'Redigera projekt' : 'Nytt projekt',
    `<form id="projektForm">
      <div class="form-row cols-2">
        <div class="form-group">
          <label class="form-label">Projektnummer <span class="req">*</span></label>
          <input name="projektnummer" class="form-control" value="${escHtml(data.projektnummer || nasta)}" ${existing ? '' : 'required'}>
        </div>
        <div class="form-group">
          <label class="form-label">Status</label>
          <select name="status" class="form-control">
            ${['Planerat','Pågående','Klart'].map(s => `<option ${(data.status||'Planerat')===s?'selected':''}>${s}</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Projektnamn <span class="req">*</span></label>
        <input name="projektnamn" class="form-control" value="${escHtml(data.projektnamn||'')}" required>
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
     <button class="btn btn-secondary" id="avbrytProjekt">Avbryt</button>`
  );

  document.getElementById('avbrytProjekt').addEventListener('click', Modal.close);
  document.getElementById('sparaProjekt').addEventListener('click', async () => {
    const f = document.getElementById('projektForm');
    if (!f.reportValidity()) return;
    const fd = new FormData(f);
    const body = Object.fromEntries(fd.entries());
    try {
      if (existing) {
        await api('PUT', `/projekt/${existing.id}`, body);
        toast('Projekt sparat', 'success');
      } else {
        await api('POST', '/projekt', body);
        toast('Projekt skapat', 'success');
      }
      Modal.close();
      await laddaProjekt();
      renderProjektRader();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----------------------------------------------------------------
// VIEW: PROJEKT DETAIL
// ----------------------------------------------------------------
async function renderProjektDetail(app, id) {
  app.innerHTML = `<div class="text-muted">Laddar…</div>`;
  let p;
  try { p = (await api('GET', `/projekt/${id}`)).projekt; }
  catch (e) { app.innerHTML = `<p class="text-red">Kunde inte ladda projekt: ${e.message}</p>`; return; }

  let protokoll = [];
  try { protokoll = (await api('GET', `/byggprotokoll?projekt_id=${id}`)).byggprotokoll || []; } catch {}

  if (!S.mallar.length) {
    try { S.mallar = (await api('GET', '/mallar')).mallar || []; } catch {}
  }

  app.innerHTML = `
    <div class="page-header">
      <div class="flex items-center gap-2">
        <button class="btn btn-outline btn-sm" id="btnBack">← Tillbaka</button>
        <h1 class="page-title">${escHtml(p.projektnummer)} – ${escHtml(p.projektnamn)}</h1>
        ${badge(p.status)}
      </div>
      <div class="flex gap-1">
        <button class="btn btn-outline btn-sm" id="btnEditProjekt">Redigera projekt</button>
        <a class="btn btn-secondary btn-sm" href="/api/projekt/${id}/materiallista/pdf" target="_blank">⬇ Materiallista PDF</a>
      </div>
    </div>

    <div class="detail-layout">
      <div class="card">
        <div class="card-header"><span class="card-title">Projektinfo</span></div>
        <div class="card-body">
          <dl class="info-dl">
            <dt>Projektnummer</dt><dd>${escHtml(p.projektnummer)}</dd>
            <dt>Beredare</dt><dd>${escHtml(p.beredare)}</dd>
            <dt>Status</dt><dd>${badge(p.status)}</dd>
            <dt>Startdatum</dt><dd>${p.startdatum||'–'}</dd>
            <dt>Skapad</dt><dd>${(p.skapad||'').slice(0,16)}</dd>
            <dt>Uppdaterad</dt><dd>${(p.uppdaterad||'').slice(0,16)}</dd>
          </dl>
          ${p.anteckningar ? `<p class="mt-2 text-sm text-muted">${escHtml(p.anteckningar)}</p>` : ''}
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Byggprotokoll (${protokoll.length})</span>
            <button class="btn btn-navy btn-sm" id="btnNyttProtokoll">+ Nytt protokoll</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th>Mall</th><th>Status</th><th>Skapad</th><th>Uppdaterad</th><th>Åtgärder</th>
              </tr></thead>
              <tbody id="protokollBody"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>`;

  document.getElementById('btnBack').addEventListener('click', () => navigate('projekt'));
  document.getElementById('btnEditProjekt').addEventListener('click', () => modalRedigeraProjekt(p));
  document.getElementById('btnNyttProtokoll').addEventListener('click', () => modalNyttProtokoll(id, renderProtokollRader));

  function renderProtokollRader() {
    const tbody = document.getElementById('protokollBody');
    if (!protokoll.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted text-center">Inga protokoll ännu</td></tr>`;
      return;
    }
    tbody.innerHTML = protokoll.map(bp => `
      <tr>
        <td>${escHtml(bp.mall_namn)}</td>
        <td>${badge(bp.status)}</td>
        <td>${(bp.skapad||'').slice(0,16)}</td>
        <td>${(bp.uppdaterad||'').slice(0,16)}</td>
        <td class="flex gap-1">
          <button class="btn btn-sm btn-navy" data-id="${bp.id}" data-action="oppna">Öppna</button>
          <a class="btn btn-sm btn-secondary" href="/api/byggprotokoll/${bp.id}/pdf" target="_blank">PDF</a>
          <button class="btn btn-sm btn-danger" data-id="${bp.id}" data-action="radera">Ta bort</button>
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
    const label = `<label class="form-label">${escHtml(f.etikett)}${f.obligatorisk ? ' <span class="req">*</span>' : ''}</label>`;
    const hint  = f.hjalp ? `<div class="form-hint">${escHtml(f.hjalp)}</div>` : '';

    if (f.typ === 'number') {
      html += `<div class="form-group">${label}<input type="number" name="${f.faltnamn}" class="form-control" value="${val}" min="0" step="any" ${f.obligatorisk?'required':''}>${hint}</div>`;
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
      const opts = artiklar.map(a =>
        `<option value="${a.id}" ${val == a.id ? 'selected' : ''}>${escHtml(a.artikelnamn)}</option>`
      ).join('');
      html += `<div class="form-group">${label}<select name="${f.faltnamn}" class="form-control" ${f.obligatorisk?'required':''}><option value="">– välj –</option>${opts}</select>${hint}</div>`;
    } else if (f.typ === 'select') {
      let alts = [];
      try { alts = JSON.parse(f.alternativ || '[]'); } catch {}
      const opts = alts.map(a => `<option ${val===a?'selected':''}>${escHtml(a)}</option>`).join('');
      html += `<div class="form-group">${label}<select name="${f.faltnamn}" class="form-control">${opts}</select>${hint}</div>`;
    } else {
      html += `<div class="form-group">${label}<input type="text" name="${f.faltnamn}" class="form-control" value="${escHtml(val)}" ${f.obligatorisk?'required':''}>${hint}</div>`;
    }
  }
  return html;
}

// ----------------------------------------------------------------
// MODAL: VISA/REDIGERA PROTOKOLL
// ----------------------------------------------------------------
async function modalVisaProtokoll(bpid, projektId, protokollLista, onDone) {
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

  document.getElementById('btnLaggTillRad').addEventListener('click', () => modalLaggTillRad(rader, renderRadBody));

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
            <input name="foretag_namn" class="form-control" value="${escHtml(inst.foretag_namn||'')}"></div>
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
  if (e.target === document.getElementById('modal')) Modal.close();
});
document.getElementById('modalClose').addEventListener('click', Modal.close);

// ----------------------------------------------------------------
// NAV CLICKS
// ----------------------------------------------------------------
document.querySelectorAll('[data-view]').forEach(el => {
  el.addEventListener('click', () => navigate(el.dataset.view));
});

// ----------------------------------------------------------------
// BOOT
// ----------------------------------------------------------------
(async function boot() {
  // Check if already logged in
  try {
    await api('GET', '/admin/check');
    S.admin = true;
    document.getElementById('adminBadge').classList.remove('hidden');
  } catch {}

  const hash = location.hash.replace('#', '');
  const [view, ...rest] = hash.split('/');
  navigate(view || 'projekt', { id: rest[0] });
})();
