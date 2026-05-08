"""Beräkningslogik för de 4 byggprotokollsmallarna."""
import math
from seed_data import (
    STD_KABELSKYDDSNAAT, STD_MARKERINGSBAND, STD_KABELSAND,
    STD_BUNTBAND, STD_MARKBRICKA, STD_KABELSTRUMPA, STD_SKRUV_M8,
    STD_GENOMFORING_LITEN, STD_GENOMFORING_STOR, STD_BETONGFUNDAMENT,
    STD_JORDSKENOR, STD_OVERSPANNING, STD_KABELKLAMMOR, STD_JORDSKENEANSL
)


def berakna(mall_id, inputdata, conn):
    """
    Returnerar lista med beräknade materialrader för ett byggprotokoll.
    Varje rad: {artikel_id, artikelnamn, kategori, enhet, antal,
                leverantor_id, leverantor_namn, artikelnummer, a_pris,
                anteckning, manuell}
    """
    fns = {1: _mall1, 2: _mall2, 3: _mall3, 4: _mall4}
    fn = fns.get(int(mall_id))
    if not fn:
        return []
    rader = fn(inputdata, conn)
    # Lägg till leverantörspris på varje rad (välj billigaste tillgängliga)
    _berikas_med_pris(rader, conn)
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


def _berikas_med_pris(rader, conn):
    """Komplettera varje rad med billigaste leverantörspris."""
    for r in rader:
        if not r or not r.get('artikel_id'):
            continue
        leverantorer = conn.execute("""
            SELECT al.leverantor_id, l.namn AS leverantor_namn,
                   al.artikelnummer, al.a_pris
            FROM artikel_leverantor al
            JOIN leverantorer l ON l.id = al.leverantor_id
            WHERE al.artikel_id = ?
            ORDER BY al.a_pris ASC
        """, (r['artikel_id'],)).fetchall()
        if leverantorer:
            billigast = dict(leverantorer[0])
            r['leverantor_id']   = billigast['leverantor_id']
            r['leverantor_namn'] = billigast['leverantor_namn']
            r['artikelnummer']   = billigast['artikelnummer']
            r['a_pris']          = billigast['a_pris']


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

    kabel_m  = _inp_float(inp, 'kabel_meter')
    ror_m    = _inp_float(inp, 'ror_meter')
    n_ändar  = max(1, _inp_int(inp, 'antal_kabelander', 2))
    inkl_sand = _inp_bool(inp, 'inkl_kabelsand', True)
    inkl_mark = _inp_bool(inp, 'inkl_markeringsband', True)

    # Markkabel
    kabel = _hämta_id(conn, inp.get('kabel_artikel_id'))
    if kabel and kabel_m > 0:
        rader.append(_rad(kabel, kabel_m, 'Markkabel'))

    # Skyddsrör
    ror = _hämta_id(conn, inp.get('ror_artikel_id'))
    if ror and ror_m > 0:
        rader.append(_rad(ror, ror_m, 'Skyddsrör'))

    # Rörkopplingar (1 per 6 m rör)
    koppling = _hämta_id(conn, inp.get('ror_koppling_artikel_id'))
    if koppling and ror_m > 0:
        n_kopp = math.ceil(ror_m / 6)
        rader.append(_rad(koppling, n_kopp, f'1 per 6m rör ≈ {n_kopp} st'))

    # Kabelskyddsnät (m = kabellängd)
    if kabel_m > 0:
        art = _hämta(conn, STD_KABELSKYDDSNAAT)
        rader.append(_rad(art, kabel_m, 'Täcker hela kabellängden'))

    # Markeringsband
    if inkl_mark and kabel_m > 0:
        art = _hämta(conn, STD_MARKERINGSBAND)
        rader.append(_rad(art, kabel_m, 'Läggs ovanpå kabelskyddsnätet'))

    # Kabelsand (ca 1 ton per 100 m schakt)
    if inkl_sand and kabel_m > 0:
        art = _hämta(conn, STD_KABELSAND)
        ton = math.ceil(kabel_m / 100)
        rader.append(_rad(art, ton, f'≈ 1 ton per 100m ({kabel_m}m)'))

    # Buntband (1 förp per 50 m + 1 extra)
    if kabel_m > 0:
        art = _hämta(conn, STD_BUNTBAND)
        förp = math.ceil(kabel_m / 50) + 1
        rader.append(_rad(art, förp))

    # Märkbrickor (2 per kabelände – L1/L2/L3/N på varje ände)
    art = _hämta(conn, STD_MARKBRICKA)
    rader.append(_rad(art, n_ändar, f'{n_ändar} ändar × 1 förp'))

    # Kabelförband ände
    förband = _hämta_id(conn, inp.get('kabelforband_artikel_id'))
    if förband:
        rader.append(_rad(förband, n_ändar, f'1 per ände'))

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
        rader.append(_rad(sakring, n_kablar, f'{n_kablar} inkommande kabel/kablar'))

    # Kabelskor (4 per kabel: L1 + L2 + L3 + N)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, n_kablar * 4, f'{n_kablar} × 4 (3L + N)'))

    # Kabelstrumpa/kabelgel
    art = _hämta(conn, STD_KABELSTRUMPA)
    rader.append(_rad(art, n_kablar))

    # Märkbrickor
    art = _hämta(conn, STD_MARKBRICKA)
    rader.append(_rad(art, n_kablar, f'{n_kablar} kabel/kablar'))

    # Skruv/mutter
    art = _hämta(conn, STD_SKRUV_M8)
    rader.append(_rad(art, n_kablar))

    # Buntband/kabelband
    art = _hämta(conn, STD_BUNTBAND)
    rader.append(_rad(art, 1))

    # Kabelgenomföring
    art = _hämta(conn, STD_GENOMFORING_LITEN)
    rader.append(_rad(art, n_kablar, 'En per kabel'))

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

    # Betongfundament
    art = _hämta(conn, STD_BETONGFUNDAMENT)
    rader.append(_rad(art, 1))

    # Säkringslastfrånskiljare (1 per fack)
    sakring = _hämta_id(conn, inp.get('sakring_artikel_id'))
    if sakring:
        rader.append(_rad(sakring, n_fack, f'{n_fack} fack'))

    # Kabelskor (4 per fack)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, n_fack * 4, f'{n_fack} × 4 (3L + N)'))

    # Jordskenor
    art = _hämta(conn, STD_JORDSKENOR)
    rader.append(_rad(art, 1))

    # Kabelgenomföringar (2 per fack: in + ut)
    art = _hämta(conn, STD_GENOMFORING_STOR)
    rader.append(_rad(art, n_fack * 2, f'{n_fack} fack × 2'))

    # Märkbrickor
    art = _hämta(conn, STD_MARKBRICKA)
    rader.append(_rad(art, n_fack, 'Märkning per fack'))

    # Skruv/mutter
    art = _hämta(conn, STD_SKRUV_M8)
    rader.append(_rad(art, n_fack))

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
    kabel_m       = _inp_float(inp, 'kabel_meter')
    n_genomforingar = max(1, _inp_int(inp, 'antal_genomforingar', 1))

    # Kabel
    kabel = _hämta_id(conn, inp.get('kabel_artikel_id'))
    if kabel and kabel_m > 0:
        rader.append(_rad(kabel, kabel_m, 'Inne i stationen'))

    # Kabelskor (4 st: L1 + L2 + L3 + N)
    kabelskor = _hämta_id(conn, inp.get('kabelskor_artikel_id'))
    if kabelskor:
        rader.append(_rad(kabelskor, 4, '3L + N'))

    # Kabelklämmor (1 per 0,5 m)
    if kabel_m > 0:
        art  = _hämta(conn, STD_KABELKLAMMOR)
        n_kl = math.ceil(kabel_m / 0.5)
        rader.append(_rad(art, n_kl, f'1 per 0,5m ({kabel_m}m)'))

    # Märkbrickor
    art = _hämta(conn, STD_MARKBRICKA)
    rader.append(_rad(art, 1, 'L1/L2/L3/N'))

    # Skruv och förband
    art = _hämta(conn, STD_SKRUV_M8)
    rader.append(_rad(art, 1))

    # Kabelgenomföring (vägg)
    art = _hämta(conn, STD_GENOMFORING_STOR)
    rader.append(_rad(art, n_genomforingar))

    # Jordskeneanslutning
    art = _hämta(conn, STD_JORDSKENEANSL)
    rader.append(_rad(art, 1))

    return rader
