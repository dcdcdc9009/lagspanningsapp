"""Beräkningslogik för de 4 byggprotokollsmallarna."""
from seed_data import STD_OVERSPANNING


def berakna(mall_id, inputdata, conn):
    """
    Returnerar lista med beräknade materialrader för ett byggprotokoll.
    Varje rad: {artikel_id, artikelnamn, kategori, enhet, antal,
                leverantor_id, leverantor_namn, artikelnummer, a_pris,
                anteckning, manuell}
    Endast material som användaren explicit valt tas med.
    """
    fns = {1: _mall1, 2: _mall2, 3: _mall3, 4: _mall4}
    fn = fns.get(int(mall_id))
    if not fn:
        return []
    rader = fn(inputdata, conn)
    return [r for r in rader if r]


# ----------------------------------------------------------------
# HJÄLPFUNKTIONER
# ----------------------------------------------------------------

def _hämta(conn, namn):
    """Hämta artikel ur DB via exakt namn."""
    r = conn.execute("""
        SELECT a.id, a.artikelnamn, a.enhet, k.namn AS kategori
        FROM artiklar a
        JOIN kategorier k ON k.id = a.kategori_id
        WHERE a.artikelnamn = ? AND a.aktiv = 1
    """, (namn,)).fetchone()
    return dict(r) if r else None


def _hämta_id(conn, artikel_id):
    """Hämta artikel ur DB via ID."""
    if not artikel_id:
        return None
    r = conn.execute("""
        SELECT a.id, a.artikelnamn, a.enhet, k.namn AS kategori
        FROM artiklar a
        JOIN kategorier k ON k.id = a.kategori_id
        WHERE a.id = ? AND a.aktiv = 1
    """, (int(artikel_id),)).fetchone()
    return dict(r) if r else None


def _rad(art, antal, anteckning=''):
    if not art or antal <= 0:
        return None
    return {
        'artikel_id':      art['id'],
        'artikelnamn':     art['artikelnamn'],
        'kategori':        art.get('kategori', ''),
        'enhet':           art['enhet'],
        'antal':           round(antal, 3),
        'leverantor_id':   None,
        'leverantor_namn': None,
        'artikelnummer':   None,
        'a_pris':          None,
        'anteckning':      anteckning,
        'manuell':         0,
    }


def _inp_int(inp, nyckel, default=0):
    try:
        return max(0, int(float(inp.get(nyckel) or default)))
    except (TypeError, ValueError):
        return default


def _inp_float(inp, nyckel, default=0.0):
    try:
        return max(0.0, float(inp.get(nyckel) or default))
    except (TypeError, ValueError):
        return default


def _inp_bool(inp, nyckel, default=True):
    val = inp.get(nyckel, default)
    return val not in (False, 'false', '0', 0, 'False')


# ----------------------------------------------------------------
# MALL 1 – KABELFÖRLÄGGNING
# ----------------------------------------------------------------

def _mall1(inp, conn):
    rader = []
    kabel_m = _inp_float(inp, 'kabel_meter')
    ror_m   = _inp_float(inp, 'ror_meter')

    # Markkabel
    kabel = _hämta_id(conn, inp.get('kabel_artikel_id'))
    if kabel and kabel_m > 0:
        rader.append(_rad(kabel, kabel_m, 'Markkabel'))

    # Skyddsrör
    ror = _hämta_id(conn, inp.get('ror_artikel_id'))
    if ror and ror_m > 0:
        rader.append(_rad(ror, ror_m, 'Skyddsrör'))

    # Kabelskyddsband
    forband = _hämta_id(conn, inp.get('kabelforband_artikel_id'))
    forband_m = _inp_float(inp, 'kabelforband_meter')
    if forband and forband_m > 0:
        rader.append(_rad(forband, forband_m, 'Kabelskyddsband'))

    return rader


# ----------------------------------------------------------------
# MALL 2 – ANSLUTNING I KABELSKÅP
# ----------------------------------------------------------------

def _mall2(inp, conn):
    rader = []
    n_kablar = max(1, _inp_int(inp, 'antal_kablar', 1))

    # Säkringslastfrånskiljare
    sakring = _hämta_id(conn, inp.get('sakring_artikel_id'))
    if sakring:
        rader.append(_rad(sakring, n_kablar))

    # Kabelskor (4 per kabel: L1 + L2 + L3 + N)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, n_kablar * 4, f'{n_kablar} x 4 (3L + N)'))

    return rader


# ----------------------------------------------------------------
# MALL 3 – NYTT KABELSKÅP
# ----------------------------------------------------------------

def _mall3(inp, conn):
    rader = []
    n_fack = max(1, _inp_int(inp, 'antal_sakringsfack', 1))
    inkl_overspanning = _inp_bool(inp, 'inkl_overspanningsskydd', False)

    # Kabelskåp
    skap = _hämta_id(conn, inp.get('kabelskap_artikel_id'))
    if skap:
        rader.append(_rad(skap, 1))

    # Säkringslastfrånskiljare (1 per fack)
    sakring = _hämta_id(conn, inp.get('sakring_artikel_id'))
    if sakring:
        rader.append(_rad(sakring, n_fack, f'{n_fack} fack'))

    # Kabelskor (4 per fack: L1 + L2 + L3 + N)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, n_fack * 4, f'{n_fack} x 4 (3L + N)'))

    # Överspänningsskydd (tillval)
    if inkl_overspanning:
        art = _hämta(conn, STD_OVERSPANNING)
        rader.append(_rad(art, 1, 'Tillval'))

    return rader


# ----------------------------------------------------------------
# MALL 4 – ANSLUTNING I NÄTSTATION
# ----------------------------------------------------------------

def _mall4(inp, conn):
    rader = []
    kabel_m        = _inp_float(inp, 'kabel_meter')
    n_genomforingar = max(1, _inp_int(inp, 'antal_genomforingar', 1))

    # Kabel
    kabel = _hämta_id(conn, inp.get('kabel_artikel_id'))
    if kabel and kabel_m > 0:
        rader.append(_rad(kabel, kabel_m, 'Inne i stationen'))

    # Kabelskor (4 st: L1 + L2 + L3 + N)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, 4, '3L + N'))

    # Kabelgenomföring (vägg) – direkt från användarens val
    from seed_data import STD_GENOMFORING_STOR
    art = _hämta(conn, STD_GENOMFORING_STOR)
    if art:
        rader.append(_rad(art, n_genomforingar))

    return rader
