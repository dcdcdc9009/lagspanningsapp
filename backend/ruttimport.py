"""Import för ruttplanering: gissa kolumnmappning + validera rader.

Parsningen av själva filen sker klient-sida (SheetJS); hit kommer redan
uppradade rader (lista av dictar nyckel=rubrik). All mappning, validering
och koordinattransform görs här server-side så skräpdata aldrig går in.
"""
import re
from ruttgeo import normalisera_koordinat

# Målfält som ärenden mappas till
IMPORT_FALT = [
    ('etikett',        'Ärendenummer / etikett'),
    ('lat',            'Latitud / N'),
    ('lon',            'Longitud / E'),
    ('arendetyp',      'Ärendetyp'),
    ('servicetid_min', 'Servicetid (min)'),
    ('fonster_fran',   'Tidsfönster från'),
    ('fonster_till',   'Tidsfönster till'),
    ('kompetenskrav',  'Kompetenskrav'),
    ('anteckning',     'Anteckning'),
]

# Alias per fält (normaliserade). Alias <= 2 tecken matchas endast exakt.
_ALIAS = {
    'etikett':        ['arendenummer', 'arendenr', 'arende', 'ordernummer', 'order',
                       'arbetsorder', 'ibnr', 'ib', 'nummer', 'etikett', 'referens', 'ref', 'id'],
    'lat':            ['latitud', 'lat', 'wgs84lat', 'northing', 'north', 'nord', 'n', 'y'],
    'lon':            ['longitud', 'long', 'lng', 'lon', 'easting', 'east', 'ost', 'oost', 'x', 'e', 'o'],
    'arendetyp':      ['arendetyp', 'typ', 'kategori', 'tjanst', 'jobbtyp', 'arbetstyp'],
    'servicetid_min': ['servicetid', 'servicetidmin', 'tidsatgang', 'duration', 'minuter', 'min'],
    'fonster_fran':   ['tidigast', 'fonsterfran', 'oppnar', 'tidfran', 'fran', 'start'],
    'fonster_till':   ['senast', 'fonstertill', 'stanger', 'tidtill', 'till', 'slut'],
    'kompetenskrav':  ['kompetenskrav', 'kompetens', 'krav', 'behorighet', 'skill'],
    'anteckning':     ['anteckning', 'notering', 'notat', 'kommentar', 'info', 'beskrivning', 'adress', 'address', 'meddelande'],
}


def _norm(s):
    """Normalisera rubrik: gemener, å/ä/ö -> a/a/o, ta bort allt utom a-z0-9."""
    s = str(s or '').lower()
    s = s.translate(str.maketrans('åäöéèüø', 'aaoeeuo'))
    return re.sub(r'[^a-z0-9]', '', s)


def rubrik_signatur(headers):
    """Stabil signatur av rubrikuppsättningen (för att känna igen sparade profiler)."""
    return '|'.join(sorted(_norm(h) for h in headers if str(h).strip()))


def gissa_mappning(headers, profiler=None):
    """Returnera {falt: rubrik} – gissad mappning. Matchar sparad profil först."""
    sig = rubrik_signatur(headers)
    for p in (profiler or []):
        if p.get('rubrik_signatur') and p['rubrik_signatur'] == sig:
            mapp = p.get('mappning') or {}
            # behåll bara rubriker som finns i den här filen
            return {f: (h if h in headers else None) for f, h in mapp.items()}, p.get('namn')

    nheaders = {h: _norm(h) for h in headers}
    poang = []  # (score, falt, header)
    for falt, alias in _ALIAS.items():
        for h, nh in nheaders.items():
            if not nh:
                continue
            best = 0
            for a in alias:
                if len(a) <= 2:
                    if nh == a:
                        best = max(best, 60)
                else:
                    if nh == a:
                        best = max(best, 100 + len(a))
                    elif a in nh or nh in a:
                        best = max(best, 50 + len(a))
            if best:
                poang.append((best, falt, h))
    poang.sort(reverse=True)
    mappning = {f: None for f, _ in IMPORT_FALT}
    tagna_headers = set()
    for score, falt, h in poang:
        if mappning[falt] is None and h not in tagna_headers:
            mappning[falt] = h
            tagna_headers.add(h)
    return mappning, None


def _parse_tid(v):
    """(normaliserad 'HH:MM' eller None, hade_innehall)."""
    if v is None:
        return None, False
    s = str(v).strip()
    if s == '':
        return None, False
    # Excel-tid som fraktion av dygn (0–1)
    try:
        f = float(s.replace(',', '.'))
        if 0 <= f < 1:
            mins = round(f * 24 * 60)
            return f'{mins // 60:02d}:{mins % 60:02d}', True
        if f == 1:
            return '24:00', True
    except ValueError:
        pass
    m = re.match(r'^(\d{1,2})[:\.\,](\d{2})', s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            return f'{h:02d}:{mi:02d}', True
    return None, True  # hade innehåll men gick ej att tolka


def _hamta(row, mappning, falt):
    h = mappning.get(falt)
    if not h:
        return ''
    return str(row.get(h, '') or '').strip()


def validera_rader(rader, mappning, arendetyper=None, default_servicetid=30):
    """Validera + transformera rader enligt mappning.

    arendetyper: lista [{namn, servicetid_min}] för default-servicetid per typ.
    Returnerar {rader: [...], sammanfattning: {...}}.
    """
    typ_servicetid = {(_norm(t['namn'])): t['servicetid_min'] for t in (arendetyper or [])}
    ut = []
    n_ok = n_saknar = n_fonster = n_sweref = 0

    for i, row in enumerate(rader):
        meddelanden = []
        etikett = _hamta(row, mappning, 'etikett') or f'Rad {i + 1}'
        if not _hamta(row, mappning, 'etikett'):
            meddelanden.append('Saknar ärendenummer – genererat')

        lat, lon, kalla = normalisera_koordinat(
            _hamta(row, mappning, 'lat'), _hamta(row, mappning, 'lon'))
        if kalla == 'sweref99tm':
            n_sweref += 1
        koord_ok = lat is not None

        arendetyp = _hamta(row, mappning, 'arendetyp')
        # servicetid: explicit -> typens default -> globalt default
        st_raw = _hamta(row, mappning, 'servicetid_min')
        servicetid = None
        if st_raw:
            try:
                servicetid = int(float(st_raw.replace(',', '.')))
            except ValueError:
                meddelanden.append('Ogiltig servicetid – använder default')
        if servicetid is None and arendetyp and _norm(arendetyp) in typ_servicetid:
            servicetid = typ_servicetid[_norm(arendetyp)]
        if servicetid is None:
            servicetid = default_servicetid

        fr_val, fr_har = _parse_tid(_hamta(row, mappning, 'fonster_fran'))
        ti_val, ti_har = _parse_tid(_hamta(row, mappning, 'fonster_till'))
        fonster_fel = False
        if (fr_har and fr_val is None) or (ti_har and ti_val is None):
            fonster_fel = True
            meddelanden.append('Ogiltigt tidsfönster (format)')
        elif fr_val and ti_val and fr_val >= ti_val:
            fonster_fel = True
            meddelanden.append('Tidsfönster: från är inte före till')

        if not koord_ok:
            status = 'fel'
            meddelanden.insert(0, {'saknas': 'Saknar koordinat',
                                   'ogiltig': 'Ogiltig koordinat',
                                   'utanfor_omrade': 'Koordinat utanför Sverige'}.get(kalla, 'Saknar koordinat'))
            n_saknar += 1
        elif fonster_fel:
            status = 'varning'
            n_fonster += 1
        else:
            status = 'ok'
            n_ok += 1

        ut.append({
            'radnr': i + 1,
            'etikett': etikett,
            'lat': round(lat, 6) if lat is not None else None,
            'lon': round(lon, 6) if lon is not None else None,
            'koord_kalla': kalla,
            'arendetyp': arendetyp,
            'servicetid_min': servicetid,
            'fonster_fran': fr_val if not fonster_fel else None,
            'fonster_till': ti_val if not fonster_fel else None,
            'kompetenskrav': _hamta(row, mappning, 'kompetenskrav'),
            'anteckning': _hamta(row, mappning, 'anteckning'),
            'status': status,
            'meddelanden': meddelanden,
            'inkludera': status != 'fel',
        })

    return {
        'rader': ut,
        'sammanfattning': {
            'totalt': len(rader),
            'ok': n_ok,
            'saknar_koordinat': n_saknar,
            'tidsfonster_fel': n_fonster,
            'sweref_antal': n_sweref,
        },
    }
