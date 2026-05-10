import os, hashlib, json
from functools import wraps
from flask import Flask, jsonify, request, session, send_from_directory, Response
from database import get_db, init_db, DB_PATH
from models import rows_to_list, row_to_dict, nu, nasta_projektnummer
from mall_berakning import berakna

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__,
            static_folder=os.path.join(FRONTEND_DIR, 'static'),
            static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'lagspanning-dev-key-byt-i-prod')
app.config['JSON_AS_ASCII'] = False


# ============================================================
# HJÄLP
# ============================================================

def fel(msg, kod=400):
    return jsonify({'fel': msg}), kod


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def admin_required(f):
    @wraps(f)
    def inner(*a, **kw):
        if not session.get('admin'):
            return fel('Administratörsinloggning krävs.', 401)
        return f(*a, **kw)
    return inner


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
    d = request.get_json(silent=True) or {}
    pw = (d.get('losenord') or '').strip()
    with get_db() as conn:
        rad = conn.execute("SELECT varde FROM installningar WHERE nyckel='admin_losenord'").fetchone()
    if rad and rad['varde'] == hash_pw(pw):
        session['admin'] = True
        return jsonify({'ok': True})
    return fel('Fel lösenord.', 401)


@app.post('/api/admin/logout')
def admin_logout():
    session.pop('admin', None)
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
    sok      = request.args.get('sok', '').strip()
    sql = "SELECT * FROM projekt WHERE 1=1"
    params = []
    if status:   sql += " AND status=?";   params.append(status)
    if beredare: sql += " AND beredare=?"; params.append(beredare)
    if sok:
        sql += " AND (projektnummer LIKE ? OR projektnamn LIKE ? OR beredare LIKE ?)"
        params += [f'%{sok}%'] * 3
    sql += " ORDER BY skapad DESC"
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


@app.post('/api/projekt')
def skapa_projekt():
    d = request.get_json(silent=True) or {}
    namn     = (d.get('projektnamn') or '').strip()
    beredare = (d.get('beredare') or '').strip()
    if not namn:     return fel('Projektnamn är obligatoriskt.')
    if not beredare: return fel('Beredare är obligatoriskt.')
    tidpunkt = nu()
    with get_db() as conn:
        pnr = d.get('projektnummer') or nasta_projektnummer(conn)
        try:
            cur = conn.execute(
                "INSERT INTO projekt (projektnummer,projektnamn,beredare,status,startdatum,anteckningar,skapad,uppdaterad)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (pnr, namn, beredare, d.get('status', 'Planerat'),
                 d.get('startdatum') or None,
                 (d.get('anteckningar') or '').strip() or None,
                 tidpunkt, tidpunkt))
            conn.commit()
            return jsonify({'projekt': row_to_dict(conn.execute("SELECT * FROM projekt WHERE id=?", (cur.lastrowid,)).fetchone())}), 201
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
        conn.execute(
            "UPDATE projekt SET projektnamn=?,beredare=?,status=?,startdatum=?,anteckningar=?,uppdaterad=? WHERE id=?",
            (namn, d.get('beredare', bef['beredare']), status,
             d.get('startdatum', bef['startdatum']) or None,
             d.get('anteckningar', bef['anteckningar']), nu(), pid))
        conn.commit()
        return jsonify({'projekt': row_to_dict(conn.execute("SELECT * FROM projekt WHERE id=?", (pid,)).fetchone())})


@app.delete('/api/projekt/<int:pid>')
def ta_bort_projekt(pid):
    with get_db() as conn:
        rad = conn.execute("SELECT projektnummer FROM projekt WHERE id=?", (pid,)).fetchone()
        if not rad: return fel('Projektet hittades inte.', 404)
        conn.execute("DELETE FROM projekt WHERE id=?", (pid,))
        conn.commit()
    return jsonify({'meddelande': f'Projekt {rad["projektnummer"]} borttaget.'})


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
    pdf = skapa_materiallista_pdf(row_to_dict(projekt), protokoll_lista, inst)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition':
                             f'attachment; filename="{projekt["projektnummer"]}_materiallista.pdf"'})


# ============================================================
# ADMIN – Artiklar CRUD
# ============================================================

@app.post('/api/admin/artiklar')
@admin_required
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
@admin_required
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
@admin_required
def admin_ta_bort_artikel(aid):
    with get_db() as conn:
        conn.execute("DELETE FROM artiklar WHERE id=?", (aid,))
        conn.commit()
    return jsonify({'meddelande': 'Artikel borttagen.'})


# ============================================================
# ADMIN – Priser (artikel_leverantor)
# ============================================================

@app.get('/api/admin/artiklar/<int:aid>/priser')
@admin_required
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
@admin_required
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
@admin_required
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
# START
# ============================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"Lågspänningsberedningssystem startar på http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
