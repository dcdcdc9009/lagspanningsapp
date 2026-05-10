"""Fyller databasen med startdata vid första uppstart."""
import hashlib


# Exakta namn för standardartiklar som mallberäkning letar upp
STD_KABELSKYDDSNAAT  = 'Kabelskyddsnät röd'
STD_MARKERINGSBAND   = 'Markeringsband gul/svart'
STD_KABELSAND        = 'Kabelsand'
STD_BUNTBAND         = 'Buntband svart (förp 100st)'
STD_MARKBRICKA       = 'Märkbricka plast (förp 100st)'
STD_KABELSTRUMPA     = 'Kabelstrumpa/kabelgel'
STD_SKRUV_M8         = 'Skruv och mutter sats M8'
STD_GENOMFORING_LITEN = 'Kabelgenomföring liten'
STD_GENOMFORING_STOR  = 'Kabelgenomföring stor'
STD_BETONGFUNDAMENT  = 'Betongfundament kabelskåp'
STD_JORDSKENOR       = 'Jordskenor 60A'
STD_OVERSPANNING     = 'Överspänningsskydd lågspänning'
STD_KABELKLAMMOR     = 'Kabelklämmor (förp 10st)'
STD_JORDSKENEANSL    = 'Jordskeneanslutning'


def _kat(conn, namn, sortering):
    conn.execute("INSERT OR IGNORE INTO kategorier (namn, sortering) VALUES (?,?)", (namn, sortering))
    return conn.execute("SELECT id FROM kategorier WHERE namn=?", (namn,)).fetchone()['id']


def _lev(conn, namn):
    conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES (?)", (namn,))
    return conn.execute("SELECT id FROM leverantorer WHERE namn=?", (namn,)).fetchone()['id']


def _art(conn, namn, kat_id, enhet, sort=0):
    existing = conn.execute(
        "SELECT id FROM artiklar WHERE artikelnamn=? AND kategori_id=?", (namn, kat_id)
    ).fetchone()
    if existing:
        return existing['id']
    cur = conn.execute(
        "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering) VALUES (?,?,?,?)",
        (namn, kat_id, enhet, sort))
    return cur.lastrowid


def fyll_i_startdata(conn):
    # ----------------------------------------------------------------
    # Kategorier
    # ----------------------------------------------------------------
    kat_kabel  = _kat(conn, 'Markkablar (0,4–1 kV)',              1)
    kat_skap   = _kat(conn, 'Kabelskåp och fördelningsskåp',           2)
    kat_sak    = _kat(conn, 'Säkringslastfrånskiljare',                3)
    kat_sko    = _kat(conn, 'Kabelskor och anslutningsmaterial',        4)
    kat_ror    = _kat(conn, 'Rör och skyddsrör',                       5)
    kat_forb   = _kat(conn, 'Kabelförband och muffar',                 6)
    kat_ovrigt = _kat(conn, 'Övrigt smågods',                          7)

    # ----------------------------------------------------------------
    # Leverantörer (inga priser – läggs till manuellt vid behov)
    # ----------------------------------------------------------------
    _lev(conn, 'Onninen')
    _lev(conn, 'Ahlsell')

    # ================================================================
    # MARKKABLAR (0,4–1 kV)
    # ================================================================
    axkj4_namn = [
        'AXKJ 4x16mm²', 'AXKJ 4x25mm²', 'AXKJ 4x35mm²', 'AXKJ 4x50mm²',
        'AXKJ 4x70mm²', 'AXKJ 4x95mm²', 'AXKJ 4x120mm²', 'AXKJ 4x150mm²',
        'AXKJ 4x185mm²', 'AXKJ 4x240mm²',
    ]
    for i, namn in enumerate(axkj4_namn):
        _art(conn, namn, kat_kabel, 'm', i)

    axkj1_namn = [
        'AXKJ 1x95mm²', 'AXKJ 1x120mm²', 'AXKJ 1x150mm²', 'AXKJ 1x185mm²', 'AXKJ 1x240mm²',
    ]
    for i, namn in enumerate(axkj1_namn):
        _art(conn, namn, kat_kabel, 'm', 20 + i)

    for i, namn in enumerate(['EKKJ 4x25mm²', 'EKKJ 4x50mm²', 'EKKJ 4x95mm²']):
        _art(conn, namn, kat_kabel, 'm', 30 + i)

    for i, namn in enumerate(['FKKJ 4x35mm²', 'FKKJ 4x70mm²', 'FKKJ 4x150mm²', 'FKKJ 4x240mm²']):
        _art(conn, namn, kat_kabel, 'm', 40 + i)

    for i, namn in enumerate(['AKKJ 4x25mm²', 'AKKJ 4x70mm²', 'AKKJ 4x120mm²']):
        _art(conn, namn, kat_kabel, 'm', 50 + i)

    # AML-kablar (från Excel-underlag)
    for i, namn in enumerate([
        'AML 4G25mm² 1kV', 'AML 4G50mm² 1kV', 'AML 4G95mm² 1kV',
        'AML 4G150mm² 1kV', 'AML 4G240mm² 1kV',
    ]):
        _art(conn, namn, kat_kabel, 'm', 60 + i)

    # ================================================================
    # KABELSKÅP OCH FÖRDELNINGSSKÅP
    # ================================================================
    skap_namn = [
        'Siemens 8GK 4-fack', 'Siemens 8GK 6-fack',
    ]
    for i, namn in enumerate(skap_namn):
        _art(conn, namn, kat_skap, 'st', i)

    # Kapslingar CDC (kopplingsdosor för kabelskåp-nät)
    for i, namn in enumerate(['Kapsling CDC 420 K2', 'Kapsling CDC 440 K3', 'Kapsling CDC 460 K4']):
        _art(conn, namn, kat_skap, 'st', 30 + i)

    # ================================================================
    # SÄKRINGSLASTFRÅNSKILJARE
    # ================================================================
    sak_namn = [
        'ABB Säkringslastfrånskiljare 63A', 'ABB Säkringslastfrånskiljare 100A',
        'ABB Säkringslastfrånskiljare 160A', 'ABB Säkringslastfrånskiljare 250A',
        'ABB Säkringslastfrånskiljare 400A',
        'Siemens Säkr.lastfrånskiljare 63A', 'Siemens Säkr.lastfrånskiljare 160A',
        'Schneider Säkr.lastfrånskiljare 63A', 'Schneider Säkr.lastfrånskiljare 160A',
    ]
    for i, namn in enumerate(sak_namn):
        _art(conn, namn, kat_sak, 'st', i)

    # Specifika modeller från Excel
    for i, namn in enumerate([
        'Säkringslastfrånskiljare SLF160P', 'Säkringslastfrånskiljare SLF250P',
        'Säkringslastfrånskiljare SLF400P', 'Säkringslastfrånskiljare SLF630P',
        'Säkringslastfrånskiljare SLD 00/000 500V', 'Säkringslastfrånskiljare SLE 1/2 690V',
    ]):
        _art(conn, namn, kat_sak, 'st', 20 + i)

    # NH-säkringar (standard)
    nh_namn = [
        'NH-säkring 00 63A', 'NH-säkring 00 100A', 'NH-säkring 00 160A',
        'NH-säkring 1 200A', 'NH-säkring 2 315A', 'NH-säkring 3 400A',
        'Handtag säkr.lastfrånskiljare', 'Täcklock/blindlock fack',
    ]
    for i, namn in enumerate(nh_namn):
        _art(conn, namn, kat_sak, 'st', 40 + i)

    # Knivsäkringar ECO HICAP (från Excel)
    kniv_namn = [
        'Knivsäkring ECO HICAP 000/10A', 'Knivsäkring ECO HICAP 000/16A',
        'Knivsäkring ECO HICAP 000/25A', 'Knivsäkring ECO HICAP 000/35A',
        'Knivsäkring ECO HICAP 000/50A', 'Knivsäkring ECO HICAP 000/63A',
        'Knivsäkring ECO HICAP 000/80A', 'Knivsäkring ECO HICAP 000/100A',
        'Knivsäkring ECO HICAP 00/125A', 'Knivsäkring ECO HICAP 00/160A',
        'Knivsäkring ECO HICAP 1/63A',  'Knivsäkring ECO HICAP 1/80A',
        'Knivsäkring ECO HICAP 1/100A', 'Knivsäkring ECO HICAP 1/125A',
        'Knivsäkring ECO HICAP 1/160A', 'Knivsäkring ECO HICAP 1/200A',
        'Knivsäkring ECO HICAP 1/224A', 'Knivsäkring ECO HICAP 1/250A',
        'Knivsäkring ECO HICAP 2/100A', 'Knivsäkring ECO HICAP 2/125A',
        'Knivsäkring ECO HICAP 2/160A', 'Knivsäkring ECO HICAP 2/200A',
        'Knivsäkring ECO HICAP 2/224A', 'Knivsäkring ECO HICAP 2/250A',
        'Knivsäkring ECO HICAP 2/315A', 'Knivsäkring ECO HICAP 2/355A',
    ]
    for i, namn in enumerate(kniv_namn):
        _art(conn, namn, kat_sak, 'st', 60 + i)

    # ================================================================
    # KABELSKOR OCH ANSLUTNINGSMATERIAL
    # ================================================================
    sko_dims = ['16mm²', '25mm²', '35mm²', '50mm²', '70mm²',
                '95mm²', '120mm²', '150mm²', '185mm²', '240mm²']
    for i, dim in enumerate(sko_dims):
        _art(conn, f'Kabelsko presssko {dim} (Klauke)', kat_sko, 'st', i)

    _art(conn, STD_KABELSTRUMPA,         kat_sko, 'st', 20)
    _art(conn, 'Jordskenor 60A',         kat_sko, 'st', 21)
    _art(conn, 'Jordskenor 160A',        kat_sko, 'st', 22)
    _art(conn, 'Jordklämma 16-35mm²',    kat_sko, 'st', 23)
    _art(conn, 'Kopplingsskena 63A',     kat_sko, 'st', 24)
    _art(conn, 'Kopplingsskena 160A',    kat_sko, 'st', 25)
    _art(conn, 'Kopplingsskena 250A',    kat_sko, 'st', 26)
    _art(conn, STD_SKRUV_M8,             kat_sko, 'sats', 27)
    _art(conn, 'Skruv och mutter sats M10', kat_sko, 'sats', 28)
    _art(conn, 'Skruv och mutter sats M12', kat_sko, 'sats', 29)

    # Anslutningsdon (från Excel)
    for i, (namn, enhet) in enumerate([
        ('Anslutningsdon ABB ADI 95',    'st'),
        ('Anslutningsdon ABB ADI 300',   'st'),
        ('Anslutningsdon ABB ADU 95',    'st'),
        ('Anslutningsdon ABB ADU 300',   'st'),
        ('Anslutningsdon PEN/PE CUZ 95', 'st'),
        ('Anslutningsdon PEN/PE CUZ 300','st'),
        ('Anslutningsdon Z-skena CIZ 95','st'),
        ('Anslutningsdon Z-skena CIZ 300','st'),
        ('Anslutningsdon AD 350',        'st'),
        ('Kabelsko KRF 25-12',           'st'),
        ('Avgreningshylsa C25-50',       'st'),
        ('Cu-lina belagd 25mm²',         'm'),
    ]):
        _art(conn, namn, kat_sko, enhet, 30 + i)

    # ================================================================
    # RÖR OCH SKYDDSRÖR
    # ================================================================
    ror_namn = [
        ('Korrugerat skyddsrör Ø50mm (DW)',  'm'),
        ('Korrugerat skyddsrör Ø63mm (DW)',  'm'),
        ('Korrugerat skyddsrör Ø75mm (DW)',  'm'),
        ('Korrugerat skyddsrör Ø90mm (DW)',  'm'),
        ('Korrugerat skyddsrör Ø110mm (DW)', 'm'),
        ('Korrugerat skyddsrör Ø160mm (DW)', 'm'),
    ]
    for i, (namn, enhet) in enumerate(ror_namn):
        _art(conn, namn, kat_ror, enhet, i)

    koppling_namn = [
        ('Rörände/rörskydd Ø50mm',   'st'), ('Rörände/rörskydd Ø110mm', 'st'),
        ('Kabelmudde/genomföringsbussning Ø50mm',  'st'),
        ('Kabelmudde/genomföringsbussning Ø110mm', 'st'),
    ]
    for i, (namn, enhet) in enumerate(koppling_namn):
        _art(conn, namn, kat_ror, enhet, 20 + i)

    # Kabelrör UDV (UV-beständiga med dränering, från Excel)
    for i, (namn, enhet) in enumerate([
        ('Kabelrör korrugerat UDV 110mm', 'm'),
        ('Kabelrör korrugerat UDV 160mm', 'm'),
        ('Rak-böj 110 SRN',  'st'),
        ('Rak-böj 160 SRN',  'st'),
        ('Hårdad stålspets FS-11',  'st'),
        ('Främre rör FS-21',        'st'),
        ('Förlängningsrör FS-31',   'st'),
        ('Markeringsstång KSPS 7',  'st'),
    ]):
        _art(conn, namn, kat_ror, enhet, 30 + i)

    # ================================================================
    # KABELFÖRBAND OCH MUFFAR
    # ================================================================
    forb_namn = [
        ('Kabelförband ände 4x16–4x50mm² utomhus (liten)',  'st'),
        ('Kabelförband ände 4x70–4x150mm² utomhus (medel)', 'st'),
        ('Kabelförband ände 4x185–4x240mm² utomhus (stor)', 'st'),
        ('Kabelförband ände 4x16–4x50mm² inomhus',          'st'),
        ('Kabelförband ände 4x70–4x150mm² inomhus',         'st'),
        ('Krympmuff skarv 4x16–4x50mm² (3M)',               'st'),
        ('Krympmuff skarv 4x70–4x150mm² (3M)',              'st'),
        ('Krympmuff skarv 4x185–4x240mm² (3M)',             'st'),
    ]
    for i, (namn, enhet) in enumerate(forb_namn):
        _art(conn, namn, kat_forb, enhet, i)

    # Kabelskarvar och ändhättor (från Excel)
    for i, (namn, enhet) in enumerate([
        ('Kabelskarv 4-led 6-50mm² 1kV',     'st'),
        ('Kabelskarv Al/Cu 50-95mm²',         'st'),
        ('Kabelskarv Al/Cu 95-240mm²',        'st'),
        ('Kabelskarv 1kV 95-240mm²',          'st'),
        ('Ändhätta kallkrymp 16-30mm',        'st'),
        ('Ändhätta kallkrymp 26-49mm',        'st'),
        ('Ändhätta kallkrymp 46-84mm',        'st'),
    ]):
        _art(conn, namn, kat_forb, enhet, 10 + i)

    # ================================================================
    # ÖVRIGT SMÅGODS
    # ================================================================
    smag = [
        (STD_MARKBRICKA,                    'förp'),
        ('Märkbricka aluminium (förp 50st)', 'förp'),
        (STD_MARKERINGSBAND,                 'm'),
        (STD_BUNTBAND,                       'förp'),
        ('Buntband vit (förp 100st)',        'förp'),
        (STD_KABELKLAMMOR,                   'förp'),
        ('Kabelklämmor stor (förp 10st)',    'förp'),
        ('Kabelkanal PVC 60x40mm',           'm'),
        (STD_OVERSPANNING,                   'st'),
        ('Jordelektrod/jordspett 1,5m',      'st'),
        ('Jordledning 16mm² grön/gul',       'm'),
        ('Jordledning 25mm² grön/gul',       'm'),
        (STD_JORDSKENEANSL,                  'st'),
        (STD_GENOMFORING_LITEN,              'st'),
        (STD_GENOMFORING_STOR,               'st'),
        (STD_JORDSKENOR,                     'st'),
        ('Varningsskylt elektrisk fara',     'st'),
        ('Flaggband varning 200m',           'rulle'),
        ('Kabelmärkning/kabelmärkband',      'förp'),
    ]
    for i, (namn, enhet) in enumerate(smag):
        _art(conn, namn, kat_ovrigt, enhet, i)

    # Övrigt från Excel
    for i, (namn, enhet) in enumerate([
        ('Kabelskydd plant 125-50',              'm'),
        ('Jordlina CCS 25 KAP',                  'm'),
        ('Jordtagsstång Elpress A9522463',        'st'),
        ('E.ON kabelskåpslogo klister',           'st'),
        ('Märklist transp skylthåll PL',          'st'),
        ('Kopplingskniv 1KN 1 3st',              'sats'),
    ]):
        _art(conn, namn, kat_ovrigt, enhet, 40 + i)

    # Märksystem R5000 – alla siffror och bokstäver
    r5000 = [f'Märksystem R5000 siffra {d}' for d in '0123456789'] + \
            [f'Märksystem R5000 bokstav {c}' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    for i, namn in enumerate(r5000):
        _art(conn, namn, kat_ovrigt, 'st', 50 + i)

    # ================================================================
    # MALLAR (4 stycken)
    # ================================================================
    mallar = [
        (1, 'Kabelförläggning',
         'Schakt och förläggning av markkabel med skyddsrör, kabelsand och markeringsband.'),
        (2, 'Anslutning i kabelskåp',
         'Inkoppling av kabel i befintligt kabelskåp med säkringslastfrånskiljare.'),
        (3, 'Nytt kabelskåp',
         'Installation av nytt kabelskåp med fundament, säkringar och kabelskor.'),
        (4, 'Anslutning i nätstation',
         'Inkoppling av kabel inne i nätstation med kabelskor och kabelgenomföring.'),
    ]
    for sortering, namn, beskrivning in mallar:
        conn.execute(
            "INSERT OR IGNORE INTO mallar (id, namn, beskrivning, sortering) VALUES (?,?,?,?)",
            (sortering, namn, beskrivning, sortering))

    # ----------------------------------------------------------------
    # Mall 1 – Kabelförläggning
    # ----------------------------------------------------------------
    _mall_falt(conn, 1, [
        ('kabel_artikel_id',       'Kabeltyp',                      'artikel_select',
         '{"kategori_namn":"Markkablar (0,4\\u20131 kV)"}',          'Välj markkabeltyp',       1, 1),
        ('kabel_meter',            'Kabellängd (m)',                 'number',
         '{"min":1}',                                                'Total förlagd sträcka',   1, 2),
        ('ror_artikel_id',         'Skyddsrörtyp',                  'artikel_select',
         '{"kategori_namn":"R\\u00f6r och skyddsrör","filter":"skyddsrör|kabelrör|Styv PVC|Stålrör"}',
         'Lämna tomt om inget rör',                                  0, 3),
        ('ror_meter',              'Skyddsrörlängd (m)',             'number',
         '{"min":0}',                                                'Meter skyddsrör',         0, 4),
        ('kabelforband_artikel_id','Kabelskyddsband',               'artikel_select',
         '{"kategori_namn":"\\u00d6vrigt sm\\u00e5gods","filter":"kabelskydd"}',
         'Välj kabelskyddsband',                                     0, 5),
        ('kabelforband_meter',     'Kabelskyddsband (m)',            'number',
         '{"min":0}',                                                'Meter kabelskyddsband',   0, 6),
        ('inkl_kabelsand',         'Inkl. kabelsand',                'checkbox',
         '{"default":true}',                                         'Ca 1 ton per 100m schakt',0, 7),
        ('inkl_markeringsband',    'Inkl. markeringsband',           'checkbox',
         '{"default":true}',                                         'Gul/svart varningsband',  0, 8),
    ])

    # ----------------------------------------------------------------
    # Mall 2 – Anslutning i kabelskåp
    # ----------------------------------------------------------------
    _mall_falt(conn, 2, [
        ('kabelskap_benamning', 'Kabelskåpsbeteckning',              'text',
         '{}',                                                        'T.ex. KS-42, Storg. 12',  1, 1),
        ('sakring_artikel_id',  'Säkringsstorlek',                   'artikel_select',
         '{"kategori_namn":"S\\u00e4kringslastfr\\u00e5nskiljare"}', 'Välj säkring',            1, 2),
        ('kabelskor_artikel_id','Kabeldimension (kabelskor)',         'artikel_select',
         '{"kategori_namn":"Kabelskor och anslutningsmaterial","filter":"presssko"}',
         'Välj kabelskor för kabeldimensionen',                       1, 3),
        ('antal_kablar',        'Antal inkommande kablar',            'number',
         '{"min":1,"default":1}',                                     'Per inkommande kabel',    1, 4),
    ])

    # ----------------------------------------------------------------
    # Mall 3 – Nytt kabelskåp
    # ----------------------------------------------------------------
    _mall_falt(conn, 3, [
        ('kabelskap_artikel_id',    'Kabelskåp (välj ur katalog)',    'artikel_select',
         '{"kategori_namn":"Kabelskåp och fördelningsskåp"}',        'Välj skåptyp',            1, 1),
        ('antal_sakringsfack',      'Antal säkringsfack',             'number',
         '{"min":1}',                                                 'Aktiva fack med säkring', 1, 2),
        ('sakring_artikel_id',      'Säkringsstorlek',                'artikel_select',
         '{"kategori_namn":"S\\u00e4kringslastfr\\u00e5nskiljare"}', 'En per fack',             1, 3),
        ('kabelskor_artikel_id',    'Kabeldimension (kabelskor)',      'artikel_select',
         '{"kategori_namn":"Kabelskor och anslutningsmaterial","filter":"presssko"}',
         '4 per fack (3L+N)',                                         1, 4),
        ('inkl_overspanningsskydd', 'Inkl. överspänningsskydd',       'checkbox',
         '{"default":false}',                                         'Tillval',                 0, 5),
    ])

    # ----------------------------------------------------------------
    # Mall 4 – Anslutning i nätstation
    # ----------------------------------------------------------------
    _mall_falt(conn, 4, [
        ('kabel_artikel_id',    'Kabeltyp',                          'artikel_select',
         '{"kategori_namn":"Markkablar (0,4\\u20131 kV)"}',          'Välj kabeltyp',           1, 1),
        ('kabel_meter',         'Kabellängd inne i station (m)',      'number',
         '{"min":0.5}',                                               'Meter kabel i stationen', 1, 2),
        ('kabelskor_artikel_id','Kabeldimension (kabelskor)',          'artikel_select',
         '{"kategori_namn":"Kabelskor och anslutningsmaterial","filter":"presssko"}',
         '4 kabelskor (3L+N)',                                         1, 3),
        ('antal_genomforingar', 'Antal kabelgenomföringar',           'number',
         '{"min":1,"default":1}',                                     'Genomföringar i vägg',    1, 4),
    ])

    # ================================================================
    # Inställningar
    # ================================================================
    for nyckel, varde in [
        ('foretagsnamn',    'Oneco Networks AB'),
        ('admin_losenord',  hashlib.sha256(b'admin').hexdigest()),
        ('logotyptext',     'LÅGSPÄNNINGSBEREDNING'),
    ]:
        conn.execute("INSERT OR IGNORE INTO installningar (nyckel, varde) VALUES (?,?)",
                     (nyckel, varde))

    # Beredare
    for namn in ['Anna L.', 'Erik S.', 'Maria K.']:
        conn.execute("INSERT OR IGNORE INTO beredare (namn) VALUES (?)", (namn,))


def fyll_nya_artiklar(conn):
    """
    Lägger till artiklar som tillkom i databas-version 2.
    Anropas vid migrering från äldre installation (INSERT OR IGNORE är säkert).
    """
    def get_kat(namn):
        r = conn.execute("SELECT id FROM kategorier WHERE namn=?", (namn,)).fetchone()
        return r['id'] if r else None

    kat_kabel  = get_kat('Markkablar (0,4–1 kV)')
    kat_skap   = get_kat('Kabelskåp och fördelningsskåp')
    kat_sak    = get_kat('Säkringslastfrånskiljare')
    kat_sko    = get_kat('Kabelskor och anslutningsmaterial')
    kat_ror    = get_kat('Rör och skyddsrör')
    kat_forb   = get_kat('Kabelförband och muffar')
    kat_ovrigt = get_kat('Övrigt smågods')

    if kat_kabel:
        for i, namn in enumerate(['AML 4G25mm² 1kV', 'AML 4G50mm² 1kV', 'AML 4G95mm² 1kV',
                                   'AML 4G150mm² 1kV', 'AML 4G240mm² 1kV']):
            _art(conn, namn, kat_kabel, 'm', 60 + i)

    if kat_skap:
        for i, namn in enumerate(['Kapsling CDC 420 K2', 'Kapsling CDC 440 K3', 'Kapsling CDC 460 K4']):
            _art(conn, namn, kat_skap, 'st', 30 + i)

    if kat_sak:
        for i, namn in enumerate([
            'Säkringslastfrånskiljare SLF160P', 'Säkringslastfrånskiljare SLF250P',
            'Säkringslastfrånskiljare SLF400P', 'Säkringslastfrånskiljare SLF630P',
            'Säkringslastfrånskiljare SLD 00/000 500V', 'Säkringslastfrånskiljare SLE 1/2 690V',
        ]):
            _art(conn, namn, kat_sak, 'st', 20 + i)
        kniv = [
            'Knivsäkring ECO HICAP 000/10A', 'Knivsäkring ECO HICAP 000/16A',
            'Knivsäkring ECO HICAP 000/25A', 'Knivsäkring ECO HICAP 000/35A',
            'Knivsäkring ECO HICAP 000/50A', 'Knivsäkring ECO HICAP 000/63A',
            'Knivsäkring ECO HICAP 000/80A', 'Knivsäkring ECO HICAP 000/100A',
            'Knivsäkring ECO HICAP 00/125A', 'Knivsäkring ECO HICAP 00/160A',
            'Knivsäkring ECO HICAP 1/63A',  'Knivsäkring ECO HICAP 1/80A',
            'Knivsäkring ECO HICAP 1/100A', 'Knivsäkring ECO HICAP 1/125A',
            'Knivsäkring ECO HICAP 1/160A', 'Knivsäkring ECO HICAP 1/200A',
            'Knivsäkring ECO HICAP 1/224A', 'Knivsäkring ECO HICAP 1/250A',
            'Knivsäkring ECO HICAP 2/100A', 'Knivsäkring ECO HICAP 2/125A',
            'Knivsäkring ECO HICAP 2/160A', 'Knivsäkring ECO HICAP 2/200A',
            'Knivsäkring ECO HICAP 2/224A', 'Knivsäkring ECO HICAP 2/250A',
            'Knivsäkring ECO HICAP 2/315A', 'Knivsäkring ECO HICAP 2/355A',
        ]
        for i, namn in enumerate(kniv):
            _art(conn, namn, kat_sak, 'st', 60 + i)

    if kat_sko:
        for i, (namn, enhet) in enumerate([
            ('Anslutningsdon ABB ADI 95',    'st'), ('Anslutningsdon ABB ADI 300',   'st'),
            ('Anslutningsdon ABB ADU 95',    'st'), ('Anslutningsdon ABB ADU 300',   'st'),
            ('Anslutningsdon PEN/PE CUZ 95', 'st'), ('Anslutningsdon PEN/PE CUZ 300','st'),
            ('Anslutningsdon Z-skena CIZ 95','st'), ('Anslutningsdon Z-skena CIZ 300','st'),
            ('Anslutningsdon AD 350',        'st'), ('Kabelsko KRF 25-12',           'st'),
            ('Avgreningshylsa C25-50',       'st'), ('Cu-lina belagd 25mm²',         'm'),
        ]):
            _art(conn, namn, kat_sko, enhet, 30 + i)

    if kat_ror:
        for i, (namn, enhet) in enumerate([
            ('Kabelrör korrugerat UDV 110mm', 'm'), ('Kabelrör korrugerat UDV 160mm', 'm'),
            ('Rak-böj 110 SRN', 'st'), ('Rak-böj 160 SRN', 'st'),
            ('Hårdad stålspets FS-11', 'st'), ('Främre rör FS-21', 'st'),
            ('Förlängningsrör FS-31', 'st'), ('Markeringsstång KSPS 7', 'st'),
        ]):
            _art(conn, namn, kat_ror, enhet, 30 + i)

    if kat_forb:
        for i, (namn, enhet) in enumerate([
            ('Kabelskarv 4-led 6-50mm² 1kV', 'st'), ('Kabelskarv Al/Cu 50-95mm²', 'st'),
            ('Kabelskarv Al/Cu 95-240mm²', 'st'),   ('Kabelskarv 1kV 95-240mm²', 'st'),
            ('Ändhätta kallkrymp 16-30mm', 'st'),   ('Ändhätta kallkrymp 26-49mm', 'st'),
            ('Ändhätta kallkrymp 46-84mm', 'st'),
        ]):
            _art(conn, namn, kat_forb, enhet, 10 + i)

    if kat_ovrigt:
        for i, (namn, enhet) in enumerate([
            ('Kabelskydd plant 125-50', 'm'),       ('Jordlina CCS 25 KAP', 'm'),
            ('Jordtagsstång Elpress A9522463', 'st'),
            ('Märksystem R5000 siffra 0-9 dekal', 'st'),
            ('E.ON kabelskåpslogo klister', 'st'),  ('Märklist transp skylthåll PL', 'st'),
            ('Kopplingskniv 1KN 1 3st', 'sats'),
            ('Märksystem H50 gul siffra 0-9', 'st'),
            ('Märksystem H50 gul bokstav A-Z', 'st'), ('Märksystem H50 gul blank', 'st'),
        ]):
            _art(conn, namn, kat_ovrigt, enhet, 40 + i)


def fyll_egenkontroll(conn):
    """
    Seed egenkontrollpunkter per mall.
    Används INSERT OR IGNORE – säkert att anropa flera gånger.
    """
    egk = {
        # Mall 1 – Kabelförläggning
        1: [
            'Riskhantering utförd och dokumenterad',
            'Schaktdjup kontrollerat',
            'Kabelns förläggning godkänd av beställaren',
            'Mantelprovning utförd med godkända värden',
            'Kabelsand utlagd i erforderlig mängd',
            'Markeringsband utlagt',
            'Kabelskyddsplatta monterad (vid vägkorsning o.d.)',
            'Kabelände utförd korrekt och väderskyddad',
            'Märkning utförd enligt anvisningar',
            'Faslikhet kontrollerad',
            'Fotodokumentation utförd',
            'Förlagt en kj. 41',
        ],
        # Mall 2 – Anslutning i kabelskåp
        2: [
            'Riskhantering utförd och dokumenterad',
            'Spänningslöshet kontrollerad och säkrad',
            'Mantelprovning utförd med godkända värden',
            'Kabelskor korrekt monterade och pressade',
            'Anslutningar dragna med rätt moment',
            'Säkringar rätt storlek, rättvända och märkning synlig',
            'Märkning utförd enligt anvisningar',
            'Faslikhet kontrollerad',
            'Spänningsprovning: Fas-N 225–240 V, Fas-Fas 390–415 V',
            'Kabelskåp stängt och låst',
        ],
        # Mall 3 – Nytt kabelskåp
        3: [
            'Riskhantering utförd och dokumenterad',
            'Kabelskåp placerat och monterat enligt anvisningar',
            'Fundament godkänt och kabelskåp säkrat',
            'Jordfförbindelsemätning utförd med godkända värden',
            'Potentialutjämning utförd',
            'Mantelprovning utförd med godkända värden',
            'Kabelskor korrekt monterade och dragna med rätt moment',
            'Säkringar rätt storlek, rättvända och märkning synlig',
            'Överspänningsskydd monterat (om beställt)',
            'IP-klassning kontrollerad (IP44 eller enligt krav)',
            'Märkning utförd enligt anvisningar',
            'Faslikhet kontrollerad',
            'Spänningsprovning: Fas-N 225–240 V, Fas-Fas 390–415 V',
            'Dokumentation/stationskort uppdaterad',
        ],
        # Mall 4 – Anslutning i nätstation
        4: [
            'Riskhantering utförd och dokumenterad',
            'Leveranskontroll utförd',
            'Mantelprovning utförd med godkända värden',
            'Jordfförbindelsemätning utförd med godkända värden',
            'Jordtag mätta och protokollförda',
            'Potentialutjämning utförd',
            'Samtliga anslutningar dragna med rätt moment',
            'Kabelgenomföringar tätade och godkända',
            'Faslikhet kontrollerad',
            'Fasfölj kontrollerad – ringa in: går rätt / går fel',
            'Spänningsprovning: Fas-N 225–240 V, Fas-Fas 390–415 V',
            'Märkning utförd enligt beställarens anvisningar',
            'Station och anslutningar uppfyller IP 2X',
            'Stationsutrymme urstädat',
            'Stationskort uppdaterat (transformator, lsp- och msp-fördelning)',
            'Funktionskontroll av skyddsvakter utförd (temp, gas, tryck, ljusbågsvakt)',
        ],
    }

    for mall_id, punkter in egk.items():
        for i, punkt in enumerate(punkter):
            conn.execute(
                "INSERT OR IGNORE INTO mall_egenkontroll (mall_id, punkt, sortering) VALUES (?,?,?)",
                (mall_id, punkt, i)
            )


def _mall_falt(conn, mall_id, falt):
    for faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering in falt:
        conn.execute(
            "INSERT OR IGNORE INTO mall_inputfalt "
            "(mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering))
