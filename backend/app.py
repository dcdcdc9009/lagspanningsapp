import os, hashlib, json, time
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from flask import Flask, jsonify, request, session, send_from_directory, Response
from database import get_db, init_db, DB_PATH
from models import rows_to_list, row_to_dict, nu, nasta_projektnummer
from ruttimport import gissa_mappning, validera_rader, rubrik_signatur, IMPORT_FALT
from ruttrestid import bygg_matris
from ruttopt import optimera as kor_optimering, berakna_rutt
from mall_berakning import berakna

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__,
            static_folder=os.path.join(FRONTEND_DIR, 'static'),
            static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'lagspanning-dev-key-byt-i-prod')
app.config['JSON_AS_ASCII'] = False
# Sessionskakor – fungerar på Railway (HTTPS) och lokalt (HTTP)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('RAILWAY_ENVIRONMENT') is not None
# Session-timeout: 8 timmar
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# ── Rate limiting – inbyggd, inga externa paket ───────────────────────────────
_login_attempts: dict = defaultdict(list)
_RATE_WINDOW = 60   # sekunder
_RATE_MAX    = 5    # max försök per fönster

def _rate_ok(ip: str) -> bool:
    """Returnerar True om IP får försöka logga in, annars False."""
    now = time.time()
    giltiga = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    _login_attempts[ip] = giltiga
    if len(giltiga) >= _RATE_MAX:
        return False
    _login_attempts[ip].append(now)
    return True


# ============================================================
# HJÄLP
# ============================================================

def fel(msg, kod=400):
    return jsonify({'fel': msg}), kod


def _num(v):
    """Tolka till float, annars None (för koordinater)."""
    try:
        return float(v) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def admin_required(f):
    @wraps(f)
    def inner(*a, **kw):
        if not session.get('admin'):
            return fel('Administratörsinloggning krävs.', 401)
        return f(*a, **kw)
    return inner


def artikel_required(f):
    """Tillåter admin ELLER användare med behörighet att hantera artiklar."""
    @wraps(f)
    def inner(*a, **kw):
        if not (session.get('admin') or session.get('far_artiklar')):
            return fel('Behörighet att hantera artiklar krävs.', 401)
        return f(*a, **kw)
    return inner


# Rutter som är tillgängliga utan app-inloggning
_OPEN_ROUTES = {'/api/auth/login', '/api/auth/status', '/api/auth/logout',
                '/api/admin/login', '/api/debug'}

@app.before_request
def kraver_inloggning():
    if not request.path.startswith('/api/'):
        return  # HTML/CSS/JS serveras alltid
    if request.path in _OPEN_ROUTES:
        return
    if not session.get('loggedin'):
        return fel('Inloggning krävs.', 401)


# ============================================================
# FRONTEND
# ============================================================

@app.get('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.get('/api/debug')
def debug_info():
    """Visar vilken databasfil appen använder – för felsökning."""
    info = {
        'db_path': DB_PATH,
        'db_abs_path': os.path.abspath(DB_PATH),
        'db_exists': os.path.isfile(DB_PATH),
        'db_size_bytes': os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else 0,
        'db_dir_exists': os.path.isdir(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else True,
        'DATABASE_PATH_env': os.environ.get('DATABASE_PATH', '(ej satt)'),
    }
    try:
        with get_db() as conn:
            info['beredare_antal'] = conn.execute("SELECT COUNT(*) FROM beredare").fetchone()[0]
            info['projekt_antal'] = conn.execute("SELECT COUNT(*) FROM projekt").fetchone()[0]
            info['db_skrivbar'] = True
    except Exception as e:
        info['db_skrivbar'] = False
        info['db_fel'] = str(e)
    return jsonify(info)


# ============================================================
# ADMIN – AUTH
# ============================================================

@app.post('/api/admin/login')
def admin_login():
    ip = request.remote_addr or 'unknown'
    if not _rate_ok(f'admin:{ip}'):
        return fel('För många inloggningsförsök. Försök igen om en minut.', 429)
    d = request.get_json(silent=True) or {}
    pw = (d.get('losenord') or '').strip()
    with get_db() as conn:
        rad = conn.execute("SELECT varde FROM installningar WHERE nyckel='admin_losenord'").fetchone()
    if rad and rad['varde'] == hash_pw(pw):
        session.permanent = True
        session['admin'] = True
        return jsonify({'ok': True})
    return fel('Fel lösenord.', 401)


@app.post('/api/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return jsonify({'ok': True})


# ============================================================
# APP – AUTH (lösenordsskydd)
# ============================================================

def _app_losenord():
    """Hämtar app-lösenordet: ENV > installningar > standardvärde."""
    env_pw = os.environ.get('APP_PASSWORD', '').strip()
    if env_pw:
        return env_pw
    try:
        with get_db() as conn:
            rad = conn.execute(
                "SELECT varde FROM installningar WHERE nyckel='app_losenord'").fetchone()
            if rad and rad['varde']:
                return rad['varde']
    except Exception:
        pass
    return 'oneco'   # standardlösenord om inget är satt


@app.get('/api/auth/status')
def auth_status():
    return jsonify({
        'loggedin':     bool(session.get('loggedin')),
        'anvandarnamn': session.get('anvandarnamn'),
        'namn':         session.get('namn'),
        'roll':         session.get('roll'),
        'beredare':     session.get('beredare'),
        'admin':        bool(session.get('admin')),
        'far_artiklar': bool(session.get('far_artiklar')),
        'har_profil':   bool(session.get('user_id')),
    })


@app.post('/api/auth/login')
def auth_login():
    ip = request.remote_addr or 'unknown'
    if not _rate_ok(f'auth:{ip}'):
        return fel('För många inloggningsförsök. Försök igen om en minut.', 429)
    d  = request.get_json(silent=True) or {}
    anvandarnamn = (d.get('anvandarnamn') or '').strip()
    pw = (d.get('losenord') or '').strip()

    # Inloggning med personligt konto
    if anvandarnamn:
        with get_db() as conn:
            u = conn.execute(
                "SELECT * FROM anvandare WHERE anvandarnamn=? AND aktiv=1",
                (anvandarnamn,)).fetchone()
        if u and u['losenord_hash'] == hash_pw(pw):
            session.permanent = True
            session['loggedin']     = True
            session['user_id']      = u['id']
            session['anvandarnamn'] = u['anvandarnamn']
            session['namn']         = u['namn']
            session['roll']         = u['roll']
            session['beredare']     = u['beredare']
            session['admin']        = (u['roll'] == 'admin')
            try:
                session['far_artiklar'] = bool(u['far_hantera_artiklar'])
            except (KeyError, IndexError):
                session['far_artiklar'] = False
            return jsonify({'ok': True, 'namn': u['namn'], 'roll': u['roll'],
                            'beredare': u['beredare'], 'admin': u['roll'] == 'admin'})
        return fel('Fel användarnamn eller lösenord.', 401)

    # Bakåtkompatibilitet: delat app-lösenord (om inget användarnamn angivits)
    if pw == _app_losenord():
        session.permanent = True
        session['loggedin'] = True
        return jsonify({'ok': True})
    return fel('Fel lösenord.', 401)


@app.post('/api/auth/logout')
def auth_logout():
    session.clear()
    return jsonify({'ok': True})


@app.get('/api/admin/check')
def admin_check():
    if session.get('admin'):
        return jsonify({'inloggad': True})
    return fel('Inte inloggad.', 401)


# ============================================================
# INSTALLNINGAR (offentlig läsning, admin skrivning)
# ============================================================

@app.get('/api/installningar')
def hamta_installningar_pub():
    with get_db() as conn:
        rader = conn.execute("SELECT nyckel,varde FROM installningar").fetchall()
    result = {r['nyckel']: r['varde'] for r in rader}
    result.pop('admin_losenord', None)
    return jsonify({'installningar': result})


@app.put('/api/installningar')
@admin_required
def spara_installningar():
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        for nyckel, varde in d.items():
            if nyckel == 'admin_losenord':
                continue
            conn.execute(
                "INSERT INTO installningar (nyckel,varde) VALUES (?,?) "
                "ON CONFLICT(nyckel) DO UPDATE SET varde=excluded.varde",
                (nyckel, str(varde)))
        conn.commit()
    return jsonify({'meddelande': 'Inställningar sparade.'})


@app.put('/api/admin/losenord')
@admin_required
def byt_losenord():
    d = request.get_json(silent=True) or {}
    pw = (d.get('losenord') or '').strip()
    if not pw:
        return fel('Lösenord får inte vara tomt.')
    with get_db() as conn:
        conn.execute(
            "INSERT INTO installningar (nyckel,varde) VALUES ('admin_losenord',?) "
            "ON CONFLICT(nyckel) DO UPDATE SET varde=excluded.varde",
            (hash_pw(pw),))
        conn.commit()
    return jsonify({'meddelande': 'Lösenord bytt.'})


# ============================================================
# PROJEKT
# ============================================================

@app.get('/api/projekt')
def lista_projekt():
    status   = request.args.get('status')
    beredare = request.args.get('beredare')
    omrade   = request.args.get('omrade', '').strip()
    sok      = request.args.get('sok', '').strip()
    sql = """
        SELECT p.*, pfd.fas_startdatum,
            COALESCE(ck.klar, 0) AS checklista_klar
        FROM projekt p
        LEFT JOIN (
            SELECT projekt_id, MAX(startdatum) AS fas_startdatum
            FROM projekt_fas_datum WHERE slutdatum IS NULL
            GROUP BY projekt_id
        ) pfd ON pfd.projekt_id = p.id
        LEFT JOIN (
            SELECT projekt_id, CAST(SUM(utford) AS INTEGER) AS klar
            FROM projekt_checklistor
            GROUP BY projekt_id
        ) ck ON ck.projekt_id = p.id
        WHERE 1=1
    """
    params = []
    if status:   sql += " AND p.status=?";   params.append(status)
    if beredare: sql += " AND p.beredare=?"; params.append(beredare)
    if omrade:   sql += " AND p.omrade=?";   params.append(omrade)
    if sok:
        sql += " AND (p.projektnummer LIKE ? OR p.projektnamn LIKE ? OR p.beredare LIKE ?)"
        params += [f'%{sok}%'] * 3
    sql += " ORDER BY p.skapad DESC"
    with get_db() as conn:
        return jsonify({'projekt': rows_to_list(conn.execute(sql, params).fetchall())})


@app.get('/api/projekt/statistik')
def projekt_statistik():
    with get_db() as conn:
        c = lambda w='': conn.execute(f"SELECT COUNT(*) FROM projekt {w}").fetchone()[0]
        return jsonify({
            'totalt':   c(),
            'pagaende': c("WHERE status='Pågående'"),
            'planerat': c("WHERE status='Planerat'"),
            'klart':    c("WHERE status='Klart'"),
        })


@app.get('/api/projekt/fas-statistik')
def fas_statistik():
    FASER = ['Beredning', 'Projektledning', 'Utförda']
    with get_db() as conn:
        result = {}
        for fas in FASER:
            result[fas] = conn.execute(
                "SELECT COUNT(*) FROM projekt WHERE fas=?", (fas,)
            ).fetchone()[0]
        result['ingen_fas'] = conn.execute(
            "SELECT COUNT(*) FROM projekt WHERE fas IS NULL"
        ).fetchone()[0]
        result['totalt'] = conn.execute("SELECT COUNT(*) FROM projekt").fetchone()[0]
    return jsonify({'fas_statistik': result})


@app.get('/api/projekt/nasta-nummer')
def nasta_nummer():
    with get_db() as conn:
        return jsonify({'projektnummer': nasta_projektnummer(conn)})


@app.get('/api/projekt/<int:pid>')
def hamta_projekt(pid):
    with get_db() as conn:
        rad = conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone()
    if not rad:
        return fel('Projektet hittades inte.', 404)
    return jsonify({'projekt': row_to_dict(rad)})


GILTIGA_FASER = ('Beredning', 'Projektledning', 'Utförda')


@app.post('/api/projekt')
def skapa_projekt():
    d = request.get_json(silent=True) or {}
    namn     = (d.get('projektnamn') or '').strip()
    beredare = (d.get('beredare') or '').strip()
    if not namn:     return fel('Projektnamn är obligatoriskt.')
    if not beredare: return fel('Beredare är obligatoriskt.')
    fas = (d.get('fas') or '').strip() or None
    if fas and fas not in GILTIGA_FASER:
        return fel(f'Ogiltig fas.')
    tidpunkt = nu()
    idag = tidpunkt[:10]
    with get_db() as conn:
        pnr = d.get('projektnummer') or nasta_projektnummer(conn)
        try:
            cur = conn.execute(
                "INSERT INTO projekt "
                "(projektnummer,projektnamn,beredare,status,startdatum,anteckningar,"
                "kund,anslutningspunkt,fas,"
                "ib_nummer,kategori,tilldelat_till,omrade,"
                "inkommande_bestallningar,bekraftade_bestallningar,"
                "beredning_start,beredning_slut,lat,lng,"
                "skapad,uppdaterad)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pnr, namn, beredare, d.get('status', 'Planerat'),
                 d.get('startdatum') or None,
                 (d.get('anteckningar') or '').strip() or None,
                 (d.get('kund') or '').strip() or None,
                 (d.get('anslutningspunkt') or '').strip() or None,
                 fas,
                 (d.get('ib_nummer') or '').strip() or None,
                 (d.get('kategori') or '').strip() or None,
                 (d.get('tilldelat_till') or '').strip() or None,
                 (d.get('omrade') or '').strip() or None,
                 (d.get('inkommande_bestallningar') or '').strip() or None,
                 (d.get('bekraftade_bestallningar') or '').strip() or None,
                 d.get('beredning_start') or None,
                 d.get('beredning_slut') or None,
                 _num(d.get('lat')), _num(d.get('lng')),
                 tidpunkt, tidpunkt))
            pid = cur.lastrowid
            if fas:
                conn.execute(
                    "INSERT INTO projekt_fas_datum (projekt_id,fas,startdatum,skapad) VALUES (?,?,?,?)",
                    (pid, fas, idag, tidpunkt))
                conn.execute(
                    "INSERT INTO projekt_aktiviteter (projekt_id,tidpunkt,typ,beskrivning) VALUES (?,?,?,?)",
                    (pid, tidpunkt, 'fas-byte', f'Projekt skapat i fas: {fas}'))
            conn.commit()
            return jsonify({'projekt': row_to_dict(conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone())}), 201
        except Exception as e:
            return fel(f'Projektnummer {pnr} finns redan.') if 'UNIQUE' in str(e) else fel(str(e))


@app.put('/api/projekt/<int:pid>')
def uppdatera_projekt(pid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone()
        if not bef: return fel('Projektet hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        namn = (d.get('projektnamn') or bef['projektnamn']).strip()
        if not namn: return fel('Projektnamn får inte vara tomt.')
        status = d.get('status', bef['status'])
        if status not in ('Planerat', 'Pågående', 'Klart'): return fel('Ogiltigt statusvärde.')
        tidpunkt = nu()
        conn.execute(
            "UPDATE projekt SET projektnamn=?,beredare=?,status=?,startdatum=?,anteckningar=?,"
            "kund=?,anslutningspunkt=?,"
            "ib_nummer=?,kategori=?,tilldelat_till=?,omrade=?,"
            "inkommande_bestallningar=?,bekraftade_bestallningar=?,"
            "beredning_start=?,beredning_slut=?,lat=?,lng=?,"
            "uppdaterad=? WHERE id=?",
            (namn, d.get('beredare', bef['beredare']), status,
             d.get('startdatum', bef['startdatum']) or None,
             d.get('anteckningar', bef['anteckningar']),
             (d.get('kund', bef['kund']) or '').strip() or None,
             (d.get('anslutningspunkt', bef['anslutningspunkt']) or '').strip() or None,
             (d.get('ib_nummer', bef['ib_nummer']) or '').strip() or None,
             (d.get('kategori', bef['kategori']) or '').strip() or None,
             (d.get('tilldelat_till', bef['tilldelat_till']) or '').strip() or None,
             (d.get('omrade', bef['omrade']) or '').strip() or None,
             (d.get('inkommande_bestallningar', bef['inkommande_bestallningar']) or '').strip() or None,
             (d.get('bekraftade_bestallningar', bef['bekraftade_bestallningar']) or '').strip() or None,
             d.get('beredning_start', bef['beredning_start']) or None,
             d.get('beredning_slut', bef['beredning_slut']) or None,
             _num(d.get('lat', bef['lat'])), _num(d.get('lng', bef['lng'])),
             tidpunkt, pid))
        conn.commit()
        return jsonify({'projekt': row_to_dict(conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone())})


@app.delete('/api/projekt/<int:pid>')
def ta_bort_projekt(pid):
    with get_db() as conn:
        rad = conn.execute("SELECT projektnummer FROM projekt WHERE id=?", (pid,)).fetchone()
        if not rad: return fel('Projektet hittades inte.', 404)
        conn.execute("DELETE FROM konstruktioner WHERE projekt_id=?", (pid,))
        conn.execute("DELETE FROM projekt WHERE id=?", (pid,))
        conn.commit()
    return jsonify({'meddelande': f'Projekt {rad["projektnummer"]} borttaget.'})


# ============================================================
# PROJEKT – CHECKLISTA
# ============================================================

@app.get('/api/projekt/checklistor')
def alla_checklistor():
    """Returnerar alla checklistepunkter för alla projekt som {pid: {done:[...], ej_rel:[...]}}."""
    with get_db() as conn:
        rader = conn.execute(
            "SELECT projekt_id, item_nr, utford, ej_relevant FROM projekt_checklistor"
        ).fetchall()
    result = {}
    for r in rader:
        pid = r['projekt_id']
        if pid not in result:
            result[pid] = {'done': [], 'ej_rel': []}
        if r['utford']:
            result[pid]['done'].append(r['item_nr'])
        if r['ej_relevant']:
            result[pid]['ej_rel'].append(r['item_nr'])
    return jsonify({'checklistor': result})


@app.get('/api/projekt/<int:pid>/checklista')
def hamta_checklista(pid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        rader = rows_to_list(conn.execute(
            "SELECT item_nr, utford, ej_relevant FROM projekt_checklistor WHERE projekt_id=? ORDER BY item_nr",
            (pid,)
        ).fetchall())
    return jsonify({'checklista': rader})


@app.put('/api/projekt/<int:pid>/checklista/<int:item_nr>')
def uppdatera_checklistepunkt(pid, item_nr):
    if item_nr < 0 or item_nr > 99:
        return fel('Ogiltigt item_nr.')
    d = request.get_json(silent=True) or {}
    utford = 1 if d.get('utford') else 0
    ej_relevant = 1 if d.get('ej_relevant') else 0
    if utford and ej_relevant:
        ej_relevant = 0
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        conn.execute(
            "INSERT INTO projekt_checklistor (projekt_id, item_nr, utford, ej_relevant) VALUES (?,?,?,?) "
            "ON CONFLICT(projekt_id, item_nr) DO UPDATE SET utford=excluded.utford, ej_relevant=excluded.ej_relevant",
            (pid, item_nr, utford, ej_relevant)
        )
        conn.commit()
    return jsonify({'item_nr': item_nr, 'utford': utford, 'ej_relevant': ej_relevant})


# ============================================================
# PROJEKT – BUDGET
# ============================================================

BUDGET_TYPER = ('Timmar', 'Material', 'UE', 'Avgifter', 'Resor')


@app.get('/api/projekt/<int:pid>/budget')
def hamta_budget(pid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        budget    = rows_to_list(conn.execute(
            "SELECT * FROM projekt_budget WHERE projekt_id=? ORDER BY skapad",
            (pid,)).fetchall())
        kostnader = rows_to_list(conn.execute(
            "SELECT * FROM projekt_kostnad WHERE projekt_id=? ORDER BY datum DESC, skapad DESC",
            (pid,)).fetchall())
        intakter  = rows_to_list(conn.execute(
            "SELECT * FROM projekt_intakt WHERE projekt_id=? ORDER BY datum DESC, skapad DESC",
            (pid,)).fetchall())

    total_budget  = sum(b['budgeterat_belopp'] for b in budget)
    total_kostnad = sum(k['belopp'] for k in kostnader)
    total_intakt  = sum(i['belopp'] for i in intakter)
    aterstar      = total_budget - total_kostnad
    forbrukat_pct = round(100 * total_kostnad / total_budget) if total_budget else 0
    resultat      = total_intakt - total_kostnad

    per_typ = {t: {'budget': 0.0, 'kostnad': 0.0} for t in BUDGET_TYPER}
    for b in budget:
        t = b['budget_typ']
        if t in per_typ:
            per_typ[t]['budget'] += b['budgeterat_belopp']
    for k in kostnader:
        t = k['budget_typ']
        if t in per_typ:
            per_typ[t]['kostnad'] += k['belopp']

    return jsonify({
        'budget':    budget,
        'kostnader': kostnader,
        'intakter':  intakter,
        'summering': {
            'total_budget':      total_budget,
            'total_kostnad':     total_kostnad,
            'total_intakt':      total_intakt,
            'återstår':          aterstar,
            'resultat':          resultat,
            'förbrukat_procent': forbrukat_pct,
            'per_typ':           per_typ,
        },
    })


@app.post('/api/projekt/<int:pid>/budget')
def skapa_budgetpost(pid):
    d = request.get_json(silent=True) or {}
    typ = (d.get('budget_typ') or '').strip()
    if typ not in BUDGET_TYPER:
        return fel(f'Ogiltig budget_typ. Välj: {", ".join(BUDGET_TYPER)}')
    try:
        belopp = float(d.get('budgeterat_belopp', 0))
    except (TypeError, ValueError):
        return fel('budgeterat_belopp måste vara ett tal.')
    tidpunkt = nu()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        cur = conn.execute(
            "INSERT INTO projekt_budget (projekt_id, budget_typ, beskrivning, budgeterat_belopp, skapad)"
            " VALUES (?,?,?,?,?)",
            (pid, typ, (d.get('beskrivning') or '').strip() or None, belopp, tidpunkt))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_budget WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'budget': rad}), 201


@app.put('/api/projekt/<int:pid>/budget/<int:bid>')
def uppdatera_budgetpost(pid, bid):
    with get_db() as conn:
        bef = conn.execute(
            "SELECT * FROM projekt_budget WHERE id=? AND projekt_id=?", (bid, pid)).fetchone()
        if not bef: return fel('Budgetposten hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        typ = (d.get('budget_typ') or bef['budget_typ']).strip()
        if typ not in BUDGET_TYPER:
            return fel('Ogiltig budget_typ.')
        try:
            belopp = float(d.get('budgeterat_belopp', bef['budgeterat_belopp']))
        except (TypeError, ValueError):
            return fel('budgeterat_belopp måste vara ett tal.')
        conn.execute(
            "UPDATE projekt_budget SET budget_typ=?, beskrivning=?, budgeterat_belopp=? WHERE id=?",
            (typ, (d.get('beskrivning', bef['beskrivning']) or '').strip() or None, belopp, bid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_budget WHERE id=?", (bid,)).fetchone())
    return jsonify({'budget': rad})


@app.delete('/api/projekt/<int:pid>/budget/<int:bid>')
def ta_bort_budgetpost(pid, bid):
    with get_db() as conn:
        rad = conn.execute(
            "SELECT id FROM projekt_budget WHERE id=? AND projekt_id=?", (bid, pid)).fetchone()
        if not rad: return fel('Budgetposten hittades inte.', 404)
        conn.execute("DELETE FROM projekt_budget WHERE id=?", (bid,))
        conn.commit()
    return jsonify({'meddelande': 'Budgetpost borttagen.'})


@app.post('/api/projekt/<int:pid>/kostnad')
def skapa_kostnad(pid):
    d = request.get_json(silent=True) or {}
    typ = (d.get('budget_typ') or '').strip()
    if typ not in BUDGET_TYPER:
        return fel(f'Ogiltig budget_typ. Välj: {", ".join(BUDGET_TYPER)}')
    try:
        belopp = float(d.get('belopp', 0))
    except (TypeError, ValueError):
        return fel('belopp måste vara ett tal.')
    tidpunkt = nu()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        cur = conn.execute(
            "INSERT INTO projekt_kostnad "
            "(projekt_id, budget_typ, beskrivning, leverantor, belopp, datum, faktura_nr, skapad)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (pid, typ,
             (d.get('beskrivning') or '').strip() or None,
             (d.get('leverantor') or '').strip() or None,
             belopp,
             d.get('datum') or None,
             (d.get('faktura_nr') or '').strip() or None,
             tidpunkt))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_kostnad WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'kostnad': rad}), 201


@app.put('/api/projekt/<int:pid>/kostnad/<int:kid>')
def uppdatera_kostnad(pid, kid):
    with get_db() as conn:
        bef = conn.execute(
            "SELECT * FROM projekt_kostnad WHERE id=? AND projekt_id=?", (kid, pid)).fetchone()
        if not bef: return fel('Kostnaden hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        typ = (d.get('budget_typ') or bef['budget_typ']).strip()
        if typ not in BUDGET_TYPER:
            return fel('Ogiltig budget_typ.')
        try:
            belopp = float(d.get('belopp', bef['belopp']))
        except (TypeError, ValueError):
            return fel('belopp måste vara ett tal.')
        conn.execute(
            "UPDATE projekt_kostnad SET budget_typ=?, beskrivning=?, leverantor=?,"
            " belopp=?, datum=?, faktura_nr=? WHERE id=?",
            (typ,
             (d.get('beskrivning', bef['beskrivning']) or '').strip() or None,
             (d.get('leverantor', bef['leverantor']) or '').strip() or None,
             belopp,
             d.get('datum', bef['datum']) or None,
             (d.get('faktura_nr', bef['faktura_nr']) or '').strip() or None,
             kid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_kostnad WHERE id=?", (kid,)).fetchone())
    return jsonify({'kostnad': rad})


@app.delete('/api/projekt/<int:pid>/kostnad/<int:kid>')
def ta_bort_kostnad(pid, kid):
    with get_db() as conn:
        rad = conn.execute(
            "SELECT id FROM projekt_kostnad WHERE id=? AND projekt_id=?", (kid, pid)).fetchone()
        if not rad: return fel('Kostnaden hittades inte.', 404)
        conn.execute("DELETE FROM projekt_kostnad WHERE id=?", (kid,))
        conn.commit()
    return jsonify({'meddelande': 'Kostnad borttagen.'})


@app.post('/api/projekt/<int:pid>/intakt')
def skapa_intakt(pid):
    d = request.get_json(silent=True) or {}
    try:
        belopp = float(d.get('belopp', 0))
    except (TypeError, ValueError):
        return fel('belopp måste vara ett tal.')
    tidpunkt = nu()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        cur = conn.execute(
            "INSERT INTO projekt_intakt "
            "(projekt_id, beskrivning, belopp, datum, faktura_nr, skapad)"
            " VALUES (?,?,?,?,?,?)",
            (pid,
             (d.get('beskrivning') or '').strip() or None,
             belopp,
             d.get('datum') or None,
             (d.get('faktura_nr') or '').strip() or None,
             tidpunkt))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_intakt WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'intakt': rad}), 201


@app.put('/api/projekt/<int:pid>/intakt/<int:iid>')
def uppdatera_intakt(pid, iid):
    with get_db() as conn:
        bef = conn.execute(
            "SELECT * FROM projekt_intakt WHERE id=? AND projekt_id=?", (iid, pid)).fetchone()
        if not bef: return fel('Intäkten hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        try:
            belopp = float(d.get('belopp', bef['belopp']))
        except (TypeError, ValueError):
            return fel('belopp måste vara ett tal.')
        conn.execute(
            "UPDATE projekt_intakt SET beskrivning=?, belopp=?, datum=?, faktura_nr=? WHERE id=?",
            ((d.get('beskrivning', bef['beskrivning']) or '').strip() or None,
             belopp,
             d.get('datum', bef['datum']) or None,
             (d.get('faktura_nr', bef['faktura_nr']) or '').strip() or None,
             iid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM projekt_intakt WHERE id=?", (iid,)).fetchone())
    return jsonify({'intakt': rad})


@app.delete('/api/projekt/<int:pid>/intakt/<int:iid>')
def ta_bort_intakt(pid, iid):
    with get_db() as conn:
        rad = conn.execute(
            "SELECT id FROM projekt_intakt WHERE id=? AND projekt_id=?", (iid, pid)).fetchone()
        if not rad: return fel('Intäkten hittades inte.', 404)
        conn.execute("DELETE FROM projekt_intakt WHERE id=?", (iid,))
        conn.commit()
    return jsonify({'meddelande': 'Intäkt borttagen.'})


# ============================================================
# PROJEKT – FAS
# ============================================================

@app.get('/api/projekt/<int:pid>/fas')
def hamta_fas(pid):
    with get_db() as conn:
        proj = conn.execute("SELECT fas FROM projekt WHERE id=?", (pid,)).fetchone()
        if not proj: return fel('Projektet hittades inte.', 404)
        historik = rows_to_list(conn.execute(
            "SELECT * FROM projekt_fas_datum WHERE projekt_id=? ORDER BY startdatum",
            (pid,)
        ).fetchall())
    return jsonify({'fas': proj['fas'], 'historik': historik})


@app.post('/api/projekt/<int:pid>/fas')
def uppdatera_fas(pid):
    d = request.get_json(silent=True) or {}
    ny_fas = (d.get('fas') or '').strip()
    if ny_fas not in GILTIGA_FASER:
        return fel(f'Ogiltig fas. Välj: {", ".join(GILTIGA_FASER)}')
    tidpunkt = nu()
    idag = tidpunkt[:10]
    with get_db() as conn:
        proj = conn.execute("SELECT fas FROM projekt WHERE id=?", (pid,)).fetchone()
        if not proj: return fel('Projektet hittades inte.', 404)
        gammal_fas = proj['fas']
        if gammal_fas == ny_fas:
            return jsonify({'fas': ny_fas, 'meddelande': 'Ingen förändring.'})
        conn.execute(
            "UPDATE projekt_fas_datum SET slutdatum=? WHERE projekt_id=? AND slutdatum IS NULL",
            (idag, pid))
        conn.execute(
            "INSERT INTO projekt_fas_datum (projekt_id,fas,startdatum,skapad) VALUES (?,?,?,?)",
            (pid, ny_fas, idag, tidpunkt))
        conn.execute(
            "UPDATE projekt SET fas=?,uppdaterad=? WHERE id=?",
            (ny_fas, tidpunkt, pid))
        conn.execute(
            "INSERT INTO projekt_aktiviteter (projekt_id,tidpunkt,typ,beskrivning) VALUES (?,?,?,?)",
            (pid, tidpunkt, 'fas-byte', f'Fas: {gammal_fas or "–"} → {ny_fas}'))
        conn.commit()
    return jsonify({'fas': ny_fas, 'meddelande': f'Fas uppdaterad till {ny_fas}.'})


# ============================================================
# PROJEKT – TILLSTÅND
# ============================================================

@app.get('/api/projekt/<int:pid>/tillstand')
def lista_tillstand(pid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        t = rows_to_list(conn.execute(
            "SELECT * FROM projekt_tillstand WHERE projekt_id=? ORDER BY skapad",
            (pid,)
        ).fetchall())
    return jsonify({'tillstand': t})


@app.post('/api/projekt/<int:pid>/tillstand')
def skapa_tillstand(pid):
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn: return fel('Namn är obligatoriskt.')
    status = d.get('status', 'Inväntas')
    if status not in ('Inväntas', 'Mottaget', 'Ej krävs'):
        return fel('Ogiltigt status.')
    tidpunkt = nu()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        cur = conn.execute(
            "INSERT INTO projekt_tillstand "
            "(projekt_id,namn,status,datum,anteckning,skapad,uppdaterad) VALUES (?,?,?,?,?,?,?)",
            (pid, namn, status, d.get('datum') or None,
             (d.get('anteckning') or '').strip() or None, tidpunkt, tidpunkt))
        conn.commit()
        t = row_to_dict(conn.execute(
            "SELECT * FROM projekt_tillstand WHERE id=?", (cur.lastrowid,)
        ).fetchone())
    return jsonify({'tillstand': t}), 201


@app.put('/api/projekt/<int:pid>/tillstand/<int:tid>')
def uppdatera_tillstand(pid, tid):
    with get_db() as conn:
        bef = conn.execute(
            "SELECT * FROM projekt_tillstand WHERE id=? AND projekt_id=?", (tid, pid)
        ).fetchone()
        if not bef: return fel('Tillståndet hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        status = d.get('status', bef['status'])
        if status not in ('Inväntas', 'Mottaget', 'Ej krävs'):
            return fel('Ogiltigt status.')
        conn.execute(
            "UPDATE projekt_tillstand SET namn=?,status=?,datum=?,anteckning=?,uppdaterad=? WHERE id=?",
            ((d.get('namn') or bef['namn']).strip(), status,
             d.get('datum', bef['datum']) or None,
             d.get('anteckning', bef['anteckning']),
             nu(), tid))
        conn.commit()
        t = row_to_dict(conn.execute(
            "SELECT * FROM projekt_tillstand WHERE id=?", (tid,)
        ).fetchone())
    return jsonify({'tillstand': t})


@app.delete('/api/projekt/<int:pid>/tillstand/<int:tid>')
def ta_bort_tillstand(pid, tid):
    with get_db() as conn:
        rad = conn.execute(
            "SELECT id FROM projekt_tillstand WHERE id=? AND projekt_id=?", (tid, pid)
        ).fetchone()
        if not rad: return fel('Tillståndet hittades inte.', 404)
        conn.execute("DELETE FROM projekt_tillstand WHERE id=?", (tid,))
        conn.commit()
    return jsonify({'meddelande': 'Tillstånd borttaget.'})


# ============================================================
# PROJEKT – AKTIVITETSLOGG
# ============================================================

@app.get('/api/projekt/<int:pid>/aktiviteter')
def lista_aktiviteter(pid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        a = rows_to_list(conn.execute(
            "SELECT * FROM projekt_aktiviteter WHERE projekt_id=? ORDER BY tidpunkt DESC LIMIT 100",
            (pid,)
        ).fetchall())
    return jsonify({'aktiviteter': a})


@app.post('/api/projekt/<int:pid>/aktiviteter')
def skapa_aktivitet(pid):
    d = request.get_json(silent=True) or {}
    beskrivning = (d.get('beskrivning') or '').strip()
    if not beskrivning: return fel('Beskrivning är obligatorisk.')
    tidpunkt = nu()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        cur = conn.execute(
            "INSERT INTO projekt_aktiviteter (projekt_id,tidpunkt,typ,beskrivning) VALUES (?,?,?,?)",
            (pid, tidpunkt, d.get('typ', 'anteckning'), beskrivning))
        conn.commit()
        a = row_to_dict(conn.execute(
            "SELECT * FROM projekt_aktiviteter WHERE id=?", (cur.lastrowid,)
        ).fetchone())
    return jsonify({'aktivitet': a}), 201


# ============================================================
# BEREDARE
# ============================================================

@app.get('/api/beredare')
def lista_beredare():
    with get_db() as conn:
        return jsonify({'beredare': rows_to_list(
            conn.execute("SELECT * FROM beredare WHERE aktiv=1 ORDER BY namn").fetchall())})


# ============================================================
# KATEGORIER & LEVERANTÖRER
# ============================================================

@app.get('/api/kategorier')
def lista_kategorier():
    with get_db() as conn:
        return jsonify({'kategorier': rows_to_list(
            conn.execute("SELECT * FROM kategorier ORDER BY sortering").fetchall())})


@app.get('/api/leverantorer')
def lista_leverantorer():
    with get_db() as conn:
        return jsonify({'leverantorer': rows_to_list(
            conn.execute("SELECT * FROM leverantorer WHERE aktiv=1 ORDER BY namn").fetchall())})


# ============================================================
# ARTIKLAR
# ============================================================

@app.get('/api/artiklar')
def lista_artiklar():
    kat_id     = request.args.get('kategori_id')
    kat_namn   = request.args.get('kategori', '').strip()
    lev_id     = request.args.get('leverantor_id')
    sok        = request.args.get('sok', '').strip()
    visa_alla  = request.args.get('filter', '').lower() == 'alla'

    sql = """
        SELECT a.id, a.artikelnamn, a.enhet, a.sortering, a.aktiv,
               COALESCE(a.moduler, 0) AS moduler,
               k.id AS kategori_id, k.namn AS kategori_namn
        FROM artiklar a
        JOIN kategorier k ON k.id = a.kategori_id
        WHERE 1=1
    """
    params = []
    if not visa_alla:
        sql += " AND a.aktiv = 1"
    if kat_id:
        sql += " AND a.kategori_id=?"; params.append(int(kat_id))
    if kat_namn:
        sql += " AND k.namn=?"; params.append(kat_namn)
    if sok:
        sql += " AND a.artikelnamn LIKE ?"; params.append(f'%{sok}%')
    sql += " ORDER BY k.sortering, a.sortering, a.artikelnamn"

    with get_db() as conn:
        artiklar = rows_to_list(conn.execute(sql, params).fetchall())
        for art in artiklar:
            priser = conn.execute("""
                SELECT al.leverantor_id, l.namn AS leverantor_namn, al.artikelnummer, al.a_pris
                FROM artikel_leverantor al
                JOIN leverantorer l ON l.id=al.leverantor_id
                WHERE al.artikel_id=? ORDER BY al.a_pris
            """, (art['id'],)).fetchall()
            art['priser'] = rows_to_list(priser)
            if priser:
                billigast = dict(priser[0])
                art['leverantor_id']   = billigast['leverantor_id']
                art['leverantor_namn'] = billigast['leverantor_namn']
                art['artikelnummer']   = billigast['artikelnummer']
                art['a_pris']          = billigast['a_pris']
            else:
                art['leverantor_id'] = art['leverantor_namn'] = art['artikelnummer'] = art['a_pris'] = None

        if lev_id:
            lev_id_int = int(lev_id)
            artiklar = [a for a in artiklar
                        if any(p['leverantor_id'] == lev_id_int for p in a.get('priser', []))]

    return jsonify({'artiklar': artiklar})


@app.get('/api/artiklar/<int:aid>')
def hamta_artikel(aid):
    with get_db() as conn:
        art = conn.execute("""
            SELECT a.*, k.namn AS kategori_namn FROM artiklar a
            JOIN kategorier k ON k.id=a.kategori_id WHERE a.id=?
        """, (aid,)).fetchone()
        if not art: return fel('Artikeln hittades inte.', 404)
        d = row_to_dict(art)
        priser = rows_to_list(conn.execute("""
            SELECT al.*, l.namn AS leverantor_namn FROM artikel_leverantor al
            JOIN leverantorer l ON l.id=al.leverantor_id WHERE al.artikel_id=?
            ORDER BY al.a_pris
        """, (aid,)).fetchall())
        d['priser'] = priser
        if priser:
            billigast = priser[0]
            d['leverantor_id']   = billigast['leverantor_id']
            d['leverantor_namn'] = billigast['leverantor_namn']
            d['artikelnummer']   = billigast['artikelnummer']
            d['a_pris']          = billigast['a_pris']
        else:
            d['leverantor_id'] = d['leverantor_namn'] = d['artikelnummer'] = d['a_pris'] = None
    return jsonify({'artikel': d})


# ============================================================
# MALLAR
# ============================================================

@app.get('/api/mallar')
def lista_mallar():
    with get_db() as conn:
        return jsonify({'mallar': rows_to_list(
            conn.execute("SELECT * FROM mallar WHERE aktiv=1 ORDER BY sortering").fetchall())})


@app.get('/api/mallar/<int:mid>')
def hamta_mall(mid):
    with get_db() as conn:
        mall = conn.execute("SELECT * FROM mallar WHERE id=?", (mid,)).fetchone()
        if not mall: return fel('Mallen hittades inte.', 404)
        d = row_to_dict(mall)
        d['inputfalt'] = rows_to_list(conn.execute(
            "SELECT * FROM mall_inputfalt WHERE mall_id=? ORDER BY sortering", (mid,)).fetchall())
    return jsonify({'mall': d})


# ============================================================
# BYGGPROTOKOLL
# ============================================================

@app.get('/api/byggprotokoll')
def lista_protokoll():
    pid = request.args.get('projekt_id')
    with get_db() as conn:
        if pid:
            rader = conn.execute(
                "SELECT * FROM byggprotokoll WHERE projekt_id=? ORDER BY skapad DESC", (int(pid),)
            ).fetchall()
        else:
            rader = conn.execute("SELECT * FROM byggprotokoll ORDER BY skapad DESC").fetchall()
    return jsonify({'byggprotokoll': rows_to_list(rader)})


@app.post('/api/byggprotokoll/berakna')
def berakna_forhandsgranskning():
    d = request.get_json(silent=True) or {}
    mall_id   = d.get('mall_id')
    inputdata = d.get('inputdata', {})
    if not mall_id: return fel('mall_id saknas.')
    with get_db() as conn:
        rader = berakna(mall_id, inputdata, conn)
    return jsonify({'rader': [r for r in rader if r]})


@app.post('/api/byggprotokoll')
def skapa_protokoll():
    d = request.get_json(silent=True) or {}
    projekt_id = d.get('projekt_id')
    mall_id    = d.get('mall_id')
    inputdata  = d.get('inputdata', {})
    rader_in   = d.get('rader')

    if not projekt_id: return fel('projekt_id saknas.')
    if not mall_id:    return fel('mall_id saknas.')

    tidpunkt = nu()

    with get_db() as conn:
        mall = conn.execute("SELECT namn FROM mallar WHERE id=?", (mall_id,)).fetchone()
        if not mall: return fel('Mallen hittades inte.', 404)
        proj = conn.execute("SELECT id FROM projekt WHERE id=?", (projekt_id,)).fetchone()
        if not proj: return fel('Projektet hittades inte.', 404)

        if rader_in is None:
            rader_in = berakna(mall_id, inputdata, conn)

        cur = conn.execute(
            "INSERT INTO byggprotokoll (projekt_id,mall_id,mall_namn,inputdata,anteckningar,status,skapad,uppdaterad)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (projekt_id, mall_id, mall['namn'], json.dumps(inputdata, ensure_ascii=False),
             (d.get('anteckningar') or '').strip() or None, 'Utkast', tidpunkt, tidpunkt))
        protokoll_id = cur.lastrowid

        _spara_rader(conn, protokoll_id, rader_in)

        # Seed egenkontroll från mallens mall_egenkontroll
        egk_mall = conn.execute(
            "SELECT punkt, sortering FROM mall_egenkontroll WHERE mall_id=? ORDER BY sortering",
            (mall_id,)
        ).fetchall()
        for row in egk_mall:
            conn.execute(
                "INSERT INTO byggprotokoll_egenkontroll "
                "(protokoll_id, punkt, utford, ej_relevant, sortering) VALUES (?,?,0,0,?)",
                (protokoll_id, row['punkt'], row['sortering'])
            )

        conn.commit()

        return jsonify({'byggprotokoll': _hamta_protokoll_komplett(conn, protokoll_id)}), 201


@app.get('/api/byggprotokoll/<int:bpid>')
def hamta_protokoll(bpid):
    with get_db() as conn:
        bp = _hamta_protokoll_komplett(conn, bpid)
    if not bp: return fel('Protokollet hittades inte.', 404)
    return jsonify({'byggprotokoll': bp})


@app.put('/api/byggprotokoll/<int:bpid>')
def uppdatera_protokoll(bpid):
    with get_db() as conn:
        bef = conn.execute("SELECT id FROM byggprotokoll WHERE id=?", (bpid,)).fetchone()
        if not bef: return fel('Protokollet hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        rader_in  = d.get('rader')
        inputdata = d.get('inputdata')

        updates = ["uppdaterad=?"]
        params  = [nu()]
        if d.get('anteckningar') is not None:
            updates.append("anteckningar=?"); params.append(d['anteckningar'] or None)
        if d.get('status'):
            updates.append("status=?"); params.append(d['status'])
        if inputdata is not None:
            updates.append("inputdata=?"); params.append(json.dumps(inputdata, ensure_ascii=False))
        params.append(bpid)
        conn.execute(f"UPDATE byggprotokoll SET {','.join(updates)} WHERE id=?", params)

        if rader_in is not None:
            conn.execute("DELETE FROM byggprotokoll_rader WHERE protokoll_id=?", (bpid,))
            _spara_rader(conn, bpid, rader_in)

        egenkontroll_in = d.get('egenkontroll')
        if egenkontroll_in is not None:
            for item in egenkontroll_in:
                conn.execute(
                    "UPDATE byggprotokoll_egenkontroll SET utford=?, ej_relevant=? WHERE id=? AND protokoll_id=?",
                    (int(item.get('utford', 0)), int(item.get('ej_relevant', 0)),
                     item['id'], bpid)
                )

        conn.commit()
        return jsonify({'byggprotokoll': _hamta_protokoll_komplett(conn, bpid)})


@app.delete('/api/byggprotokoll/<int:bpid>')
def ta_bort_protokoll(bpid):
    with get_db() as conn:
        rad = conn.execute("SELECT id FROM byggprotokoll WHERE id=?", (bpid,)).fetchone()
        if not rad: return fel('Protokollet hittades inte.', 404)
        conn.execute("DELETE FROM byggprotokoll WHERE id=?", (bpid,))
        conn.commit()
    return jsonify({'meddelande': 'Protokoll borttaget.'})


def _spara_rader(conn, protokoll_id, rader):
    for i, r in enumerate(rader):
        if not r: continue
        conn.execute("""
            INSERT INTO byggprotokoll_rader
            (protokoll_id,artikel_id,artikelnamn,kategori,enhet,antal,
             leverantor_id,leverantor_namn,artikelnummer,a_pris,anteckning,manuell,sortering)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (protokoll_id, r.get('artikel_id'), r.get('artikelnamn', ''),
              r.get('kategori', ''), r.get('enhet', ''), float(r.get('antal', 0)),
              r.get('leverantor_id'), r.get('leverantor_namn'),
              r.get('artikelnummer'), r.get('a_pris'),
              r.get('anteckning', ''), int(r.get('manuell', 0)), i))


def _hamta_protokoll_komplett(conn, bpid):
    bp = conn.execute("SELECT * FROM byggprotokoll WHERE id=?", (bpid,)).fetchone()
    if not bp: return None
    d = row_to_dict(bp)
    d['rader'] = rows_to_list(conn.execute(
        "SELECT * FROM byggprotokoll_rader WHERE protokoll_id=? ORDER BY sortering", (bpid,)).fetchall())
    d['egenkontroll'] = rows_to_list(conn.execute(
        "SELECT * FROM byggprotokoll_egenkontroll WHERE protokoll_id=? ORDER BY sortering", (bpid,)).fetchall())
    try:
        d['inputdata'] = json.loads(d['inputdata'] or '{}')
    except Exception:
        d['inputdata'] = {}
    return d


# ============================================================
# PDF – Byggprotokoll
# ============================================================

@app.get('/api/byggprotokoll/<int:bpid>/pdf')
def byggprotokoll_pdf(bpid):
    from pdf_generator import skapa_byggprotokoll_pdf
    with get_db() as conn:
        bp = _hamta_protokoll_komplett(conn, bpid)
        if not bp: return fel('Protokollet hittades inte.', 404)
        projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (bp['projekt_id'],)).fetchone()
        inst = {r['nyckel']: r['varde'] for r in
                conn.execute("SELECT nyckel,varde FROM installningar").fetchall()}
    pdf = skapa_byggprotokoll_pdf(bp, row_to_dict(projekt), inst)
    pnr = projekt['projektnummer'] if projekt else str(bpid)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{pnr}_byggprotokoll_{bpid}.pdf"'})


# ============================================================
# PDF – Materiallista per projekt
# ============================================================

@app.get('/api/projekt/<int:pid>/materiallista/pdf')
def materiallista_pdf(pid):
    from pdf_generator import skapa_materiallista_pdf
    with get_db() as conn:
        projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone()
        if not projekt: return fel('Projektet hittades inte.', 404)
        inst = {r['nyckel']: r['varde'] for r in
                conn.execute("SELECT nyckel,varde FROM installningar").fetchall()}
        protokoll_ids = [r[0] for r in
                         conn.execute("SELECT id FROM byggprotokoll WHERE projekt_id=?", (pid,)).fetchall()]
        protokoll_lista = [_hamta_protokoll_komplett(conn, bpid) for bpid in protokoll_ids]
        # Berika rader med E-nummer från artikel_leverantor om artikelnummer saknas
        # Slår upp på artikelnamn (alltid satt) eftersom artikel_id kan vara NULL på äldre rader
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
    pdf = skapa_materiallista_pdf(row_to_dict(projekt), protokoll_lista, inst, enr_lookup)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition':
                             f'attachment; filename="{projekt["projektnummer"]}_materiallista.pdf"'})


@app.get('/api/projekt/<int:pid>/materiallista/excel')
def materiallista_excel(pid):
    from excel_generator import skapa_materiallista_excel
    with get_db() as conn:
        projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone()
        if not projekt: return fel('Projektet hittades inte.', 404)
        protokoll_ids = [r[0] for r in
                         conn.execute("SELECT id FROM byggprotokoll WHERE projekt_id=?", (pid,)).fetchall()]
        protokoll_lista = [_hamta_protokoll_komplett(conn, bpid) for bpid in protokoll_ids]
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
    xlsx = skapa_materiallista_excel(row_to_dict(projekt), protokoll_lista, enr_lookup)
    filnamn = f"{projekt['projektnummer']}_materiallista.xlsx"
    return Response(xlsx,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{filnamn}"'})


# ============================================================
# ADMIN – Artiklar CRUD
# ============================================================

@app.post('/api/admin/artiklar')
@artikel_required
def admin_skapa_artikel():
    d = request.get_json(silent=True) or {}
    namn   = (d.get('artikelnamn') or '').strip()
    enhet  = (d.get('enhet') or '').strip()
    kat_id = d.get('kategori_id')
    if not namn:   return fel('Artikelnamn är obligatoriskt.')
    if not enhet:  return fel('Enhet är obligatorisk.')
    if not kat_id: return fel('Kategori är obligatorisk.')
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO artiklar (artikelnamn,kategori_id,enhet,aktiv) VALUES (?,?,?,1)",
            (namn, int(kat_id), enhet))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM artiklar WHERE id=?", (cur.lastrowid,)).fetchone())), 201


@app.put('/api/admin/artiklar/<int:aid>')
@artikel_required
def admin_uppdatera_artikel(aid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM artiklar WHERE id=?", (aid,)).fetchone()
        if not bef: return fel('Artikeln hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        conn.execute(
            "UPDATE artiklar SET artikelnamn=?,kategori_id=?,enhet=?,beskrivning=?,aktiv=? WHERE id=?",
            ((d.get('artikelnamn') or bef['artikelnamn']).strip(),
             d.get('kategori_id', bef['kategori_id']),
             (d.get('enhet') or bef['enhet']).strip(),
             d.get('beskrivning', bef['beskrivning']),
             d.get('aktiv', bef['aktiv']), aid))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM artiklar WHERE id=?", (aid,)).fetchone()))


@app.delete('/api/admin/artiklar/<int:aid>')
@artikel_required
def admin_ta_bort_artikel(aid):
    with get_db() as conn:
        rad = conn.execute("SELECT artikelnamn FROM artiklar WHERE id=?", (aid,)).fetchone()
        if not rad:
            return fel('Artikeln hittades inte.', 404)
        try:
            conn.execute("DELETE FROM artiklar WHERE id=?", (aid,))
            conn.commit()
        except Exception as e:
            if 'FOREIGN KEY' in str(e):
                return fel('Artikeln kan inte tas bort – den används i ett eller flera byggprotokoll.', 400)
            return fel(str(e))
    return jsonify({'meddelande': 'Artikel borttagen.'})


# ============================================================
# ADMIN – Priser (artikel_leverantor)
# ============================================================

@app.get('/api/admin/artiklar/<int:aid>/priser')
@artikel_required
def admin_lista_priser(aid):
    with get_db() as conn:
        priser = rows_to_list(conn.execute("""
            SELECT al.id, al.leverantor_id, l.namn AS leverantor_namn,
                   al.artikelnummer, al.a_pris
            FROM artikel_leverantor al
            JOIN leverantorer l ON l.id=al.leverantor_id
            WHERE al.artikel_id=? ORDER BY al.a_pris
        """, (aid,)).fetchall())
    return jsonify({'priser': priser})


@app.post('/api/admin/artiklar/<int:aid>/priser')
@artikel_required
def admin_lagg_till_pris(aid):
    d = request.get_json(silent=True) or {}
    lev_id = d.get('leverantor_id')
    if not lev_id: return fel('leverantor_id saknas.')
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO artikel_leverantor (artikel_id,leverantor_id,artikelnummer,a_pris)
                VALUES (?,?,?,?)
                ON CONFLICT(artikel_id,leverantor_id)
                DO UPDATE SET artikelnummer=excluded.artikelnummer, a_pris=excluded.a_pris
            """, (aid, int(lev_id), d.get('artikelnummer'), d.get('a_pris')))
            conn.commit()
            pris = conn.execute("""
                SELECT al.id, al.leverantor_id, l.namn AS leverantor_namn,
                       al.artikelnummer, al.a_pris
                FROM artikel_leverantor al
                JOIN leverantorer l ON l.id=al.leverantor_id
                WHERE al.artikel_id=? AND al.leverantor_id=?
            """, (aid, int(lev_id))).fetchone()
            return jsonify({'pris': row_to_dict(pris)}), 201
        except Exception as e:
            return fel(str(e))


@app.delete('/api/admin/artiklar/<int:aid>/priser/<int:pris_id>')
@artikel_required
def admin_ta_bort_pris(aid, pris_id):
    with get_db() as conn:
        conn.execute("DELETE FROM artikel_leverantor WHERE id=? AND artikel_id=?", (pris_id, aid))
        conn.commit()
    return jsonify({'meddelande': 'Pris borttaget.'})


# ============================================================
# ADMIN – Kategorier
# ============================================================

@app.post('/api/admin/kategorier')
@admin_required
def admin_skapa_kategori():
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn: return fel('Namn är obligatoriskt.')
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO kategorier (namn,sortering) VALUES (?,?)",
                               (namn, d.get('sortering', 99)))
            conn.commit()
            return jsonify(row_to_dict(conn.execute("SELECT * FROM kategorier WHERE id=?", (cur.lastrowid,)).fetchone())), 201
        except Exception as e:
            return fel(f'Kategorin "{namn}" finns redan.') if 'UNIQUE' in str(e) else fel(str(e))


@app.put('/api/admin/kategorier/<int:kid>')
@admin_required
def admin_uppdatera_kategori(kid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM kategorier WHERE id=?", (kid,)).fetchone()
        if not bef: return fel('Kategorin hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        conn.execute("UPDATE kategorier SET namn=?,sortering=? WHERE id=?",
                     ((d.get('namn') or bef['namn']).strip(),
                      d.get('sortering', bef['sortering']), kid))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM kategorier WHERE id=?", (kid,)).fetchone()))


@app.delete('/api/admin/kategorier/<int:kid>')
@admin_required
def admin_ta_bort_kategori(kid):
    with get_db() as conn:
        try:
            conn.execute("DELETE FROM kategorier WHERE id=?", (kid,))
            conn.commit()
        except Exception as e:
            if 'FOREIGN KEY' in str(e):
                return fel('Kategorin kan inte tas bort – den har artiklar kopplade till sig.', 400)
            return fel(str(e))
    return jsonify({'meddelande': 'Kategori borttagen.'})


# ============================================================
# ADMIN – Leverantörer
# ============================================================

@app.post('/api/admin/leverantorer')
@admin_required
def admin_skapa_leverantor():
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn: return fel('Namn är obligatoriskt.')
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO leverantorer (namn) VALUES (?)", (namn,))
            conn.commit()
            return jsonify(row_to_dict(conn.execute("SELECT * FROM leverantorer WHERE id=?", (cur.lastrowid,)).fetchone())), 201
        except Exception as e:
            return fel(f'Leverantören "{namn}" finns redan.') if 'UNIQUE' in str(e) else fel(str(e))


@app.put('/api/admin/leverantorer/<int:lid>')
@admin_required
def admin_uppdatera_leverantor(lid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM leverantorer WHERE id=?", (lid,)).fetchone()
        if not bef: return fel('Leverantören hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        conn.execute("UPDATE leverantorer SET namn=?,aktiv=? WHERE id=?",
                     ((d.get('namn') or bef['namn']).strip(), d.get('aktiv', bef['aktiv']), lid))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM leverantorer WHERE id=?", (lid,)).fetchone()))


@app.delete('/api/admin/leverantorer/<int:lid>')
@admin_required
def admin_ta_bort_leverantor(lid):
    with get_db() as conn:
        try:
            conn.execute("DELETE FROM leverantorer WHERE id=?", (lid,))
            conn.commit()
        except Exception as e:
            if 'FOREIGN KEY' in str(e):
                return fel('Leverantören kan inte tas bort – den används i artiklar eller protokoll.', 400)
            return fel(str(e))
    return jsonify({'meddelande': 'Leverantör borttagen.'})


# ============================================================
# ADMIN – Beredare
# ============================================================

@app.post('/api/admin/beredare')
@admin_required
def admin_skapa_beredare():
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn: return fel('Namn är obligatoriskt.')
    with get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO beredare (namn) VALUES (?)", (namn,))
            conn.commit()
            return jsonify(row_to_dict(conn.execute("SELECT * FROM beredare WHERE id=?", (cur.lastrowid,)).fetchone())), 201
        except Exception as e:
            return fel(f'Beredaren "{namn}" finns redan.') if 'UNIQUE' in str(e) else fel(str(e))


@app.put('/api/admin/beredare/<int:bid>')
@admin_required
def admin_uppdatera_beredare(bid):
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM beredare WHERE id=?", (bid,)).fetchone()
        if not bef: return fel('Beredaren hittades inte.', 404)
        conn.execute("UPDATE beredare SET namn=?,aktiv=? WHERE id=?",
                     ((d.get('namn') or bef['namn']).strip(), d.get('aktiv', bef['aktiv']), bid))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM beredare WHERE id=?", (bid,)).fetchone()))


@app.delete('/api/admin/beredare/<int:bid>')
@admin_required
def admin_ta_bort_beredare(bid):
    with get_db() as conn:
        conn.execute("DELETE FROM beredare WHERE id=?", (bid,))
        conn.commit()
    return jsonify({'meddelande': 'Beredare borttagen.'})


# ============================================================
# ADMIN – Användare
# ============================================================

GILTIGA_ROLLER = ('admin', 'beredare', 'ue')


@app.get('/api/admin/anvandare')
@admin_required
def admin_lista_anvandare():
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT id, anvandarnamn, namn, roll, beredare, aktiv, far_hantera_artiklar, telefon, epost, skapad "
            "FROM anvandare ORDER BY roll, anvandarnamn").fetchall())
    return jsonify({'anvandare': rader})


@app.post('/api/admin/anvandare')
@admin_required
def admin_skapa_anvandare():
    d = request.get_json(silent=True) or {}
    anvandarnamn = (d.get('anvandarnamn') or '').strip().lower()
    namn         = (d.get('namn') or '').strip()
    losenord     = (d.get('losenord') or '').strip()
    roll         = (d.get('roll') or 'beredare').strip()
    beredare     = (d.get('beredare') or '').strip() or None
    far_art      = 1 if d.get('far_hantera_artiklar') else 0
    telefon      = (d.get('telefon') or '').strip()
    epost        = (d.get('epost') or '').strip()
    if not anvandarnamn: return fel('Användarnamn är obligatoriskt.')
    if not losenord:     return fel('Lösenord är obligatoriskt.')
    if roll not in GILTIGA_ROLLER:
        return fel(f'Ogiltig roll. Välj: {", ".join(GILTIGA_ROLLER)}')
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO anvandare (anvandarnamn,namn,losenord_hash,roll,beredare,aktiv,far_hantera_artiklar,telefon,epost,skapad) "
                "VALUES (?,?,?,?,?,1,?,?,?,?)",
                (anvandarnamn, namn, hash_pw(losenord), roll, beredare, far_art, telefon, epost, nu()))
            conn.commit()
            rad = row_to_dict(conn.execute(
                "SELECT id, anvandarnamn, namn, roll, beredare, aktiv, far_hantera_artiklar, telefon, epost, skapad "
                "FROM anvandare WHERE id=?", (cur.lastrowid,)).fetchone())
            return jsonify({'anvandare': rad}), 201
        except Exception as e:
            return fel(f'Användarnamnet "{anvandarnamn}" finns redan.') if 'UNIQUE' in str(e) else fel(str(e))


@app.put('/api/admin/anvandare/<int:uid>')
@admin_required
def admin_uppdatera_anvandare(uid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM anvandare WHERE id=?", (uid,)).fetchone()
        if not bef: return fel('Användaren hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        roll = (d.get('roll') or bef['roll']).strip()
        if roll not in GILTIGA_ROLLER:
            return fel(f'Ogiltig roll. Välj: {", ".join(GILTIGA_ROLLER)}')
        namn     = (d.get('namn', bef['namn']) or '').strip()
        beredare = (d.get('beredare', bef['beredare']) or '').strip() or None
        aktiv    = int(d.get('aktiv', bef['aktiv']))
        far_art  = 1 if d.get('far_hantera_artiklar', bef['far_hantera_artiklar']) else 0
        telefon  = (d.get('telefon', bef['telefon']) or '').strip()
        epost    = (d.get('epost', bef['epost']) or '').strip()
        losenord = (d.get('losenord') or '').strip()
        if losenord:
            conn.execute("UPDATE anvandare SET losenord_hash=? WHERE id=?",
                         (hash_pw(losenord), uid))
        conn.execute(
            "UPDATE anvandare SET namn=?, roll=?, beredare=?, aktiv=?, far_hantera_artiklar=?, telefon=?, epost=? WHERE id=?",
            (namn, roll, beredare, aktiv, far_art, telefon, epost, uid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT id, anvandarnamn, namn, roll, beredare, aktiv, far_hantera_artiklar, telefon, epost, skapad "
            "FROM anvandare WHERE id=?", (uid,)).fetchone())
    return jsonify({'anvandare': rad})


@app.delete('/api/admin/anvandare/<int:uid>')
@admin_required
def admin_ta_bort_anvandare(uid):
    with get_db() as conn:
        rad = conn.execute("SELECT anvandarnamn FROM anvandare WHERE id=?", (uid,)).fetchone()
        if not rad: return fel('Användaren hittades inte.', 404)
        # Skydda mot att radera sista admin-kontot
        if conn.execute("SELECT roll FROM anvandare WHERE id=?", (uid,)).fetchone()['roll'] == 'admin':
            kvar = conn.execute("SELECT COUNT(*) FROM anvandare WHERE roll='admin' AND aktiv=1").fetchone()[0]
            if kvar <= 1:
                return fel('Kan inte ta bort det sista admin-kontot.', 400)
        conn.execute("DELETE FROM anvandare WHERE id=?", (uid,))
        conn.commit()
    return jsonify({'meddelande': f'Användare "{rad["anvandarnamn"]}" borttagen.'})


# ============================================================
# PROFIL – inloggad användare hanterar SITT EGNA konto
# ============================================================

@app.get('/api/profil')
def hamta_profil():
    uid = session.get('user_id')
    if not uid:
        return fel('Ingen personlig profil (delat konto).', 404)
    with get_db() as conn:
        rad = conn.execute(
            "SELECT id, anvandarnamn, namn, roll, telefon, epost FROM anvandare WHERE id=?",
            (uid,)).fetchone()
    if not rad:
        return fel('Profilen hittades inte.', 404)
    return jsonify({'profil': row_to_dict(rad)})


@app.put('/api/profil')
def uppdatera_profil():
    """Inloggad användare ändrar SITT EGNA lösenord/telefon/epost."""
    uid = session.get('user_id')
    if not uid:
        return fel('Ingen personlig profil (delat konto).', 404)
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM anvandare WHERE id=?", (uid,)).fetchone()
        if not bef:
            return fel('Profilen hittades inte.', 404)
        telefon  = (d.get('telefon', bef['telefon']) or '').strip()
        epost    = (d.get('epost', bef['epost']) or '').strip()
        losenord = (d.get('losenord') or '').strip()
        if losenord:
            if len(losenord) < 4:
                return fel('Lösenordet måste vara minst 4 tecken.')
            conn.execute("UPDATE anvandare SET losenord_hash=? WHERE id=?",
                         (hash_pw(losenord), uid))
        conn.execute("UPDATE anvandare SET telefon=?, epost=? WHERE id=?",
                     (telefon, epost, uid))
        conn.commit()
        rad = conn.execute(
            "SELECT id, anvandarnamn, namn, roll, telefon, epost FROM anvandare WHERE id=?",
            (uid,)).fetchone()
    return jsonify({'profil': row_to_dict(rad),
                    'meddelande': 'Profil uppdaterad.' + (' Lösenord ändrat.' if losenord else '')})


@app.get('/api/kontakter')
def hamta_kontakter():
    """Kontaktlista för alla aktiva användare (alla inloggade får läsa)."""
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT namn, anvandarnamn, roll, beredare, telefon, epost "
            "FROM anvandare WHERE aktiv=1 ORDER BY roll, namn, anvandarnamn").fetchall())
    return jsonify({'kontakter': rader})


# ============================================================
# ADMIN – Mall-inputfält
# ============================================================

@app.get('/api/admin/mallar/<int:mid>/inputfalt')
@admin_required
def hamta_mall_inputfalt(mid):
    with get_db() as conn:
        return jsonify({'inputfalt': rows_to_list(conn.execute(
            "SELECT * FROM mall_inputfalt WHERE mall_id=? ORDER BY sortering", (mid,)).fetchall())})


@app.put('/api/admin/mallar/inputfalt/<int:fid>')
@admin_required
def uppdatera_mall_inputfalt(fid):
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM mall_inputfalt WHERE id=?", (fid,)).fetchone()
        if not bef: return fel('Fältet hittades inte.', 404)
        conn.execute("UPDATE mall_inputfalt SET etikett=?,hjalp=?,obligatorisk=? WHERE id=?",
                     (d.get('etikett', bef['etikett']),
                      d.get('hjalp', bef['hjalp']),
                      d.get('obligatorisk', bef['obligatorisk']), fid))
        conn.commit()
        return jsonify(row_to_dict(conn.execute("SELECT * FROM mall_inputfalt WHERE id=?", (fid,)).fetchone()))


# ============================================================
# KONSTRUKTIONER
# ============================================================

KONSTRUKTIONSTYPER = {
    'Kabelskåp': [
        'Riskhantering utförd och dokumenterad',
        'Leveranskontroll utförd',
        'Kabelskåp placerade enligt beredningshandlingar',
        'Kabelskåp i rätt marknivå',
        'Kabelskåp, kontroll av moment på förmonterade apparater',
        'Samtliga av oss utförda anslutningar dragna med rätt moment',
        'Anslutningar i kabelskåp uppfyller IP 2X',
        'Parallellhandtag monterat i kabelskåp',
        'Potentialutjämning utförd',
        'Egenkontroll utförd på utrustning och mätinstrument',
        'Jordtag mätta och protokollförda',
        'Kontinuitetsmätning utförd på berörd anläggning',
        'Fasföljd kontrollerad, ringa in (går rätt) (går fel)',
        'Spänningsprovning, Fas-N 225-240 V, Fas-Fas 390-415 V',
        'Tjälskjutningsskruvar i kabelskåp avlägsnade (i dialog med beställare)',
        'Snökäpp monterat på kabelskåp',
    ],
    'Kabelförläggning': [
        'Schakt och djup: Kontrollera att schaktet har rätt djup enligt ritning/standard '
        '(vanligtvis ca 35-70 cm beroende på anläggning). Botten ska vara jämn och fri från vassa stenar.',
        'Bäddmaterial: Säkerställ att korrekt sandbädd (eller annat föreskrivet material) är utlagd '
        'under kabeln. Tillräcklig tjocklek (ofta minst 10 cm).',
        'Kabelplacering: Kabeln ska ligga rakt och utan onödiga böjar eller spänningar. '
        'Rätt avstånd till andra kablar/ledningar ska hållas.',
        'Skydd och markering: Kabelskyddsband ska placeras korrekt ovan kabeln '
        '(vanligtvis ca 10-20 cm ovan).',
        'Återfyllning och dokumentation: Återfyllning ska ske med rätt material och packas enligt krav. '
        'Fotodokumentation och inmätning ska vara utförd innan igenfyllning.',
    ],
    'Nätstation': [
        'Riskhantering utförd och dokumenterad',
        'Leveranskontroll utförd',
        'Nätstation placerade enligt beredningshandlingar',
        'Nätsstationen i rätt marknivå',
        'Nätstation, kontroll av moment på förmonterade apparater',
        'Samtliga av oss utförda anslutningar dragna med rätt moment',
        'Anslutningar i nätsstationen uppfyller IP 2X',
        'Parallellhandtag monterat i kabelskåp',
        'Potentialutjämning utförd',
        'Egenkontroll utförd på utrustning och mätinstrument',
        'Jordtag mätta och protokollförda',
        'Kontinuitetsmätning utförd på berörd anläggning',
        'Fasföljd kontrollerad, ringa in (går rätt) (går fel)',
        'Spänningsprovning, Fas-N 225-240 V, Fas-Fas 390-415 V',
        'Tjälskjutningsskruvar i kabelskåp avlägsnade (i dialog med beställare)',
    ],
    'Övrigt': [
        'Riskhantering utförd och dokumenterad',
        'Arbetet utfört enligt beredningshandlingar',
        'Märkning utförd enligt anvisningar',
        'Fotodokumentation utförd',
    ],
}

GILTIGA_STATUSAR_KONSTR = ('Pågående', 'Klar', 'Pausad', 'Avbruten')


@app.get('/api/konstruktionstyper')
def lista_konstruktionstyper():
    result = []
    for typ, punkter in KONSTRUKTIONSTYPER.items():
        result.append({'typ': typ, 'egenkontroll': punkter})
    return jsonify({'typer': result})


def _hamta_konstruktion_komplett(conn, kid):
    k = conn.execute("SELECT * FROM konstruktioner WHERE id=?", (kid,)).fetchone()
    if not k:
        return None
    d = row_to_dict(k)
    d['rader'] = rows_to_list(conn.execute(
        "SELECT * FROM konstruktion_rader WHERE konstruktion_id=? ORDER BY sortering",
        (kid,)).fetchall())
    d['egenkontroll'] = rows_to_list(conn.execute(
        "SELECT * FROM konstruktion_egenkontroll WHERE konstruktion_id=? ORDER BY sortering",
        (kid,)).fetchall())
    return d


@app.get('/api/konstruktioner')
def lista_konstruktioner():
    typ        = request.args.get('typ', '').strip()
    status     = request.args.get('status', '').strip()
    sok        = request.args.get('sok', '').strip()
    projekt_id = request.args.get('projekt_id', '').strip()
    sql = "SELECT * FROM konstruktioner WHERE 1=1"
    params = []
    if projekt_id: sql += " AND projekt_id=?"; params.append(int(projekt_id))
    if typ:        sql += " AND typ=?";         params.append(typ)
    if status:     sql += " AND status=?";      params.append(status)
    if sok:
        sql += " AND (namn LIKE ? OR byggnr LIKE ? OR fri_id LIKE ?)"
        params += [f'%{sok}%'] * 3
    sql += " ORDER BY skapad DESC"
    with get_db() as conn:
        return jsonify({'konstruktioner': rows_to_list(conn.execute(sql, params).fetchall())})


@app.post('/api/konstruktioner')
def skapa_konstruktion():
    d = request.get_json(silent=True) or {}
    typ  = (d.get('typ') or '').strip()
    namn = (d.get('namn') or '').strip()
    if not typ:  return fel('Typ är obligatorisk.')
    if typ not in KONSTRUKTIONSTYPER: return fel(f'Ogiltig typ: {typ}')
    if not namn: return fel('Namn är obligatoriskt.')
    tidpunkt = nu()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO konstruktioner (projekt_id,typ,byggnr,namn,fri_id,anmarkning,status,skapad,uppdaterad)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (d.get('projekt_id') or None,
             typ, (d.get('byggnr') or '').strip() or None,
             namn,
             (d.get('fri_id') or '').strip() or None,
             (d.get('anmarkning') or '').strip() or None,
             d.get('status', 'Pågående'),
             tidpunkt, tidpunkt))
        kid = cur.lastrowid
        # Seed egenkontrollpunkter från typen
        for i, punkt in enumerate(KONSTRUKTIONSTYPER[typ]):
            conn.execute(
                "INSERT INTO konstruktion_egenkontroll "
                "(konstruktion_id, punkt, utford, ej_relevant, sortering) VALUES (?,?,0,0,?)",
                (kid, punkt, i))
        conn.commit()
        return jsonify({'konstruktion': _hamta_konstruktion_komplett(conn, kid)}), 201


@app.get('/api/konstruktioner/<int:kid>')
def hamta_konstruktion(kid):
    with get_db() as conn:
        k = _hamta_konstruktion_komplett(conn, kid)
    if not k: return fel('Konstruktionen hittades inte.', 404)
    return jsonify({'konstruktion': k})


@app.put('/api/konstruktioner/<int:kid>')
def uppdatera_konstruktion(kid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM konstruktioner WHERE id=?", (kid,)).fetchone()
        if not bef: return fel('Konstruktionen hittades inte.', 404)
        d = request.get_json(silent=True) or {}

        # Uppdatera grundfält
        updates = ["uppdaterad=?"]
        params  = [nu()]
        for falt in ('typ', 'byggnr', 'namn', 'fri_id', 'anmarkning', 'status'):
            if falt in d:
                updates.append(f"{falt}=?")
                params.append((d[falt] or '').strip() or None if falt != 'typ' and falt != 'status' else d[falt])
        params.append(kid)
        conn.execute(f"UPDATE konstruktioner SET {','.join(updates)} WHERE id=?", params)

        # Uppdatera rader om skickade
        rader_in = d.get('rader')
        if rader_in is not None:
            conn.execute("DELETE FROM konstruktion_rader WHERE konstruktion_id=?", (kid,))
            for i, r in enumerate(rader_in):
                if not r: continue
                conn.execute(
                    "INSERT INTO konstruktion_rader "
                    "(konstruktion_id,artikel_id,artikelnamn,enhet,antal,moduler,anteckning,sortering)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (kid, r.get('artikel_id'), r.get('artikelnamn', ''),
                     r.get('enhet', ''), float(r.get('antal', 1)),
                     int(r.get('moduler', 0)),
                     r.get('anteckning', '') or None, i))

        # Uppdatera egenkontroll om skickad
        egk_in = d.get('egenkontroll')
        if egk_in is not None:
            for item in egk_in:
                conn.execute(
                    "UPDATE konstruktion_egenkontroll SET utford=?, ej_relevant=? WHERE id=? AND konstruktion_id=?",
                    (int(item.get('utford', 0)), int(item.get('ej_relevant', 0)),
                     item['id'], kid))

        conn.commit()
        return jsonify({'konstruktion': _hamta_konstruktion_komplett(conn, kid)})


@app.delete('/api/konstruktioner/<int:kid>')
def ta_bort_konstruktion(kid):
    with get_db() as conn:
        rad = conn.execute("SELECT namn FROM konstruktioner WHERE id=?", (kid,)).fetchone()
        if not rad: return fel('Konstruktionen hittades inte.', 404)
        conn.execute("DELETE FROM konstruktioner WHERE id=?", (kid,))
        conn.commit()
    return jsonify({'meddelande': f'Konstruktion "{rad["namn"]}" borttagen.'})


@app.get('/api/konstruktioner/<int:kid>/pdf')
def konstruktion_pdf(kid):
    from pdf_generator import skapa_konstruktion_pdf
    with get_db() as conn:
        k = _hamta_konstruktion_komplett(conn, kid)
        if not k: return fel('Konstruktionen hittades inte.', 404)
        inst = {r['nyckel']: r['varde'] for r in
                conn.execute("SELECT nyckel,varde FROM installningar").fetchall()}
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
    pdf = skapa_konstruktion_pdf(k, inst, enr_lookup)
    filnamn = f"konstruktion_{kid}_{k['namn'][:20].replace(' ','_')}.pdf"
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{filnamn}"'})


@app.get('/api/konstruktioner/materiallista/pdf')
def konstruktioner_materiallista_pdf():
    from pdf_generator import skapa_konstruktioner_materiallista_pdf
    projekt_id = request.args.get('projekt_id', '').strip()
    with get_db() as conn:
        inst = {r['nyckel']: r['varde'] for r in
                conn.execute("SELECT nyckel,varde FROM installningar").fetchall()}
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
        if projekt_id:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner WHERE projekt_id=? ORDER BY typ, namn",
                (int(projekt_id),)).fetchall()]
            projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (int(projekt_id),)).fetchone()
            filnamn = f"{projekt['projektnummer']}_konstruktioner_materiallista.pdf" if projekt else "konstruktioner_materiallista.pdf"
        else:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner ORDER BY typ, namn").fetchall()]
            filnamn = "konstruktioner_materiallista.pdf"
        konstruktioner = [_hamta_konstruktion_komplett(conn, kid) for kid in ids]
    pdf = skapa_konstruktioner_materiallista_pdf(konstruktioner, inst, enr_lookup)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{filnamn}"'})


@app.get('/api/konstruktioner/byggprotokoll/pdf')
def konstruktioner_byggprotokoll_pdf():
    from pdf_generator import skapa_konstruktioner_byggprotokoll_pdf
    projekt_id = request.args.get('projekt_id', '').strip()
    with get_db() as conn:
        inst = {r['nyckel']: r['varde'] for r in
                conn.execute("SELECT nyckel,varde FROM installningar").fetchall()}
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
        if projekt_id:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner WHERE projekt_id=? ORDER BY typ, namn",
                (int(projekt_id),)).fetchall()]
            projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (int(projekt_id),)).fetchone()
            filnamn = f"{projekt['projektnummer']}_byggprotokoll.pdf" if projekt else "byggprotokoll.pdf"
        else:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner ORDER BY typ, namn").fetchall()]
            filnamn = "byggprotokoll.pdf"
        konstruktioner = [_hamta_konstruktion_komplett(conn, kid) for kid in ids]
    pdf = skapa_konstruktioner_byggprotokoll_pdf(konstruktioner, inst, enr_lookup)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{filnamn}"'})


@app.get('/api/konstruktioner/materiallista/excel')
def konstruktioner_materiallista_excel():
    from excel_generator import skapa_konstruktioner_materiallista_excel
    projekt_id = request.args.get('projekt_id', '').strip()
    with get_db() as conn:
        enr_lookup = {r['artikelnamn']: r['artikelnummer'] for r in conn.execute(
            "SELECT a.artikelnamn, al.artikelnummer FROM artikel_leverantor al "
            "JOIN artiklar a ON a.id = al.artikel_id "
            "JOIN leverantorer l ON l.id = al.leverantor_id "
            "WHERE l.namn = 'Onninen' AND al.artikelnummer IS NOT NULL"
        ).fetchall()}
        if projekt_id:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner WHERE projekt_id=? ORDER BY typ, namn",
                (int(projekt_id),)).fetchall()]
            projekt = conn.execute("SELECT * FROM projekt WHERE id=?", (int(projekt_id),)).fetchone()
            projekt_namn = f"{projekt['projektnummer']} – {projekt['projektnamn']}" if projekt else ''
            filnamn = f"{projekt['projektnummer']}_konstruktioner_materiallista.xlsx" if projekt else "konstruktioner_materiallista.xlsx"
        else:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM konstruktioner ORDER BY typ, namn").fetchall()]
            projekt_namn = ''
            filnamn = "konstruktioner_materiallista.xlsx"
        konstruktioner = [_hamta_konstruktion_komplett(conn, kid) for kid in ids]
    xlsx = skapa_konstruktioner_materiallista_excel(konstruktioner, projekt_namn, enr_lookup)
    return Response(xlsx,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{filnamn}"'})


# ============================================================
# ANSLUTNING (Analys-fliken)
# ============================================================

@app.get('/api/anslutning')
def hamta_anslutning():
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT * FROM anslutning_projekt ORDER BY skapad"
        ).fetchall())
    return jsonify({'projekt': rader})


@app.post('/api/anslutning/import')
def importera_anslutning():
    items = request.get_json(silent=True)
    if not isinstance(items, list):
        return fel('Förväntade en lista av ärenden.')
    tidpunkt = nu()
    with get_db() as conn:
        conn.execute("DELETE FROM anslutning_projekt")
        for item in items:
            pid = str(item.get('id') or '').strip()
            if not pid:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO anslutning_projekt "
                "(id,namn,kund,fas,berStart,berSlut,montStart,montSlut,driftDat,blockering,notat,bestallningKlar,beredare,skapad)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid,
                 str(item.get('namn') or ''),
                 str(item.get('kund') or ''),
                 str(item.get('fas') or 'Tidig fas'),
                 item.get('berStart') or None,
                 item.get('berSlut') or None,
                 item.get('montStart') or None,
                 item.get('montSlut') or None,
                 item.get('driftDat') or None,
                 item.get('blockering') or None,
                 str(item.get('notat') or ''),
                 item.get('bestallningKlar') or None,
                 item.get('beredare') or None,
                 tidpunkt))
        conn.commit()
    return jsonify({'meddelande': f'{len(items)} ärenden importerade.'})


@app.put('/api/anslutning/<string:pid>')
def uppdatera_anslutning(pid):
    with get_db() as conn:
        bef = conn.execute(
            "SELECT * FROM anslutning_projekt WHERE id=?", (pid,)
        ).fetchone()
        if not bef:
            return fel('Ärendet hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        conn.execute(
            "UPDATE anslutning_projekt SET fas=?,blockering=?,notat=? WHERE id=?",
            (str(d.get('fas') or bef['fas']),
             d.get('blockering') or None,
             str(d.get('notat') or ''),
             pid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM anslutning_projekt WHERE id=?", (pid,)
        ).fetchone())
    return jsonify({'projekt': rad})


# ============================================================
# FAKTURERING — Statistik
# ============================================================

@app.get('/api/fakturering')
def hamta_fakturering():
    with get_db() as conn:
        rader = conn.execute(
            "SELECT * FROM fakturering ORDER BY manad, projektledare, id"
        ).fetchall()
    return jsonify({'rader': rows_to_list(rader)})


@app.post('/api/fakturering/import')
def importera_fakturering():
    data = request.get_json(force=True)
    manad   = (data.get('manad') or '').strip()
    projekt = data.get('projekt', [])
    if not manad:
        return fel('manad saknas')
    if not isinstance(projekt, list) or len(projekt) == 0:
        return fel('projekt saknas')
    tidpunkt = nu()
    with get_db() as conn:
        conn.execute("DELETE FROM fakturering WHERE manad=?", (manad,))
        for p in projekt:
            conn.execute(
                "INSERT INTO fakturering "
                "(id,projektnamn,projektledare,utestående,verklIntakt,verklKostn,budgIntakt,budgKostn,fardigt,manad,importerad) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(p.get('id') or ''),
                    str(p.get('projektnamn') or ''),
                    str(p.get('projektledare') or ''),
                    float(p.get('utestående') or 0),
                    float(p.get('verklIntakt') or 0),
                    float(p.get('verklKostn') or 0),
                    float(p.get('budgIntakt') or 0),
                    float(p.get('budgKostn') or 0),
                    float(p.get('fardigt') or 0),
                    manad,
                    tidpunkt,
                )
            )
    return jsonify({'ok': True, 'antal': len(projekt), 'manad': manad})


@app.delete('/api/fakturering/<string:manad>')
def radera_fakturering_manad(manad):
    with get_db() as conn:
        conn.execute("DELETE FROM fakturering WHERE manad=?", (manad,))
    return jsonify({'ok': True})


# ============================================================
# MASKINPLANERING (delad med UE)
# ============================================================

GILTIGA_MASKIN_STATUS = ('Planerad', 'Pågående', 'Klar', 'Inställd')


@app.get('/api/maskinplanering')
def lista_maskinplanering():
    status = request.args.get('status', '').strip()
    maskin = request.args.get('maskin', '').strip()
    sok    = request.args.get('sok', '').strip()
    sql = "SELECT * FROM maskinplanering WHERE 1=1"
    params = []
    if status: sql += " AND status=?";  params.append(status)
    if maskin: sql += " AND maskin=?";  params.append(maskin)
    if sok:
        sql += " AND (projektnamn LIKE ? OR maskin LIKE ? OR ue LIKE ? OR notat LIKE ?)"
        params += [f'%{sok}%'] * 4
    sql += " ORDER BY startdatum IS NULL, startdatum, id"
    with get_db() as conn:
        return jsonify({'maskinplanering': rows_to_list(conn.execute(sql, params).fetchall())})


@app.post('/api/maskinplanering')
def skapa_maskinplanering():
    d = request.get_json(silent=True) or {}
    maskin = (d.get('maskin') or '').strip()
    if not maskin:
        return fel('Maskin är obligatorisk.')
    status = (d.get('status') or 'Planerad').strip()
    if status not in GILTIGA_MASKIN_STATUS:
        return fel(f'Ogiltig status. Välj: {", ".join(GILTIGA_MASKIN_STATUS)}')
    tidpunkt = nu()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO maskinplanering "
            "(projekt_id,projektnamn,maskin,ue,startdatum,slutdatum,status,notat,skapad,uppdaterad) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (d.get('projekt_id') or None,
             (d.get('projektnamn') or '').strip(),
             maskin,
             (d.get('ue') or '').strip() or None,
             d.get('startdatum') or None,
             d.get('slutdatum') or None,
             status,
             (d.get('notat') or '').strip() or None,
             tidpunkt, tidpunkt))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM maskinplanering WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'rad': rad}), 201


@app.put('/api/maskinplanering/<int:mid>')
def uppdatera_maskinplanering(mid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM maskinplanering WHERE id=?", (mid,)).fetchone()
        if not bef: return fel('Planeringsraden hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        status = (d.get('status', bef['status']) or 'Planerad').strip()
        if status not in GILTIGA_MASKIN_STATUS:
            return fel(f'Ogiltig status. Välj: {", ".join(GILTIGA_MASKIN_STATUS)}')
        maskin = (d.get('maskin', bef['maskin']) or '').strip()
        if not maskin:
            return fel('Maskin är obligatorisk.')
        conn.execute(
            "UPDATE maskinplanering SET projekt_id=?,projektnamn=?,maskin=?,ue=?,"
            "startdatum=?,slutdatum=?,status=?,notat=?,uppdaterad=? WHERE id=?",
            (d.get('projekt_id', bef['projekt_id']) or None,
             (d.get('projektnamn', bef['projektnamn']) or '').strip(),
             maskin,
             (d.get('ue', bef['ue']) or '').strip() or None,
             d.get('startdatum', bef['startdatum']) or None,
             d.get('slutdatum', bef['slutdatum']) or None,
             status,
             (d.get('notat', bef['notat']) or '').strip() or None,
             nu(), mid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM maskinplanering WHERE id=?", (mid,)).fetchone())
    return jsonify({'rad': rad})


@app.delete('/api/maskinplanering/<int:mid>')
def ta_bort_maskinplanering(mid):
    with get_db() as conn:
        rad = conn.execute("SELECT id FROM maskinplanering WHERE id=?", (mid,)).fetchone()
        if not rad: return fel('Planeringsraden hittades inte.', 404)
        conn.execute("DELETE FROM maskinplanering WHERE id=?", (mid,))
        conn.commit()
    return jsonify({'meddelande': 'Planeringsrad borttagen.'})


# ============================================================
# PROJEKT – STATUS (Excel-planeringsfält, nyckel/värde)
# ============================================================

@app.get('/api/projekt/status-alla')
def alla_projekt_status():
    with get_db() as conn:
        rader = conn.execute("SELECT projekt_id, falt, varde FROM projekt_status").fetchall()
    result = {}
    for r in rader:
        result.setdefault(str(r['projekt_id']), {})[r['falt']] = r['varde']
    return jsonify({'status': result})


@app.get('/api/projekt/<int:pid>/status')
def hamta_projekt_status(pid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        rader = conn.execute("SELECT falt, varde FROM projekt_status WHERE projekt_id=?", (pid,)).fetchall()
    return jsonify({'status': {r['falt']: r['varde'] for r in rader}})


@app.put('/api/projekt/<int:pid>/status')
def spara_projekt_status(pid):
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (pid,)).fetchone():
            return fel('Projektet hittades inte.', 404)
        for falt, varde in d.items():
            v = (str(varde).strip() if varde is not None else '')
            if v == '':
                conn.execute("DELETE FROM projekt_status WHERE projekt_id=? AND falt=?", (pid, falt))
            else:
                conn.execute(
                    "INSERT INTO projekt_status (projekt_id, falt, varde) VALUES (?,?,?) "
                    "ON CONFLICT(projekt_id, falt) DO UPDATE SET varde=excluded.varde",
                    (pid, falt, v))
        conn.execute("UPDATE projekt SET uppdaterad=? WHERE id=?", (nu(), pid))
        conn.commit()
        rader = conn.execute("SELECT falt, varde FROM projekt_status WHERE projekt_id=?", (pid,)).fetchall()
    return jsonify({'status': {r['falt']: r['varde'] for r in rader}})


# ============================================================
# KABELTRUMMOR
# ============================================================

@app.get('/api/kabeltrummor')
def lista_kabeltrummor():
    with get_db() as conn:
        return jsonify({'kabeltrummor': rows_to_list(conn.execute(
            "SELECT * FROM kabeltrummor ORDER BY projekt_text, kabeltyp, id").fetchall())})


@app.post('/api/kabeltrummor')
def skapa_kabeltrumma():
    d = request.get_json(silent=True) or {}
    tid = nu()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO kabeltrummor (projekt_id,projekt_text,kabeltyp,uttagen,kvar,notat,skapad,uppdaterad) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (d.get('projekt_id') or None, (d.get('projekt_text') or '').strip(),
             (d.get('kabeltyp') or '').strip(),
             float(d.get('uttagen') or 0), float(d.get('kvar') or 0),
             (d.get('notat') or '').strip() or None, tid, tid))
        conn.commit()
        rad = row_to_dict(conn.execute("SELECT * FROM kabeltrummor WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'rad': rad}), 201


@app.put('/api/kabeltrummor/<int:kid>')
def uppdatera_kabeltrumma(kid):
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM kabeltrummor WHERE id=?", (kid,)).fetchone()
        if not bef: return fel('Raden hittades inte.', 404)
        d = request.get_json(silent=True) or {}
        conn.execute(
            "UPDATE kabeltrummor SET projekt_text=?,kabeltyp=?,uttagen=?,kvar=?,notat=?,uppdaterad=? WHERE id=?",
            ((d.get('projekt_text', bef['projekt_text']) or '').strip(),
             (d.get('kabeltyp', bef['kabeltyp']) or '').strip(),
             float(d.get('uttagen', bef['uttagen']) or 0),
             float(d.get('kvar', bef['kvar']) or 0),
             (d.get('notat', bef['notat']) or '').strip() or None, nu(), kid))
        conn.commit()
        rad = row_to_dict(conn.execute("SELECT * FROM kabeltrummor WHERE id=?", (kid,)).fetchone())
    return jsonify({'rad': rad})


@app.delete('/api/kabeltrummor/<int:kid>')
def ta_bort_kabeltrumma(kid):
    with get_db() as conn:
        conn.execute("DELETE FROM kabeltrummor WHERE id=?", (kid,))
        conn.commit()
    return jsonify({'meddelande': 'Rad borttagen.'})


# ============================================================
# ADMIN – Import av projektplanering (Excel)
# ============================================================

@app.post('/api/admin/import-projektplanering')
@admin_required
def import_projektplanering():
    d = request.get_json(silent=True) or {}
    projekt_in = d.get('projekt', [])
    kabel_in   = d.get('kabeltrummor', [])
    ersatt_kabel = bool(d.get('ersatt_kabeltrummor'))
    tid = nu()
    skapade = uppdaterade = statusrader = 0
    with get_db() as conn:
        for p in projekt_in:
            ib = str(p.get('ib') or '').strip()
            if not ib:
                continue
            namn     = (p.get('namn') or '').strip() or ib
            beredare = (p.get('beredare') or '').strip()
            status   = p.get('status') or {}
            bef = conn.execute(
                "SELECT id FROM projekt WHERE projektnummer=? OR ib_nummer=?", (ib, ib)).fetchone()
            if bef:
                pid = bef['id']
                conn.execute(
                    "UPDATE projekt SET projektnamn=?, beredare=COALESCE(NULLIF(?,''),beredare), "
                    "ib_nummer=?, uppdaterad=? WHERE id=?",
                    (namn, beredare, ib, tid, pid))
                uppdaterade += 1
            else:
                cur = conn.execute(
                    "INSERT INTO projekt (projektnummer,projektnamn,beredare,status,ib_nummer,skapad,uppdaterad) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (ib, namn, beredare or 'Okänd', 'Planerat', ib, tid, tid))
                pid = cur.lastrowid
                skapade += 1
            for falt, varde in status.items():
                v = (str(varde).strip() if varde is not None else '')
                if v == '':
                    continue
                conn.execute(
                    "INSERT INTO projekt_status (projekt_id,falt,varde) VALUES (?,?,?) "
                    "ON CONFLICT(projekt_id,falt) DO UPDATE SET varde=excluded.varde",
                    (pid, falt, v))
                statusrader += 1
        if ersatt_kabel:
            conn.execute("DELETE FROM kabeltrummor")
        for k in kabel_in:
            ib = str(k.get('ib') or '').strip()
            projid = None
            if ib:
                row = conn.execute(
                    "SELECT id FROM projekt WHERE projektnummer=? OR ib_nummer=?", (ib, ib)).fetchone()
                projid = row['id'] if row else None
            conn.execute(
                "INSERT INTO kabeltrummor (projekt_id,projekt_text,kabeltyp,uttagen,kvar,notat,skapad,uppdaterad) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (projid, (k.get('projekt_text') or '').strip(), (k.get('kabeltyp') or '').strip(),
                 float(k.get('uttagen') or 0), float(k.get('kvar') or 0),
                 (k.get('notat') or '').strip() or None, tid, tid))
        conn.commit()
    return jsonify({'skapade': skapade, 'uppdaterade': uppdaterade,
                    'statusrader': statusrader, 'kabeltrummor': len(kabel_in)})


@app.post('/api/admin/sla-ihop-projekt')
@admin_required
def sla_ihop_projekt():
    """Slår ihop två projektposter (dubbletter): flyttar allt från ta_bort_id
    till behall_id och raderar ta_bort_id. behall_id behålls (IB, projektnummer)."""
    d = request.get_json(silent=True) or {}
    behall = d.get('behall_id')
    tabort = d.get('ta_bort_id')
    ny_ib  = (d.get('ib_nummer') or '').strip()
    if not behall or not tabort or behall == tabort:
        return fel('behall_id och ta_bort_id krävs och måste vara olika.')
    with get_db() as conn:
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (behall,)).fetchone():
            return fel('behall_id hittades inte.', 404)
        if not conn.execute("SELECT id FROM projekt WHERE id=?", (tabort,)).fetchone():
            return fel('ta_bort_id hittades inte.', 404)
        # Flytta poster som pekar på ta_bort -> behall
        conn.execute("UPDATE konstruktioner SET projekt_id=? WHERE projekt_id=?", (behall, tabort))
        conn.execute("UPDATE byggprotokoll  SET projekt_id=? WHERE projekt_id=?", (behall, tabort))
        for tbl in ('projekt_tillstand', 'projekt_aktiviteter', 'projekt_budget',
                    'projekt_kostnad', 'projekt_intakt', 'projekt_fas_datum'):
            try:
                conn.execute(f"UPDATE {tbl} SET projekt_id=? WHERE projekt_id=?", (behall, tabort))
            except Exception:
                pass
        # Status och checklista: fyll bara där behall saknar värde (undvik UNIQUE-krock)
        for r in conn.execute("SELECT falt,varde FROM projekt_status WHERE projekt_id=?", (tabort,)).fetchall():
            conn.execute("INSERT OR IGNORE INTO projekt_status (projekt_id,falt,varde) VALUES (?,?,?)",
                         (behall, r['falt'], r['varde']))
        for r in conn.execute("SELECT item_nr,utford,ej_relevant FROM projekt_checklistor WHERE projekt_id=?", (tabort,)).fetchall():
            conn.execute("INSERT OR IGNORE INTO projekt_checklistor (projekt_id,item_nr,utford,ej_relevant) VALUES (?,?,?,?)",
                         (behall, r['item_nr'], r['utford'], r['ej_relevant']))
        if ny_ib:
            conn.execute("UPDATE projekt SET ib_nummer=? WHERE id=?", (ny_ib, behall))
        conn.execute("UPDATE projekt SET uppdaterad=? WHERE id=?", (nu(), behall))
        conn.execute("DELETE FROM projekt WHERE id=?", (tabort,))
        conn.commit()
    return jsonify({'ok': True, 'behall_id': behall, 'borttaget': tabort})


# ============================================================
# RUTTPLANERING (v39) – fältserviceplanering / ruttoptimering
# ============================================================

def _rutt_uid():
    """Inloggad användares id (None vid delat app-lösenord utan personligt konto)."""
    return session.get('user_id')


def _komp_str(v):
    """Normalisera kompetenser till komma-separerad sträng."""
    if isinstance(v, list):
        return ', '.join(str(x).strip() for x in v if str(x).strip())
    return (v or '').strip()


# ---- Tekniker (delat register, alla planerare delar samma tekniker) ----
@app.get('/api/rutt/tekniker')
def rutt_lista_tekniker():
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_tekniker ORDER BY aktiv DESC, namn").fetchall())
    return jsonify({'tekniker': rader})


@app.post('/api/rutt/tekniker')
def rutt_skapa_tekniker():
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn:
        return fel('Teknikerns namn är obligatoriskt.')
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO rutt_tekniker "
            "(namn,kompetenser,arbetstid_start,arbetstid_slut,start_lat,start_lon,slut_lat,slut_lon,farg,aktiv,skapad) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (namn, _komp_str(d.get('kompetenser')),
             d.get('arbetstid_start') or '07:00', d.get('arbetstid_slut') or '16:00',
             _num(d.get('start_lat')), _num(d.get('start_lon')),
             _num(d.get('slut_lat')), _num(d.get('slut_lon')),
             (d.get('farg') or None), 1 if d.get('aktiv', True) else 0, nu()))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_tekniker WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'tekniker': rad}), 201


@app.put('/api/rutt/tekniker/<int:tid>')
def rutt_uppdatera_tekniker(tid):
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM rutt_tekniker WHERE id=?", (tid,)).fetchone()
        if not bef:
            return fel('Teknikern hittades inte.', 404)
        # default samma slutpunkt som startpunkt om slut saknas
        start_lat = _num(d.get('start_lat', bef['start_lat']))
        start_lon = _num(d.get('start_lon', bef['start_lon']))
        slut_lat = _num(d.get('slut_lat', bef['slut_lat']))
        slut_lon = _num(d.get('slut_lon', bef['slut_lon']))
        if slut_lat is None and slut_lon is None:
            slut_lat, slut_lon = start_lat, start_lon
        conn.execute(
            "UPDATE rutt_tekniker SET namn=?, kompetenser=?, arbetstid_start=?, arbetstid_slut=?, "
            "start_lat=?, start_lon=?, slut_lat=?, slut_lon=?, farg=?, aktiv=? WHERE id=?",
            ((d.get('namn', bef['namn']) or '').strip(),
             _komp_str(d.get('kompetenser', bef['kompetenser'])),
             d.get('arbetstid_start', bef['arbetstid_start']) or '07:00',
             d.get('arbetstid_slut', bef['arbetstid_slut']) or '16:00',
             start_lat, start_lon, slut_lat, slut_lon,
             (d.get('farg', bef['farg']) or None),
             1 if d.get('aktiv', bef['aktiv']) else 0, tid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_tekniker WHERE id=?", (tid,)).fetchone())
    return jsonify({'tekniker': rad})


@app.delete('/api/rutt/tekniker/<int:tid>')
def rutt_ta_bort_tekniker(tid):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM rutt_tekniker WHERE id=?", (tid,)).fetchone():
            return fel('Teknikern hittades inte.', 404)
        conn.execute("DELETE FROM rutt_tekniker WHERE id=?", (tid,))
        conn.commit()
    return jsonify({'meddelande': 'Tekniker borttagen.'})


# ---- Ärendetyper (delat register, namn + default servicetid) ----
@app.get('/api/rutt/arendetyper')
def rutt_lista_arendetyper():
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arendetyp ORDER BY namn").fetchall())
    return jsonify({'arendetyper': rader})


@app.post('/api/rutt/arendetyper')
def rutt_skapa_arendetyp():
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip()
    if not namn:
        return fel('Ärendetypens namn är obligatoriskt.')
    try:
        mins = int(d.get('servicetid_min') or 30)
    except (TypeError, ValueError):
        return fel('Servicetid måste vara ett heltal (minuter).')
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO rutt_arendetyp (namn,servicetid_min,skapad) VALUES (?,?,?)",
                (namn, mins, nu()))
            conn.commit()
        except Exception as e:
            return fel(f'Ärendetypen "{namn}" finns redan.') if 'UNIQUE' in str(e) else fel(str(e))
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_arendetyp WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'arendetyp': rad}), 201


@app.put('/api/rutt/arendetyper/<int:aid>')
def rutt_uppdatera_arendetyp(aid):
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        bef = conn.execute("SELECT * FROM rutt_arendetyp WHERE id=?", (aid,)).fetchone()
        if not bef:
            return fel('Ärendetypen hittades inte.', 404)
        try:
            mins = int(d.get('servicetid_min', bef['servicetid_min']))
        except (TypeError, ValueError):
            return fel('Servicetid måste vara ett heltal (minuter).')
        conn.execute("UPDATE rutt_arendetyp SET namn=?, servicetid_min=? WHERE id=?",
                     ((d.get('namn', bef['namn']) or '').strip(), mins, aid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_arendetyp WHERE id=?", (aid,)).fetchone())
    return jsonify({'arendetyp': rad})


@app.delete('/api/rutt/arendetyper/<int:aid>')
def rutt_ta_bort_arendetyp(aid):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM rutt_arendetyp WHERE id=?", (aid,)).fetchone():
            return fel('Ärendetypen hittades inte.', 404)
        conn.execute("DELETE FROM rutt_arendetyp WHERE id=?", (aid,))
        conn.commit()
    return jsonify({'meddelande': 'Ärendetyp borttagen.'})


# ---- Planeringar (per användare – historik) ----
@app.get('/api/rutt/planeringar')
def rutt_lista_planeringar():
    uid = _rutt_uid()
    if not uid:
        return jsonify({'planeringar': []})
    with get_db() as conn:
        rader = rows_to_list(conn.execute(
            "SELECT p.*, "
            "(SELECT COUNT(*) FROM rutt_arende a WHERE a.planering_id=p.id) AS antal_arenden "
            "FROM rutt_planering p WHERE agare=? ORDER BY COALESCE(datum,'') DESC, id DESC",
            (uid,)).fetchall())
    return jsonify({'planeringar': rader})


@app.post('/api/rutt/planeringar')
def rutt_skapa_planering():
    uid = _rutt_uid()
    if not uid:
        return fel('Du måste vara inloggad med ett personligt konto för att skapa planeringar.', 403)
    d = request.get_json(silent=True) or {}
    namn = (d.get('namn') or '').strip() or 'Ny planering'
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO rutt_planering (agare,namn,datum,status,skapad,uppdaterad) "
            "VALUES (?,?,?,'utkast',?,?)",
            (uid, namn, (d.get('datum') or None), nu(), nu()))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_planering WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({'planering': rad}), 201


def _rutt_sammanfattning(conn, arenden):
    """Per tekniker: stopp, körtid, servicetid, sluttid – ur cachad restidsmatris."""
    tilldelade = [a for a in arenden if a.get('tilldelad_tekniker') is not None]
    if not tilldelade:
        return []
    tek_ids = sorted({a['tilldelad_tekniker'] for a in tilldelade})
    tek_rader = rows_to_list(conn.execute(
        "SELECT * FROM rutt_tekniker WHERE id IN (%s)" % ','.join('?' * len(tek_ids)),
        tek_ids).fetchall())
    tmap = {t['id']: t for t in tek_rader}

    punkter, index = [], {}

    def _pt(lat, lon):
        key = (round(lat, 5), round(lon, 5))
        if key not in index:
            index[key] = len(punkter)
            punkter.append((lat, lon))
        return index[key]

    for t in tek_rader:
        t['_ds'] = _pt(t['start_lat'], t['start_lon'])
        sl_lat = t['slut_lat'] if t['slut_lat'] is not None else t['start_lat']
        sl_lon = t['slut_lon'] if t['slut_lon'] is not None else t['start_lon']
        t['_de'] = _pt(sl_lat, sl_lon)
    for a in tilldelade:
        a['_pt'] = _pt(a['lat'], a['lon'])

    dur, _dist, _k = bygg_matris(conn, punkter, bara_cache=True)

    samm = []
    for tid in tek_ids:
        t = tmap.get(tid)
        if not t:
            continue
        seq = sorted([a for a in tilldelade if a['tilldelad_tekniker'] == tid],
                     key=lambda a: (a['ordning'] if a['ordning'] is not None else 0))
        drive = 0.0
        prev = t['_ds']
        for a in seq:
            drive += dur[prev][a['_pt']] / 60.0
            prev = a['_pt']
        drive += dur[prev][t['_de']] / 60.0
        service = sum(a['servicetid_min'] or 0 for a in seq)
        sista = seq[-1]
        slut = None
        if sista.get('ankomst'):
            slut = _min_hhmm(_hhmm_min(sista['ankomst']) + (sista['servicetid_min'] or 0)
                             + dur[sista['_pt']][t['_de']] / 60.0)
        samm.append({'tekniker_id': tid, 'namn': t['namn'], 'farg': t['farg'],
                     'stopp': len(seq), 'kortid_min': int(round(drive)),
                     'servicetid_min': service, 'sluttid': slut})
    return samm


@app.get('/api/rutt/planeringar/<int:pid>')
def rutt_hamta_planering(pid):
    uid = _rutt_uid()
    with get_db() as conn:
        p = conn.execute("SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)
        arenden = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=? "
            "ORDER BY COALESCE(tilldelad_tekniker,999999), COALESCE(ordning,999999), id",
            (pid,)).fetchall())
        sammanfattning = _rutt_sammanfattning(conn, [dict(a) for a in arenden])
    res = row_to_dict(p)
    res['arenden'] = arenden
    res['sammanfattning'] = sammanfattning
    return jsonify({'planering': res})


@app.put('/api/rutt/planeringar/<int:pid>')
def rutt_uppdatera_planering(pid):
    uid = _rutt_uid()
    d = request.get_json(silent=True) or {}
    with get_db() as conn:
        p = conn.execute("SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)
        conn.execute(
            "UPDATE rutt_planering SET namn=?, datum=?, status=?, uppdaterad=? WHERE id=?",
            ((d.get('namn', p['namn']) or '').strip() or p['namn'],
             (d.get('datum', p['datum']) or None),
             d.get('status', p['status']), nu(), pid))
        conn.commit()
        rad = row_to_dict(conn.execute(
            "SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone())
    return jsonify({'planering': rad})


@app.delete('/api/rutt/planeringar/<int:pid>')
def rutt_ta_bort_planering(pid):
    uid = _rutt_uid()
    with get_db() as conn:
        p = conn.execute("SELECT agare FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)
        conn.execute("DELETE FROM rutt_arende WHERE planering_id=?", (pid,))
        conn.execute("DELETE FROM rutt_planering WHERE id=?", (pid,))
        conn.commit()
    return jsonify({'meddelande': 'Planering borttagen.'})


# ---- Import: förhandsvisning, validering, bekräftelse ----
def _rutt_profiler(conn, uid):
    rader = rows_to_list(conn.execute(
        "SELECT * FROM rutt_importprofil WHERE agare=? ORDER BY uppdaterad DESC", (uid,)).fetchall())
    for p in rader:
        try:
            p['mappning'] = json.loads(p['mappning']) if p.get('mappning') else {}
        except (ValueError, TypeError):
            p['mappning'] = {}
    return rader


@app.get('/api/rutt/importprofiler')
def rutt_importprofiler():
    uid = _rutt_uid()
    if not uid:
        return jsonify({'profiler': []})
    with get_db() as conn:
        return jsonify({'profiler': _rutt_profiler(conn, uid)})


@app.post('/api/rutt/import/forhandsvisa')
def rutt_import_forhandsvisa():
    d = request.get_json(silent=True) or {}
    headers = d.get('headers') or []
    if not headers:
        return fel('Filen saknar kolumnrubriker.')
    uid = _rutt_uid()
    profiler = []
    if uid:
        with get_db() as conn:
            profiler = _rutt_profiler(conn, uid)
    mappning, profilnamn = gissa_mappning(headers, profiler)
    return jsonify({
        'mappning': mappning,
        'falt': [{'nyckel': k, 'etikett': e} for k, e in IMPORT_FALT],
        'headers': headers,
        'profil_namn': profilnamn,
    })


@app.post('/api/rutt/import/validera')
def rutt_import_validera():
    d = request.get_json(silent=True) or {}
    rader = d.get('rader') or []
    mappning = d.get('mappning') or {}
    if not isinstance(rader, list):
        return fel('Ogiltiga rader.')
    with get_db() as conn:
        typer = rows_to_list(conn.execute(
            "SELECT namn, servicetid_min FROM rutt_arendetyp").fetchall())
    return jsonify(validera_rader(rader, mappning, typer))


@app.post('/api/rutt/planeringar/<int:pid>/import/bekrafta')
def rutt_import_bekrafta(pid):
    uid = _rutt_uid()
    d = request.get_json(silent=True) or {}
    arenden = d.get('arenden') or []
    with get_db() as conn:
        p = conn.execute("SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)

        # Ersätt befintliga ärenden i planeringen (import = dagens ärenden)
        conn.execute("DELETE FROM rutt_arende WHERE planering_id=?", (pid,))
        infogade, hoppade = 0, []
        for a in arenden:
            if not a.get('inkludera', True):
                continue
            lat, lon = _num(a.get('lat')), _num(a.get('lon'))
            if lat is None or lon is None:
                hoppade.append({'etikett': a.get('etikett') or '?', 'orsak': 'saknar koordinat'})
                continue
            st = a.get('servicetid_min')
            try:
                st = int(st) if st not in (None, '') else None
            except (TypeError, ValueError):
                st = None
            conn.execute(
                "INSERT INTO rutt_arende "
                "(planering_id,etikett,lat,lon,arendetyp,servicetid_min,fonster_fran,fonster_till,"
                "kompetenskrav,anteckning,skapad) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, (a.get('etikett') or '').strip(), lat, lon,
                 (a.get('arendetyp') or '').strip() or None, st,
                 (a.get('fonster_fran') or None), (a.get('fonster_till') or None),
                 (a.get('kompetenskrav') or '').strip() or None,
                 (a.get('anteckning') or '').strip() or None, nu()))
            infogade += 1

        # Spara/uppdatera importprofil (per användare, per rubrik-signatur)
        headers = d.get('headers') or []
        mappning = d.get('mappning') or {}
        profilnamn = (d.get('profilnamn') or '').strip()
        if uid and headers and mappning and profilnamn:
            sig = rubrik_signatur(headers)
            bef = conn.execute(
                "SELECT id FROM rutt_importprofil WHERE agare=? AND rubrik_signatur=?",
                (uid, sig)).fetchone()
            if bef:
                conn.execute(
                    "UPDATE rutt_importprofil SET namn=?, mappning=?, uppdaterad=? WHERE id=?",
                    (profilnamn, json.dumps(mappning), nu(), bef['id']))
            else:
                conn.execute(
                    "INSERT INTO rutt_importprofil (agare,namn,rubrik_signatur,mappning,skapad,uppdaterad) "
                    "VALUES (?,?,?,?,?,?)",
                    (uid, profilnamn, sig, json.dumps(mappning), nu(), nu()))

        conn.execute("UPDATE rutt_planering SET uppdaterad=? WHERE id=?", (nu(), pid))
        conn.commit()
        arend = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=? ORDER BY id", (pid,)).fetchall())
    return jsonify({'infogade': infogade, 'hoppade': hoppade, 'arenden': arend})


# ---- Optimering ----
def _hhmm_min(s):
    try:
        h, m = str(s).split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _min_hhmm(m):
    if m is None:
        return None
    m = int(round(m))
    return f'{(m // 60) % 24:02d}:{m % 60:02d}'


def _komp_set(s):
    return set(k.strip().lower() for k in (s or '').replace(';', ',').split(',') if k.strip())


@app.post('/api/rutt/planeringar/<int:pid>/optimera')
def rutt_optimera(pid):
    uid = _rutt_uid()
    with get_db() as conn:
        p = conn.execute("SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)

        ar_rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=? AND lat IS NOT NULL AND lon IS NOT NULL",
            (pid,)).fetchall())
        if not ar_rader:
            return fel('Planeringen saknar ärenden med giltiga koordinater.')
        tek_rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_tekniker WHERE aktiv=1 AND start_lat IS NOT NULL AND start_lon IS NOT NULL").fetchall())
        if not tek_rader:
            return fel('Inga aktiva tekniker med depå-koordinater. Lägg till tekniker under Inställningar.')

        # Punktindex (avrundade koordinater delas mellan depåer och ärenden)
        punkter, index = [], {}

        def _pt(lat, lon):
            key = (round(lat, 5), round(lon, 5))
            if key not in index:
                index[key] = len(punkter)
                punkter.append((lat, lon))
            return index[key]

        for t in tek_rader:
            t['_dep_start'] = _pt(t['start_lat'], t['start_lon'])
            sl_lat = t['slut_lat'] if t['slut_lat'] is not None else t['start_lat']
            sl_lon = t['slut_lon'] if t['slut_lon'] is not None else t['start_lon']
            t['_dep_end'] = _pt(sl_lat, sl_lon)
        for a in ar_rader:
            a['_pt'] = _pt(a['lat'], a['lon'])

        dur, dist, kalla = bygg_matris(conn, punkter)

        tekniker = [{
            'id': t['id'], 'namn': t['namn'], 'skills': _komp_set(t['kompetenser']),
            'start_min': _hhmm_min(t['arbetstid_start']) or 420,
            'end_min': _hhmm_min(t['arbetstid_slut']) or 960,
            'dep_start': t['_dep_start'], 'dep_end': t['_dep_end'],
        } for t in tek_rader]
        arenden = [{
            'id': a['id'], 'pt': a['_pt'],
            'service': int(a['servicetid_min']) if a['servicetid_min'] is not None else 30,
            'wf': _hhmm_min(a['fonster_fran']), 'wt': _hhmm_min(a['fonster_till']),
            'krav': _komp_set(a['kompetenskrav']),
        } for a in ar_rader]

        res = kor_optimering(tekniker, arenden, dur)

        # Spara tilldelning
        ank = res['ankomster']
        ej_map = {e['id']: e['orsak'] for e in res['ej_placerade']}
        for tid, idlist in res['rutter'].items():
            for ordning, aid in enumerate(idlist):
                conn.execute(
                    "UPDATE rutt_arende SET tilldelad_tekniker=?, ordning=?, ankomst=?, ej_placerad_orsak=NULL WHERE id=?",
                    (tid, ordning, _min_hhmm(ank.get(aid)), aid))
        for aid, orsak in ej_map.items():
            conn.execute(
                "UPDATE rutt_arende SET tilldelad_tekniker=NULL, ordning=NULL, ankomst=NULL, ej_placerad_orsak=? WHERE id=?",
                (orsak, aid))
        conn.execute("UPDATE rutt_planering SET status='optimerad', uppdaterad=? WHERE id=?", (nu(), pid))
        conn.commit()

        # Sammanfattning per tekniker
        tek_by_id = {t['id']: t for t in tekniker}
        ar_by_id = {a['id']: a for a in arenden}
        sammanfattning = []
        for t in tek_rader:
            idlist = res['rutter'].get(t['id'], [])
            if not idlist:
                continue
            tk = tek_by_id[t['id']]
            drive = 0.0
            prev = tk['dep_start']
            for aid in idlist:
                drive += dur[prev][ar_by_id[aid]['pt']] / 60.0
                prev = ar_by_id[aid]['pt']
            drive += dur[prev][tk['dep_end']] / 60.0
            service = sum(ar_by_id[aid]['service'] for aid in idlist)
            sista = idlist[-1]
            slut = (ank.get(sista, 0) + ar_by_id[sista]['service']
                    + dur[ar_by_id[sista]['pt']][tk['dep_end']] / 60.0)
            sammanfattning.append({
                'tekniker_id': t['id'], 'namn': t['namn'], 'farg': t['farg'],
                'stopp': len(idlist), 'kortid_min': int(round(drive)),
                'servicetid_min': service, 'sluttid': _min_hhmm(slut),
            })

        arend = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=? "
            "ORDER BY COALESCE(tilldelad_tekniker,999999), COALESCE(ordning,999999), id",
            (pid,)).fetchall())

    return jsonify({
        'kalla': kalla,
        'sammanfattning': sammanfattning,
        'ej_placerade': [{'etikett': next((a['etikett'] for a in arend if a['id'] == e['id']), '?'),
                          'orsak': e['orsak']} for e in res['ej_placerade']],
        'arenden': arend,
    })


@app.post('/api/rutt/planeringar/<int:pid>/tilldelning')
def rutt_tilldelning(pid):
    """Manuell omfördelning (dra-och-släpp): räkna om tider utan full omoptimering."""
    uid = _rutt_uid()
    d = request.get_json(silent=True) or {}
    tilldelning = d.get('tilldelning') or {}
    ej_in = d.get('ej_placerade') or []
    with get_db() as conn:
        p = conn.execute("SELECT * FROM rutt_planering WHERE id=?", (pid,)).fetchone()
        if not p:
            return fel('Planeringen hittades inte.', 404)
        if p['agare'] != uid:
            return fel('Du har inte åtkomst till den här planeringen.', 403)

        ar_rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=?", (pid,)).fetchall())
        ar_map = {a['id']: a for a in ar_rader}
        tek_ids = [int(t) for t in tilldelning.keys()]
        tek_rader = rows_to_list(conn.execute(
            "SELECT * FROM rutt_tekniker WHERE id IN (%s)" % (','.join('?' * len(tek_ids)) or 'NULL'),
            tek_ids).fetchall()) if tek_ids else []
        tmap = {t['id']: t for t in tek_rader}

        # punktindex
        punkter, index = [], {}

        def _pt(lat, lon):
            key = (round(lat, 5), round(lon, 5))
            if key not in index:
                index[key] = len(punkter)
                punkter.append((lat, lon))
            return index[key]

        for t in tek_rader:
            t['_ds'] = _pt(t['start_lat'], t['start_lon'])
            sl_lat = t['slut_lat'] if t['slut_lat'] is not None else t['start_lat']
            sl_lon = t['slut_lon'] if t['slut_lon'] is not None else t['start_lon']
            t['_de'] = _pt(sl_lat, sl_lon)
        for a in ar_rader:
            if a['lat'] is not None and a['lon'] is not None:
                a['_pt'] = _pt(a['lat'], a['lon'])

        dur, _dist, _k = bygg_matris(conn, punkter, bara_cache=True)

        sena, over = [], []
        for tid_str, aidlist in tilldelning.items():
            tid = int(tid_str)
            t = tmap.get(tid)
            if not t:
                continue
            tek = {'dep_start': t['_ds'], 'dep_end': t['_de'],
                   'start_min': _hhmm_min(t['arbetstid_start']) or 420,
                   'end_min': _hhmm_min(t['arbetstid_slut']) or 960}
            seq = [{'id': aid, 'pt': ar_map[aid]['_pt'],
                    'service': ar_map[aid]['servicetid_min'] or 30,
                    'wf': _hhmm_min(ar_map[aid]['fonster_fran']),
                    'wt': _hhmm_min(ar_map[aid]['fonster_till'])}
                   for aid in aidlist if aid in ar_map and ar_map[aid].get('_pt') is not None]
            r = berakna_rutt(seq, tek, dur)
            for i, item in enumerate(seq):
                conn.execute(
                    "UPDATE rutt_arende SET tilldelad_tekniker=?, ordning=?, ankomst=?, ej_placerad_orsak=NULL WHERE id=?",
                    (tid, i, _min_hhmm(r['arrivals'][i]), item['id']))
            sena.extend(r['sena'])
            if r['over_arbetstid']:
                over.append(tid)

        for aid in ej_in:
            if aid in ar_map:
                conn.execute(
                    "UPDATE rutt_arende SET tilldelad_tekniker=NULL, ordning=NULL, ankomst=NULL, ej_placerad_orsak=? WHERE id=?",
                    ('Ej tilldelad', aid))

        conn.execute("UPDATE rutt_planering SET uppdaterad=? WHERE id=?", (nu(), pid))
        conn.commit()

        arenden = rows_to_list(conn.execute(
            "SELECT * FROM rutt_arende WHERE planering_id=? "
            "ORDER BY COALESCE(tilldelad_tekniker,999999), COALESCE(ordning,999999), id",
            (pid,)).fetchall())
        sammanfattning = _rutt_sammanfattning(conn, [dict(a) for a in arenden])
    return jsonify({'arenden': arenden, 'sammanfattning': sammanfattning,
                    'varningar': {'sena': sena, 'over_arbetstid': over}})


# ============================================================
# START
# ============================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"Lågspänningsberedningssystem startar på http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
