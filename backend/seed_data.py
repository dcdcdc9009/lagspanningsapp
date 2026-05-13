"""Fyller databasen med startdata vid första uppstart."""
import hashlib


# Standardartiklar som mallberäkning letar upp (namn måste matcha exakt)
STD_GENOMFORING_STOR = 'Kabelgenomföring stor'   # används ej längre – bevaras för bakåtkompatibilitet
STD_OVERSPANNING     = 'Överspänningsskydd'        # används ej längre – bevaras för bakåtkompatibilitet


def _kat(conn, namn, sortering):
    conn.execute("INSERT OR IGNORE INTO kategorier (namn, sortering) VALUES (?,?)", (namn, sortering))
    return conn.execute("SELECT id FROM kategorier WHERE namn=?", (namn,)).fetchone()['id']


def _lev(conn, namn):
    conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES (?)", (namn,))
    return conn.execute("SELECT id FROM leverantorer WHERE namn=?", (namn,)).fetchone()['id']


def _art(conn, namn, kat_id, enhet, sort=0, moduler=0):
    existing = conn.execute(
        "SELECT id FROM artiklar WHERE artikelnamn=? AND kategori_id=?", (namn, kat_id)
    ).fetchone()
    if existing:
        return existing['id']
    cur = conn.execute(
        "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering, moduler) VALUES (?,?,?,?,?)",
        (namn, kat_id, enhet, sort, moduler))
    return cur.lastrowid


def fyll_i_startdata(conn):
    # ----------------------------------------------------------------
    # Kategorier (från Excel)
    # ----------------------------------------------------------------
    kat_kabel   = _kat(conn, 'Kablar',                    1)
    kat_ansl    = _kat(conn, 'Anslutningsdon',             2)
    kat_sak     = _kat(conn, 'Säkringslastfrånskiljare',   3)
    kat_kniv    = _kat(conn, 'Knivssäkringar',             4)
    kat_kaps    = _kat(conn, 'Kapsling',                   5)
    kat_skarv   = _kat(conn, 'Kabelskarvar',               6)
    kat_skydd   = _kat(conn, 'Kabelskydd och rör',         7)
    kat_mark    = _kat(conn, 'Märkning',                   8)
    kat_ovrigt  = _kat(conn, 'Övrigt',                     9)

    # ----------------------------------------------------------------
    # Leverantörer
    # ----------------------------------------------------------------
    _lev(conn, 'Onninen')
    _lev(conn, 'Ahlsell')

    # ================================================================
    # KABLAR
    # ================================================================
    for i, (namn, enhet) in enumerate([
        ('AML 4G10 1KV SV',    'm'),
        ('AML 4G25 1KV SV',    'm'),
        ('AML 4G50 1KV SV',    'm'),
        ('AML 4G95 1KV SV',    'm'),
        ('AML 4G150 1KV SV',   'm'),
        ('AML 4G240 1KV SV',   'm'),
        ('CU-LINA BELAGD 25MM²', 'm'),
    ]):
        _art(conn, namn, kat_kabel, enhet, i)

    # ================================================================
    # ANSLUTNINGSDON
    # ================================================================
    for i, namn in enumerate([
        'ANSLUTNINGSDON ABB ADI 300 ISOLERAT',
        'ANSLUTNINGSDON ABB ADU 300 OISOLERAT',
        'ANSLUTNINGSDON ABB ADI 95 ISOLERAT',
        'ANSLUTNINGSDON ABB ADU 95 OISOLERAT',
        'ANSLUTNINGSDON AD 350',
        'ANSLUTNINGSDON PEN/PE CUZ 95',
        'ANSLUTNINGSDON PEN/PE CUZ 300',
        'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95',
        'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300',
    ]):
        _art(conn, namn, kat_ansl, 'st', i, moduler=-1)

    # ================================================================
    # SÄKRINGSLASTFRÅNSKILJARE
    # ================================================================
    for i, (namn, moduler) in enumerate([
        ('SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',  -3),
        ('SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V', -3),
        ('SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',   -3),
        ('SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',   -3),
        ('SÄKRINGSLASFRÅNSK SLF160P',             -4),
        ('SÄKRINGSLASFRÅNSK SLF250P',             -4),
        ('SÄKRINGSLASFRÅNSK SLF400P',             -4),
        ('SÄKRINGSLASFRÅNSK SLF630P',             -4),
    ]):
        _art(conn, namn, kat_sak, 'st', i, moduler=moduler)

    # ================================================================
    # KNIVSSÄKRINGAR
    # ================================================================
    for i, namn in enumerate([
        'KNIVSSÄKRING ECO HICAP 000/10A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/16A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/25A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/35A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/50A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/63A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/80A GG 500V',
        'KNIVSSÄKRING ECO HICAP 000/100A GG 500V',
        'KNIVSSÄKRING ECO HICAP 00/125A GG 500V',
        'KNIVSSÄKRING ECO HICAP 00/160A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/63A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/80A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/100A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/125A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/160A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/200A GG 500V',
        'KNIVSSÄKRING ECO HICAP 1/250A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/100A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/125A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/160A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/200A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/250A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/315A GG 500V',
        'KNIVSSÄKRING ECO HICAP 2/355A GG 500V',
        'KOPPLINGSKNIV 1 KN 1 3ST',
    ]):
        enhet = 'sats' if 'KOPPLINGSKNIV' in namn else 'st'
        _art(conn, namn, kat_kniv, enhet, i)

    # ================================================================
    # KAPSLING (moduler = kapacitet i moduler)
    # ================================================================
    for i, (namn, moduler) in enumerate([
        ('KAPSLING CDC 420 K2', 20),
        ('KAPSLING CDC 440 K3', 40),
        ('KAPSLING CDC 460 K4', 60),
    ]):
        _art(conn, namn, kat_kaps, 'st', i, moduler=moduler)

    # ================================================================
    # KABELSKARVAR
    # ================================================================
    for i, namn in enumerate([
        'KABELSKARV 4-LED 6-50 MM² 1KV',
        'KABELSKARV 1KV AL/CU 50-95MM²',
        'KABELSKARV 1KV AL/CU 95-240MM²',
        'KABELSKARV PXE-SU5-SE01',
        'KABELSKARV LJTM-W-4X035-150',
        'KABELSKARV 1KV 95-240 MM²',
        'AVGRENINGSHYLSA C25-50',
        'ÄNDHÄTTA KALLKRYMP 16-30MM',
        'ÄNDHÄTTA KALLKRYMP 26-49MM',
        'ÄNDHÄTTA KALLKRYMP 46-84MM',
    ]):
        _art(conn, namn, kat_skarv, 'st', i)

    # ================================================================
    # KABELSKYDD OCH RÖR
    # ================================================================
    for i, (namn, enhet) in enumerate([
        ('KABELSKYDD PLANT 125-50',  'm'),
        ('KABELRÖR KORR UDV 160',    'm'),
        ('KABELRÖR UDV 110',         'm'),
        ('RAK-BÖJ 110 SRN',          'st'),
        ('RAK-BÖJ 160 SRN',          'st'),
    ]):
        _art(conn, namn, kat_skydd, enhet, i)

    # ================================================================
    # MÄRKNING
    # ================================================================
    mark_art = (
        [('MÄRKSYST R5000 SIFFRA {} DEKAL'.format(d), 'st') for d in '0123456789'] +
        [('MÄRKLIST TRANSP SKYLTHÅLL PL',    'st')] +
        [('MARKERINGSSTÅNG KSPS 7',           'st')] +
        [('E.ON KABELSKÅPSLOGO KLISTER',      'st')] +
        [('MÄRKSYSTEM H50 GUL SIFFRA {}'.format(d), 'st') for d in '0123456789'] +
        [('MÄRKSYSTEM H50 GUL BOKSTAV {}'.format(c), 'st') for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] +
        [('MÄRKSYSTEM H50 GUL BLANK',         'st')] +
        [('BOTTENPLATTA H50',                  'st')]
    )
    for i, (namn, enhet) in enumerate(mark_art):
        _art(conn, namn, kat_mark, enhet, i)

    # ================================================================
    # ÖVRIGT
    # ================================================================
    for i, (namn, enhet) in enumerate([
        ('HÅRDAD STÅLSPETS FS-11',           'st'),
        ('FRÄMRE RÖR FS-21',                 'st'),
        ('FÖRLÄNGNINGSRÖR FS-31',            'st'),
        ('JORDLINA CCS 25 KAP',              'm'),
        ('JORDTAGSSTÅNG ELPRESS A9522463',   'st'),
        ('KABELSKO KRF 25-12',               'st'),
    ]):
        _art(conn, namn, kat_ovrigt, enhet, i)

    # ================================================================
    # MALLAR (4 stycken)
    # ================================================================
    mallar = [
        (1, 'Kabelförläggning',
         'Schakt och förläggning av markkabel med skyddsrör och kabelskyddsband.'),
        (2, 'Anslutning i kabelskåp',
         'Inkoppling av kabel i befintligt kabelskåp med säkringslastfrånskiljare.'),
        (3, 'Nytt kabelskåp',
         'Installation av ny kapsling/kabelskåp med säkringar och anslutningsdon.'),
        (4, 'Anslutning i nätstation',
         'Inkoppling av kabel inne i nätstation med anslutningsdon.'),
    ]
    for sortering, namn, beskrivning in mallar:
        conn.execute(
            "INSERT OR IGNORE INTO mallar (id, namn, beskrivning, sortering) VALUES (?,?,?,?)",
            (sortering, namn, beskrivning, sortering))

    # ----------------------------------------------------------------
    # Mall 1 – Kabelförläggning
    # ----------------------------------------------------------------
    _mall_falt(conn, 1, [
        ('kabel_artikel_id',        'Kabeltyp',              'artikel_select',
         '{"kategori_namn":"Kablar"}',
         'Välj kabeltyp',                                       1, 1),
        ('kabel_meter',             'Kabellängd (m)',         'number',
         '{"min":1}',
         'Total förlagd sträcka',                               1, 2),
        ('ror_artikel_id',          'Skyddsrörtyp',           'artikel_select',
         '{"kategori_namn":"Kabelskydd och rör","filter":"Kabelrör|Rak-böj"}',
         'Lämna tomt om inget rör',                             0, 3),
        ('ror_meter',               'Skyddsrörlängd (m)',     'number',
         '{"min":0}',
         'Meter skyddsrör',                                     0, 4),
        ('kabelforband_artikel_id', 'Kabelskyddsband',        'artikel_select',
         '{"kategori_namn":"Kabelskydd och rör","filter":"kabelskydd"}',
         'Välj kabelskyddsband',                                0, 5),
        ('kabelforband_meter',      'Kabelskyddsband (m)',    'number',
         '{"min":0}',
         'Meter kabelskyddsband',                               0, 6),
    ])

    # ----------------------------------------------------------------
    # Mall 2 – Anslutning i kabelskåp
    # ----------------------------------------------------------------
    _mall_falt(conn, 2, [
        ('kabelskap_benamning', 'Kabelskåpsbeteckning',        'text',
         '{}',
         'T.ex. KS-42, Storg. 12',                             1, 1),
        ('sakring_artikel_id',  'Säkringsstorlek',             'artikel_select',
         '{"kategori_namn":"Säkringslastfrånskiljare"}',
         'Välj säkring',                                        1, 2),
        ('kabelskor_artikel_id','Anslutningsdon',               'artikel_select',
         '{"kategori_namn":"Anslutningsdon"}',
         'Välj anslutningsdon för kabeldimensionen',            1, 3),
        ('antal_kablar',        'Antal inkommande kablar',      'number',
         '{"min":1,"default":1}',
         'Per inkommande kabel',                                1, 4),
    ])

    # ----------------------------------------------------------------
    # Mall 3 – Nytt kabelskåp
    # ----------------------------------------------------------------
    _mall_falt(conn, 3, [
        ('kabelskap_artikel_id',    'Kapsling (välj ur katalog)', 'artikel_select',
         '{"kategori_namn":"Kapsling"}',
         'Välj kapsling/kabelskåp',                             1, 1),
        ('antal_sakringsfack',      'Antal säkringsfack',         'number',
         '{"min":1}',
         'Aktiva fack med säkring',                             1, 2),
        ('sakring_artikel_id',      'Säkringsstorlek',            'artikel_select',
         '{"kategori_namn":"Säkringslastfrånskiljare"}',
         'En per fack',                                          1, 3),
        ('kabelskor_artikel_id',    'Anslutningsdon',              'artikel_select',
         '{"kategori_namn":"Anslutningsdon"}',
         '4 per fack (3L+N)',                                    1, 4),
        ('inkl_overspanningsskydd', 'Inkl. överspänningsskydd',   'checkbox',
         '{"default":false}',
         'Tillval',                                              0, 5),
    ])

    # ----------------------------------------------------------------
    # Mall 4 – Anslutning i nätstation
    # ----------------------------------------------------------------
    _mall_falt(conn, 4, [
        ('kabel_artikel_id',    'Kabeltyp',                    'artikel_select',
         '{"kategori_namn":"Kablar"}',
         'Välj kabeltyp',                                       1, 1),
        ('kabel_meter',         'Kabellängd inne i station (m)', 'number',
         '{"min":0.5}',
         'Meter kabel i stationen',                             1, 2),
        ('kabelskor_artikel_id','Anslutningsdon',               'artikel_select',
         '{"kategori_namn":"Anslutningsdon"}',
         '4 anslutningsdon (3L+N)',                             1, 3),
        ('antal_genomforingar', 'Antal kabelgenomföringar',     'number',
         '{"min":1,"default":1}',
         'Genomföringar i vägg',                                1, 4),
    ])

    # ================================================================
    # E-nummer (Onninen) för alla artiklar med känt E-nummer
    # ================================================================
    lev_onninen = conn.execute("SELECT id FROM leverantorer WHERE namn='Onninen'").fetchone()['id']
    enr_map = [
        ('ANSLUTNINGSDON ABB ADI 300 ISOLERAT',     'E0732794'),
        ('ANSLUTNINGSDON ABB ADU 300 OISOLERAT',    'E0732796'),
        ('ANSLUTNINGSDON ABB ADI 95 ISOLERAT',      'E0732795'),
        ('ANSLUTNINGSDON ABB ADU 95 OISOLERAT',     'E0732797'),
        ('ANSLUTNINGSDON AD 350',                   'E0732602'),
        ('ANSLUTNINGSDON PEN/PE CUZ 95',            'E0731209'),
        ('ANSLUTNINGSDON PEN/PE CUZ 300',           'E0731210'),
        ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95',  'E0731207'),
        ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300', 'E0731208'),
        ('SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',    'E0732749'),
        ('SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V',   'E0732747'),
        ('SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',     'E0732771'),
        ('SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',     'E0732772'),
        ('SÄKRINGSLASFRÅNSK SLF160P',               'E0733146'),
        ('SÄKRINGSLASFRÅNSK SLF250P',               'E0733147'),
        ('SÄKRINGSLASFRÅNSK SLF400P',               'E0733148'),
        ('SÄKRINGSLASFRÅNSK SLF630P',               'E0733149'),
        ('KNIVSSÄKRING ECO HICAP 000/10A GG 500V',  'E2044104'),
        ('KNIVSSÄKRING ECO HICAP 000/16A GG 500V',  'E2044106'),
        ('KNIVSSÄKRING ECO HICAP 000/25A GG 500V',  'E2044110'),
        ('KNIVSSÄKRING ECO HICAP 000/35A GG 500V',  'E2044114'),
        ('KNIVSSÄKRING ECO HICAP 000/50A GG 500V',  'E2044118'),
        ('KNIVSSÄKRING ECO HICAP 000/63A GG 500V',  'E2044120'),
        ('KNIVSSÄKRING ECO HICAP 000/80A GG 500V',  'E2044122'),
        ('KNIVSSÄKRING ECO HICAP 000/100A GG 500V', 'E2044124'),
        ('KNIVSSÄKRING ECO HICAP 00/125A GG 500V',  'E2044126'),
        ('KNIVSSÄKRING ECO HICAP 00/160A GG 500V',  'E2044128'),
        ('KNIVSSÄKRING ECO HICAP 1/63A GG 500V',   'E2044316'),
        ('KNIVSSÄKRING ECO HICAP 1/80A GG 500V',   'E2044318'),
        ('KNIVSSÄKRING ECO HICAP 1/100A GG 500V',  'E2044320'),
        ('KNIVSSÄKRING ECO HICAP 1/125A GG 500V',  'E2044322'),
        ('KNIVSSÄKRING ECO HICAP 1/160A GG 500V',  'E2044324'),
        ('KNIVSSÄKRING ECO HICAP 1/200A GG 500V',  'E2044326'),
        ('KNIVSSÄKRING ECO HICAP 1/250A GG 500V',  'E2044330'),
        ('KNIVSSÄKRING ECO HICAP 2/100A GG 500V',  'E2044410'),
        ('KNIVSSÄKRING ECO HICAP 2/160A GG 500V',  'E2044414'),
        ('KNIVSSÄKRING ECO HICAP 2/200A GG 500V',  'E2044416'),
        ('KNIVSSÄKRING ECO HICAP 2/250A GG 500V',  'E2044420'),
        ('KNIVSSÄKRING ECO HICAP 2/315A GG 500V',  'E2044422'),
        ('KNIVSSÄKRING ECO HICAP 2/355A GG 500V',  'E2044424'),
        ('KOPPLINGSKNIV 1 KN 1 3ST',               'E0732776'),
        ('KAPSLING CDC 420 K2',  'E0732130'),
        ('KAPSLING CDC 440 K3',  'E0732131'),
        ('KAPSLING CDC 460 K4',  'E0732132'),
        ('KABELSKARV 4-LED 6-50 MM² 1KV',    'E0702026'),
        ('KABELSKARV 1KV AL/CU 50-95MM²',    'E0718322'),
        ('KABELSKARV 1KV AL/CU 95-240MM²',   'E0718323'),
        ('KABELSKARV PXE-SU5-SE01',           'E0702128'),
        ('KABELSKARV LJTM-W-4X035-150',       'E0716209'),
        ('KABELSKARV 1KV 95-240 MM²',         'E0702134'),
        ('AVGRENINGSHYLSA C25-50',            'E0825320'),
        ('ÄNDHÄTTA KALLKRYMP 16-30MM',        'E0714382'),
        ('ÄNDHÄTTA KALLKRYMP 26-49MM',        'E0714383'),
        ('ÄNDHÄTTA KALLKRYMP 46-84MM',        'E0714384'),
        ('KABELSKYDD PLANT 125-50', 'E0663009'),
        ('KABELRÖR KORR UDV 160',   'E0663214'),
        ('KABELRÖR UDV 110',        'E0663206'),
        ('RAK-BÖJ 110 SRN',         'E0663185'),
        ('RAK-BÖJ 160 SRN',         'E0663186'),
        ('MÄRKSYST R5000 SIFFRA 0 DEKAL', 'E2988710'),
        ('MÄRKSYST R5000 SIFFRA 1 DEKAL', 'E2988711'),
        ('MÄRKSYST R5000 SIFFRA 2 DEKAL', 'E2988712'),
        ('MÄRKSYST R5000 SIFFRA 3 DEKAL', 'E2988713'),
        ('MÄRKSYST R5000 SIFFRA 4 DEKAL', 'E2988714'),
        ('MÄRKSYST R5000 SIFFRA 5 DEKAL', 'E2988715'),
        ('MÄRKSYST R5000 SIFFRA 6 DEKAL', 'E2988716'),
        ('MÄRKSYST R5000 SIFFRA 7 DEKAL', 'E2988717'),
        ('MÄRKSYST R5000 SIFFRA 8 DEKAL', 'E2988718'),
        ('MÄRKSYST R5000 SIFFRA 9 DEKAL', 'E2988719'),
        ('MÄRKLIST TRANSP SKYLTHÅLL PL',   'E0668132'),
        ('MARKERINGSSTÅNG KSPS 7',          'E0731094'),
        ('E.ON KABELSKÅPSLOGO KLISTER',     'E992373505'),
        ('HÅRDAD STÅLSPETS FS-11',          'E0632207'),
        ('FRÄMRE RÖR FS-21',                'E0632201'),
        ('FÖRLÄNGNINGSRÖR FS-31',           'E0632233'),
    ]
    for artikelnamn, enr in enr_map:
        art = conn.execute(
            "SELECT id FROM artiklar WHERE artikelnamn=? AND aktiv=1", (artikelnamn,)
        ).fetchone()
        if art:
            conn.execute(
                "INSERT OR IGNORE INTO artikel_leverantor "
                "(artikel_id, leverantor_id, artikelnummer) VALUES (?,?,?)",
                (art['id'], lev_onninen, enr)
            )

    # ================================================================
    # Inställningar
    # ================================================================
    for nyckel, varde in [
        ('foretagsnamn',   'Oneco Networks AB'),
        ('admin_losenord', hashlib.sha256(b'admin').hexdigest()),
        ('logotyptext',    'LÅGSPÄNNINGSBEREDNING'),
        ('db_version',     '19'),
    ]:
        conn.execute("INSERT OR IGNORE INTO installningar (nyckel, varde) VALUES (?,?)",
                     (nyckel, varde))

    # Beredare
    for namn in ['Anna L.', 'Erik S.', 'Maria K.']:
        conn.execute("INSERT OR IGNORE INTO beredare (namn) VALUES (?)", (namn,))


def fyll_egenkontroll(conn):
    """
    Seed egenkontrollpunkter per mall (från Excel Byggprotokoll 1.0).
    INSERT OR IGNORE – säkert att anropa flera gånger.
    """
    # Egenkontroll Kabelskåp (KabelId=1)
    egk_kabelskap = [
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
    ]

    # Egenkontroll Kabelförläggning (KabelId=4)
    egk_kabelforlаggning = [
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
    ]

    # Egenkontroll Nätstation (KabelId=5)
    egk_natstation = [
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
    ]

    egk = {
        1: egk_kabelforlаggning,   # Mall 1 – Kabelförläggning
        2: egk_kabelskap,          # Mall 2 – Anslutning i kabelskåp
        3: egk_kabelskap,          # Mall 3 – Nytt kabelskåp (samma kontroller)
        4: egk_natstation,         # Mall 4 – Anslutning i nätstation
    }

    for mall_id, punkter in egk.items():
        for i, punkt in enumerate(punkter):
            conn.execute(
                "INSERT OR IGNORE INTO mall_egenkontroll (mall_id, punkt, sortering) VALUES (?,?,?)",
                (mall_id, punkt, i)
            )


def fyll_nya_artiklar(conn):
    """Bakåtkompatibilitet – anropas vid migrering från v1. Behålls men migration v15 hanterar allt."""
    pass


def _mall_falt(conn, mall_id, falt):
    for faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering in falt:
        conn.execute(
            "INSERT OR IGNORE INTO mall_inputfalt "
            "(mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering))
