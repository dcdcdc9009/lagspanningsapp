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
    conn.execute("INSERT OR IGNORE INTO artiklar (artikelnamn, kategori_id, enhet, sortering) VALUES (?,?,?,?)",
                 (namn, kat_id, enhet, sort))
    return conn.execute("SELECT id FROM artiklar WHERE artikelnamn=? AND kategori_id=?",
                        (namn, kat_id)).fetchone()['id']


def _pris(conn, art_id, lev_id, artnr, pris):
    conn.execute(
        "INSERT OR IGNORE INTO artikel_leverantor (artikel_id, leverantor_id, artikelnummer, a_pris) VALUES (?,?,?,?)",
        (art_id, lev_id, artnr, pris))


def fyll_i_startdata(conn):
    # ----------------------------------------------------------------
    # Kategorier
    # ----------------------------------------------------------------
    kat_kabel  = _kat(conn, 'Markkablar (0,4–1 kV)',              1)
    kat_skap   = _kat(conn, 'Kabelskåp och fördelningsskåp',       2)
    kat_sak    = _kat(conn, 'Säkringslastfrånskiljare',            3)
    kat_sko    = _kat(conn, 'Kabelskor och anslutningsmaterial',    4)
    kat_ror    = _kat(conn, 'Rör och skyddsrör',                   5)
    kat_forb   = _kat(conn, 'Kabelförband och muffar',             6)
    kat_ovrigt = _kat(conn, 'Övrigt smågods',                      7)

    # ----------------------------------------------------------------
    # Leverantörer
    # ----------------------------------------------------------------
    onninen = _lev(conn, 'Onninen')
    ahlsell = _lev(conn, 'Ahlsell')

    # ================================================================
    # MARKKABLAR (0,4–1 kV)
    # ================================================================
    axkj4 = [
        ('AXKJ 4x16mm²',  25,  155,  'ART-K001', 'ART-AK001'),
        ('AXKJ 4x25mm²',  35,  225,  'ART-K002', 'ART-AK002'),
        ('AXKJ 4x35mm²',  45,  295,  'ART-K003', 'ART-AK003'),
        ('AXKJ 4x50mm²',  65,  420,  'ART-K004', 'ART-AK004'),
        ('AXKJ 4x70mm²',  90,  580,  'ART-K005', 'ART-AK005'),
        ('AXKJ 4x95mm²',  120, 780,  'ART-K006', 'ART-AK006'),
        ('AXKJ 4x120mm²', 155, 990,  'ART-K007', 'ART-AK007'),
        ('AXKJ 4x150mm²', 195, 1250, 'ART-K008', 'ART-AK008'),
        ('AXKJ 4x185mm²', 250, 1590, 'ART-K009', 'ART-AK009'),
        ('AXKJ 4x240mm²', 330, 2050, 'ART-K010', 'ART-AK010'),
    ]
    for i, (namn, po, pa, nro, nra) in enumerate(axkj4):
        aid = _art(conn, namn, kat_kabel, 'm', i)
        _pris(conn, aid, onninen, nro, po)
        _pris(conn, aid, ahlsell, nra, pa)

    for i, (namn, po, nro) in enumerate([
        ('AXKJ 1x95mm²',  85,  'ART-K011'),
        ('AXKJ 1x120mm²', 110, 'ART-K012'),
        ('AXKJ 1x150mm²', 140, 'ART-K013'),
        ('AXKJ 1x185mm²', 175, 'ART-K014'),
        ('AXKJ 1x240mm²', 230, 'ART-K015'),
    ]):
        aid = _art(conn, namn, kat_kabel, 'm', 20 + i)
        _pris(conn, aid, onninen, nro, po)

    for i, (namn, po, nro) in enumerate([
        ('EKKJ 4x25mm²', 42,  'ART-K020'),
        ('EKKJ 4x50mm²', 85,  'ART-K021'),
        ('EKKJ 4x95mm²', 155, 'ART-K022'),
    ]):
        aid = _art(conn, namn, kat_kabel, 'm', 30 + i)
        _pris(conn, aid, onninen, nro, po)

    for i, (namn, po, nro) in enumerate([
        ('FKKJ 4x35mm²',  55,  'ART-K030'),
        ('FKKJ 4x70mm²',  105, 'ART-K031'),
        ('FKKJ 4x150mm²', 210, 'ART-K032'),
        ('FKKJ 4x240mm²', 360, 'ART-K033'),
    ]):
        aid = _art(conn, namn, kat_kabel, 'm', 40 + i)
        _pris(conn, aid, onninen, nro, po)

    for i, (namn, po, nro) in enumerate([
        ('AKKJ 4x25mm²',  32,  'ART-K040'),
        ('AKKJ 4x70mm²',  95,  'ART-K041'),
        ('AKKJ 4x120mm²', 160, 'ART-K042'),
    ]):
        aid = _art(conn, namn, kat_kabel, 'm', 50 + i)
        _pris(conn, aid, onninen, nro, po)

    # ================================================================
    # KABELSKÅP OCH FÖRDELNINGSSKÅP
    # ================================================================
    skap_data = [
        # (namn, pris_ahlsell, artnr_ahlsell, pris_onninen, artnr_onninen)
        ('ABB RK 5-fack',               4500,  'ART-S001', None,  None),
        ('ABB RK 7-fack',               6500,  'ART-S002', None,  None),
        ('ABB RK 10-fack',              9000,  'ART-S003', None,  None),
        ('ABB RK 12-fack',              11500, 'ART-S004', None,  None),
        ('ABB Combiflex 4-fack',        5200,  'ART-S005', None,  None),
        ('ABB Combiflex 6-fack',        7200,  'ART-S006', None,  None),
        ('Elmeko kabelskåp 4-fack',     3800,  'ART-S007', None,  None),
        ('Elmeko kabelskåp 6-fack',     5200,  'ART-S008', None,  None),
        ('Elmeko kabelskåp 8-fack',     7000,  'ART-S009', None,  None),
        ('Elmeko kabelskåp 10-fack',    8500,  'ART-S010', None,  None),
        ('Elmeko kabelskåp 12-fack',    10200, 'ART-S011', None,  None),
        ('Ensto utomhus 4-fack',        4200,  None,       4200,  'ART-S012'),
        ('Ensto utomhus 6-fack',        5800,  None,       5800,  'ART-S013'),
        ('Ensto utomhus 8-fack',        7600,  None,       7600,  'ART-S014'),
        ('Ensto utomhus 12-fack',       10800, None,       10800, 'ART-S015'),
        ('Hager kabelskåp 4-fack',      3600,  'ART-S016', None,  None),
        ('Hager kabelskåp 6-fack',      5100,  'ART-S017', None,  None),
        ('Hager kabelskåp 8-fack',      6800,  'ART-S018', None,  None),
        ('Schneider Linergy 6-fack',    6200,  'ART-S019', None,  None),
        ('Schneider Linergy 12-fack',   11000, 'ART-S020', None,  None),
        ('Siemens 8GK 4-fack',          5400,  'ART-S021', None,  None),
        ('Siemens 8GK 6-fack',          7100,  'ART-S022', None,  None),
        ('Pehaka kabelskåp 4-fack',     3400,  'ART-S023', None,  None),
        ('Pehaka kabelskåp 6-fack',     4900,  'ART-S024', None,  None),
        ('Pehaka kabelskåp 8-fack',     6500,  'ART-S025', None,  None),
    ]
    for i, (namn, pa, nra, po, nro) in enumerate(skap_data):
        aid = _art(conn, namn, kat_skap, 'st', i)
        if pa and nra:
            _pris(conn, aid, ahlsell, nra, pa)
        if po and nro:
            _pris(conn, aid, onninen, nro, po)

    # ================================================================
    # SÄKRINGSLASTFRÅNSKILJARE
    # ================================================================
    sak_data = [
        ('ABB Säkringslastfrånskiljare 63A',  850,  'ART-F001'),
        ('ABB Säkringslastfrånskiljare 100A', 1100, 'ART-F002'),
        ('ABB Säkringslastfrånskiljare 160A', 1600, 'ART-F003'),
        ('ABB Säkringslastfrånskiljare 250A', 2800, 'ART-F004'),
        ('ABB Säkringslastfrånskiljare 400A', 4500, 'ART-F005'),
        ('Siemens Säkr.lastfrånskiljare 63A', 820,  'ART-F006'),
        ('Siemens Säkr.lastfrånskiljare 160A',1550, 'ART-F007'),
        ('Schneider Säkr.lastfrånskiljare 63A',880, 'ART-F008'),
        ('Schneider Säkr.lastfrånskiljare 160A',1650,'ART-F009'),
    ]
    for i, (namn, pa, nra) in enumerate(sak_data):
        aid = _art(conn, namn, kat_sak, 'st', i)
        _pris(conn, aid, ahlsell, nra, pa)

    # Tillbehör
    for i, (namn, pa, nra) in enumerate([
        ('NH-säkring 00 63A',   85,  'ART-F020'),
        ('NH-säkring 00 100A',  95,  'ART-F021'),
        ('NH-säkring 00 160A',  110, 'ART-F022'),
        ('NH-säkring 1 200A',   130, 'ART-F023'),
        ('NH-säkring 2 315A',   165, 'ART-F024'),
        ('NH-säkring 3 400A',   210, 'ART-F025'),
        ('Handtag säkr.lastfrånskiljare', 180, 'ART-F030'),
        ('Täcklock/blindlock fack', 95, 'ART-F031'),
    ]):
        aid = _art(conn, namn, kat_sak, 'st', 20 + i)
        _pris(conn, aid, ahlsell, nra, pa)

    # ================================================================
    # KABELSKOR OCH ANSLUTNINGSMATERIAL
    # ================================================================
    sko_dims = [
        ('16mm²',  22,  'ART-L001'),
        ('25mm²',  28,  'ART-L002'),
        ('35mm²',  35,  'ART-L003'),
        ('50mm²',  45,  'ART-L004'),
        ('70mm²',  58,  'ART-L005'),
        ('95mm²',  75,  'ART-L006'),
        ('120mm²', 95,  'ART-L007'),
        ('150mm²', 118, 'ART-L008'),
        ('185mm²', 145, 'ART-L009'),
        ('240mm²', 185, 'ART-L010'),
    ]
    for i, (dim, pa, nra) in enumerate(sko_dims):
        aid = _art(conn, f'Kabelsko presssko {dim} (Klauke)', kat_sko, 'st', i)
        _pris(conn, aid, ahlsell, nra, pa)
        _pris(conn, aid, onninen, 'ON-' + nra, round(pa * 1.05, 0))

    aid = _art(conn, STD_KABELSTRUMPA,  kat_sko, 'st', 20)
    _pris(conn, aid, onninen, 'ART-L020', 45)
    _pris(conn, aid, ahlsell, 'ART-AL020', 48)

    aid = _art(conn, 'Jordskenor 60A', kat_sko, 'st', 21)
    _pris(conn, aid, ahlsell, 'ART-L021', 120)
    aid = _art(conn, 'Jordskenor 160A', kat_sko, 'st', 22)
    _pris(conn, aid, ahlsell, 'ART-L022', 175)
    aid = _art(conn, 'Jordklämma 16-35mm²', kat_sko, 'st', 23)
    _pris(conn, aid, ahlsell, 'ART-L023', 55)

    aid = _art(conn, 'Kopplingsskena 63A', kat_sko, 'st', 24)
    _pris(conn, aid, ahlsell, 'ART-L024', 220)
    aid = _art(conn, 'Kopplingsskena 160A', kat_sko, 'st', 25)
    _pris(conn, aid, ahlsell, 'ART-L025', 380)
    aid = _art(conn, 'Kopplingsskena 250A', kat_sko, 'st', 26)
    _pris(conn, aid, ahlsell, 'ART-L026', 620)

    aid = _art(conn, STD_SKRUV_M8, kat_sko, 'sats', 27)
    _pris(conn, aid, onninen, 'ART-L030', 38)
    aid = _art(conn, 'Skruv och mutter sats M10', kat_sko, 'sats', 28)
    _pris(conn, aid, onninen, 'ART-L031', 45)
    aid = _art(conn, 'Skruv och mutter sats M12', kat_sko, 'sats', 29)
    _pris(conn, aid, onninen, 'ART-L032', 55)

    # ================================================================
    # RÖR OCH SKYDDSRÖR
    # ================================================================
    ror_data = [
        ('Korrugerat skyddsrör Ø50mm (DW)',  8,  'ART-R001'),
        ('Korrugerat skyddsrör Ø63mm (DW)',  12, 'ART-R002'),
        ('Korrugerat skyddsrör Ø75mm (DW)',  16, 'ART-R003'),
        ('Korrugerat skyddsrör Ø90mm (DW)',  19, 'ART-R004'),
        ('Korrugerat skyddsrör Ø110mm (DW)', 22, 'ART-R005'),
        ('Korrugerat skyddsrör Ø160mm (DW)', 38, 'ART-R006'),
        ('Styv PVC-rör Ø50mm',               18, 'ART-R010'),
        ('Styv PVC-rör Ø63mm',               24, 'ART-R011'),
        ('Styv PVC-rör Ø110mm',              45, 'ART-R012'),
        ('Styv PVC-rör Ø160mm',              68, 'ART-R013'),
        ('Stålrör Ø50mm (väggenomföring)',   85, 'ART-R020'),
        ('Stålrör Ø100mm (väggenomföring)', 165, 'ART-R021'),
    ]
    for i, (namn, po, nro) in enumerate(ror_data):
        aid = _art(conn, namn, kat_ror, 'm', i)
        _pris(conn, aid, onninen, nro, po)

    koppling_data = [
        ('Rörkoppling Ø50mm',  12,  'ART-R030'),
        ('Rörkoppling Ø63mm',  16,  'ART-R031'),
        ('Rörkoppling Ø75mm',  19,  'ART-R032'),
        ('Rörkoppling Ø90mm',  22,  'ART-R033'),
        ('Rörkoppling Ø110mm', 28,  'ART-R034'),
        ('Rörkoppling Ø160mm', 48,  'ART-R035'),
        ('Rörände/rörskydd Ø50mm',   8, 'ART-R040'),
        ('Rörände/rörskydd Ø110mm', 14, 'ART-R041'),
        ('Kabelmudde/genomföringsbussning Ø50mm', 22, 'ART-R050'),
        ('Kabelmudde/genomföringsbussning Ø110mm',38, 'ART-R051'),
    ]
    for i, (namn, po, nro) in enumerate(koppling_data):
        aid = _art(conn, namn, kat_ror, 'st', 20 + i)
        _pris(conn, aid, onninen, nro, po)

    # ================================================================
    # KABELFÖRBAND OCH MUFFAR
    # ================================================================
    forb_data = [
        ('Kabelförband ände 4x16–4x50mm² utomhus (liten)',  650,  'ART-B001'),
        ('Kabelförband ände 4x70–4x150mm² utomhus (medel)', 950,  'ART-B002'),
        ('Kabelförband ände 4x185–4x240mm² utomhus (stor)', 1350, 'ART-B003'),
        ('Kabelförband ände 4x16–4x50mm² inomhus',          420,  'ART-B004'),
        ('Kabelförband ände 4x70–4x150mm² inomhus',         680,  'ART-B005'),
        ('Krympmuff skarv 4x16–4x50mm² (3M)',               1200, 'ART-B010'),
        ('Krympmuff skarv 4x70–4x150mm² (3M)',              1800, 'ART-B011'),
        ('Krympmuff skarv 4x185–4x240mm² (3M)',             2800, 'ART-B012'),
    ]
    for i, (namn, pa, nra) in enumerate(forb_data):
        aid = _art(conn, namn, kat_forb, 'st', i)
        _pris(conn, aid, ahlsell, nra, pa)

    # ================================================================
    # ÖVRIGT SMÅGODS
    # ================================================================
    smag = [
        (STD_MARKBRICKA,     'förp',  85,   'ART-O001', onninen),
        ('Märkbricka aluminium (förp 50st)', 'förp', 125, 'ART-O002', onninen),
        (STD_MARKERINGSBAND, 'm',     8,    'ART-O003', onninen),
        ('Markeringsband röd', 'm',   8,    'ART-O004', onninen),
        (STD_KABELSKYDDSNAAT,'m',     18,   'ART-O010', onninen),
        ('Kabelskyddsplatta (grön/svart)', 'm', 22, 'ART-O011', onninen),
        (STD_BUNTBAND,       'förp',  45,   'ART-O020', onninen),
        ('Buntband vit (förp 100st)', 'förp', 45, 'ART-O021', onninen),
        (STD_KABELKLAMMOR,   'förp',  55,   'ART-O030', onninen),
        ('Kabelklämmor stor (förp 10st)', 'förp', 75, 'ART-O031', onninen),
        ('Kabelstege plast 200mm bredd', 'm', 85, 'ART-O040', onninen),
        ('Kabelstege plast 300mm bredd', 'm', 115, 'ART-O041', onninen),
        ('Kabelkanal PVC 60x40mm',       'm',  65, 'ART-O042', onninen),
        (STD_KABELSAND,      'ton',   450,  'ART-O050', onninen),
        (STD_BETONGFUNDAMENT,'st',    1800, 'ART-O060', ahlsell),
        (STD_OVERSPANNING,   'st',    850,  'ART-O070', ahlsell),
        ('Jordelektrod/jordspett 1,5m', 'st', 280, 'ART-O080', ahlsell),
        ('Jordledning 16mm² grön/gul', 'm', 28, 'ART-O081', onninen),
        ('Jordledning 25mm² grön/gul', 'm', 42, 'ART-O082', onninen),
        (STD_JORDSKENEANSL,  'st',    95,   'ART-O083', ahlsell),
        (STD_GENOMFORING_LITEN, 'st', 65,   'ART-O090', onninen),
        (STD_GENOMFORING_STOR,  'st', 110,  'ART-O091', onninen),
        ('Kabelgenomföring flerfack',   'st', 185, 'ART-O092', onninen),
        (STD_JORDSKENOR,     'st',    120,  'ART-O100', ahlsell),
        ('Silikon och fogmassa',        'st', 95,  'ART-O110', onninen),
        ('Varningsskylt elektrisk fara','st', 45,  'ART-O120', onninen),
        ('Flaggband varning 200m',      'rulle', 85, 'ART-O121', onninen),
        ('Kabelmärkning/kabelmärkband', 'förp', 55, 'ART-O130', onninen),
    ]
    for i, (namn, enhet, pris, artnr, lev) in enumerate(smag):
        aid = _art(conn, namn, kat_ovrigt, enhet, i)
        _pris(conn, aid, lev, artnr, pris)

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
         '{"kategori_namn":"R\\u00f6r och skyddsrör"}',              'Lämna tomt om inget rör', 0, 3),
        ('ror_meter',              'Skyddsrörlängd (m)',             'number',
         '{"min":0}',                                                'Meter skyddsrör',         0, 4),
        ('ror_koppling_artikel_id','Rörkopplingstyp',               'artikel_select',
         '{"kategori_namn":"R\\u00f6r och skyddsrör","filter":"koppling"}',
         'Välj rörkoppling (beräknas 1 per 6m)',                     0, 5),
        ('kabelforband_artikel_id','Kabelförband ände (typ)',        'artikel_select',
         '{"kategori_namn":"Kabelförband och muffar","filter":"\\u00e4nde"}',
         'Välj förbandtyp',                                          0, 6),
        ('antal_kabelander',       'Antal kabeländar (st)',          'number',
         '{"min":1,"default":2}',                                    '1 per ände',              1, 7),
        ('inkl_kabelsand',         'Inkl. kabelsand',                'checkbox',
         '{"default":true}',                                         'Ca 1 ton per 100m schakt',0, 8),
        ('inkl_markeringsband',    'Inkl. markeringsband',           'checkbox',
         '{"default":true}',                                         'Gul/svart varningsband',  0, 9),
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
        ('foretagsnamn',    'Mitt Elnätsföretag AB'),
        ('admin_losenord',  hashlib.sha256(b'admin').hexdigest()),
        ('logotyptext',     'LÅGSPÄNNINGSBEREDNING'),
    ]:
        conn.execute("INSERT OR IGNORE INTO installningar (nyckel, varde) VALUES (?,?)",
                     (nyckel, varde))

    # Beredare
    for namn in ['Anna L.', 'Erik S.', 'Maria K.']:
        conn.execute("INSERT OR IGNORE INTO beredare (namn) VALUES (?)", (namn,))


def _mall_falt(conn, mall_id, falt):
    for faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering in falt:
        conn.execute(
            "INSERT OR IGNORE INTO mall_inputfalt "
            "(mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering))
