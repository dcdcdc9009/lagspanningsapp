import sqlite3, os, threading
from contextlib import contextmanager

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'lagspanning.db')
)

# En persistent connection per tråd (undviker open/close-overhead per request)
_local = threading.local()


def _open_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -16000")  # 16 MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


@contextmanager
def get_db():
    """Återanvänder en persistent connection per tråd för att undvika nätverksoverhead."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = _open_conn()
    conn = _local.conn
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        raise


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        _create_tables(conn)
        conn.commit()

        tom = _is_tom(conn)
        if tom:
            from seed_data import fyll_i_startdata
            fyll_i_startdata(conn)
            conn.commit()
        else:
            _migrera(conn)

        from seed_data import fyll_egenkontroll
        fyll_egenkontroll(conn)
        conn.commit()
    finally:
        conn.close()


def _migrera(conn):
    """Kör eventuella databas-migrationer."""
    ver_rad = conn.execute(
        "SELECT varde FROM installningar WHERE nyckel='db_version'"
    ).fetchone()
    v = int(ver_rad['varde']) if ver_rad else 0

    if v < 2:
        conn.execute("DELETE FROM artikel_leverantor")
        from seed_data import fyll_nya_artiklar
        fyll_nya_artiklar(conn)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','2')"
        )
        conn.commit()
        v = 2

    if v < 3:
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN beskrivning TEXT")
        except Exception:
            pass
        conn.execute("""
            DELETE FROM artiklar WHERE id NOT IN (
                SELECT MIN(id) FROM artiklar GROUP BY artikelnamn, kategori_id
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','3')"
        )
        conn.commit()

    if v < 4:
        for namn in ['Kabelskarv PXE-SU5-SE01', 'Kabelskarv LJTM-W-4X035-150']:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','4')"
        )
        conn.commit()

    if v < 5:
        conn.execute(
            "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn='ror_koppling_artikel_id'"
        )
        conn.execute(
            "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn='antal_kabelander'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Kabelskyddsband', hjalp='Välj kabelskyddsband' "
            "WHERE mall_id=1 AND faltnamn='kabelforband_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET alternativ=? "
            "WHERE mall_id=1 AND faltnamn='ror_artikel_id'",
            ('{"kategori_namn":"Rör och skyddsrör","filter":"skyddsrör|kabelrör|Styv PVC|Stålrör"}',)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','5')"
        )
        conn.commit()
        v = 5

    if v < 6:
        ta_bort = [
            'ABB RK 5-fack', 'ABB RK 7-fack', 'ABB RK 10-fack', 'ABB RK 12-fack',
            'ABB Combiflex 4-fack', 'ABB Combiflex 6-fack',
            'Elmeko kabelskåp 4-fack', 'Elmeko kabelskåp 6-fack', 'Elmeko kabelskåp 8-fack',
            'Elmeko kabelskåp 10-fack', 'Elmeko kabelskåp 12-fack',
            'Ensto utomhus 4-fack', 'Ensto utomhus 6-fack',
            'Ensto utomhus 8-fack', 'Ensto utomhus 12-fack',
            'Hager kabelskåp 4-fack', 'Hager kabelskåp 6-fack', 'Hager kabelskåp 8-fack',
            'Schneider Linergy 6-fack', 'Schneider Linergy 12-fack',
            'Pehaka kabelskåp 4-fack', 'Pehaka kabelskåp 6-fack', 'Pehaka kabelskåp 8-fack',
            'Styv PVC-rör Ø50mm', 'Styv PVC-rör Ø63mm',
            'Styv PVC-rör Ø110mm', 'Styv PVC-rör Ø160mm',
            'Stålrör Ø50mm (väggenomföring)', 'Stålrör Ø100mm (väggenomföring)',
            'Rörkoppling Ø50mm', 'Rörkoppling Ø63mm', 'Rörkoppling Ø75mm',
            'Rörkoppling Ø90mm', 'Rörkoppling Ø110mm', 'Rörkoppling Ø160mm',
            'Markeringsband röd', 'Kabelskyddsnät röd', 'Kabelskyddsplatta (grön/svart)',
            'Kabelstege plast 200mm bredd', 'Kabelstege plast 300mm bredd',
            'Kabelsand', 'Betongfundament kabelskåp', 'Silikon och fogmassa',
            'Kabelgenomföring flerfack',
            'Märksystem H50 gul siffra 0-9', 'Märksystem H50 gul bokstav A-Z',
            'Märksystem H50 gul blank', 'Märksystem R5000 siffra 0-9 dekal',
        ]
        for namn in ta_bort:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))

        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Övrigt smågods'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sortering),49) FROM artiklar WHERE kategori_id=?",
                (kat_id,)
            ).fetchone()[0]
            r5000 = [f'Märksystem R5000 siffra {d}' for d in '0123456789'] + \
                    [f'Märksystem R5000 bokstav {c}'
                     for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
            for i, namn in enumerate(r5000):
                conn.execute(
                    "INSERT OR IGNORE INTO artiklar "
                    "(artikelnamn, kategori_id, enhet, sortering) VALUES (?,?,?,?)",
                    (namn, kat_id, 'st', max_sort + 1 + i)
                )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','6')"
        )
        conn.commit()

    if v < 7:
        conn.execute("""
            DELETE FROM artiklar WHERE id NOT IN (
                SELECT MIN(id) FROM artiklar GROUP BY artikelnamn, kategori_id
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','7')"
        )
        conn.commit()

    if v < 8:
        conn.execute(
            "UPDATE mall_inputfalt SET alternativ=? "
            "WHERE mall_id=1 AND faltnamn='kabelforband_artikel_id'",
            ('{"kategori_namn":"Övrigt smågods","filter":"kabelskydd"}',)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','8')"
        )
        conn.commit()

    if v < 9:
        # v9: Korta schaktdjup-texten, lägg till kj.41-punkt i Mall 1
        conn.execute(
            "UPDATE mall_egenkontroll SET punkt='Schaktdjup kontrollerat' "
            "WHERE mall_id=1 AND punkt='Schaktdjup kontrollerat (min 0,7 m för markkabel)'"
        )
        # Lägg till ny punkt sist (högst sortering + 1)
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sortering), 0) FROM mall_egenkontroll WHERE mall_id=1"
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO mall_egenkontroll (mall_id, punkt, sortering) VALUES (?,?,?)",
            (1, 'Förlagt en kj. 41', max_sort + 1)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','9')"
        )
        conn.commit()

    if v < 10:
        # v10: Lägg till meterfält för kabelskyddsband i Mall 1
        conn.execute("""
            INSERT OR IGNORE INTO mall_inputfalt
                (mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering)
            VALUES (1, 'kabelforband_meter', 'Kabelskyddsband (m)', 'number',
                    '{"min":0}', 'Meter kabelskyddsband', 0, 6)
        """)
        # Flytta inkl_kabelsand och inkl_markeringsband ett steg ned
        conn.execute(
            "UPDATE mall_inputfalt SET sortering=7 WHERE mall_id=1 AND faltnamn='inkl_kabelsand'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET sortering=8 WHERE mall_id=1 AND faltnamn='inkl_markeringsband'"
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','10')"
        )
        conn.commit()

    if v < 11:
        # v11: Ta bort punkter 3,4,7,10 och byt namn på punkt 6 i Mall 1
        for punkt in [
            'Kabelns förläggning godkänd av beställaren',
            'Mantelprovning utförd med godkända värden',
            'Kabelskyddsplatta monterad (vid vägkorsning o.d.)',
            'Faslikhet kontrollerad',
        ]:
            conn.execute(
                "DELETE FROM mall_egenkontroll WHERE mall_id=1 AND punkt=?", (punkt,)
            )
        conn.execute(
            "UPDATE mall_egenkontroll SET punkt='Kabelskyddsband utlagt' "
            "WHERE mall_id=1 AND punkt='Markeringsband utlagt'"
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','11')"
        )
        conn.commit()

    if v < 12:
        # v12: Lägg till SLD 00, SLD 000, SLE 1, SLE 2 som separata artiklar.
        # De gamla ihopslagna artiklarna raderas INTE (kan finnas i befintliga byggprotokoll).
        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Säkringslastfrånskiljare'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sortering), 20) FROM artiklar WHERE kategori_id=?",
                (kat_id,)
            ).fetchone()[0]
            for i, namn in enumerate([
                'Säkringslastfrånskiljare SLD 00 500V',
                'Säkringslastfrånskiljare SLD 000 500V',
                'Säkringslastfrånskiljare SLE 1 690V',
                'Säkringslastfrånskiljare SLE 2 690V',
            ]):
                exists = conn.execute(
                    "SELECT 1 FROM artiklar WHERE artikelnamn=? AND kategori_id=?",
                    (namn, kat_id)
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering) "
                        "VALUES (?,?,?,?)",
                        (namn, kat_id, 'st', max_sort + 1 + i)
                    )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','12')"
        )
        conn.commit()

    if v < 13:
        # v13: Fixa typo "Jordfförbindelsemätning", ta bort oanvända checkboxar i Mall 1,
        #      och säkerställ att db_version finns satt
        conn.execute("""
            UPDATE mall_egenkontroll
            SET punkt = REPLACE(punkt, 'Jordfförbindelsemätning', 'Jordförbindelsemätning')
            WHERE punkt LIKE '%Jordfförbindelsemätning%'
        """)
        for falt in ('inkl_kabelsand', 'inkl_markeringsband'):
            conn.execute(
                "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn=?", (falt,)
            )
        # Säkerställ att foretagsnamn-nyckeln är konsekvent (inte foretag_namn)
        rad = conn.execute(
            "SELECT varde FROM installningar WHERE nyckel='foretag_namn'"
        ).fetchone()
        if rad:
            conn.execute(
                "INSERT OR IGNORE INTO installningar (nyckel,varde) VALUES ('foretagsnamn',?)",
                (rad['varde'],)
            )
            conn.execute("DELETE FROM installningar WHERE nyckel='foretag_namn'")
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','13')"
        )
        conn.commit()

    if v < 14:
        # v14: Lägg till konstruktioner-modulen
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN moduler INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        # skapa_tabeller för konstruktioner körs redan via _create_tables
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','14')")
        conn.commit()

    if v < 15:
        # v15: Ersätt alla kategorier och artiklar med Excel-baserade (Byggprotokoll 1.0)
        #      samt uppdatera egenkontroll för alla mallar och inputfält-alternativ.

        # Nullställ artikel_id i rader så FK-constraint inte blockerar radering
        # (artikelnamn bevaras som text i raderna)
        conn.execute("UPDATE byggprotokoll_rader SET artikel_id = NULL")
        conn.execute("UPDATE konstruktion_rader SET artikel_id = NULL")

        # Radera allt befintligt
        conn.execute("DELETE FROM artikel_leverantor")
        conn.execute("DELETE FROM artiklar")
        conn.execute("DELETE FROM kategorier")

        # Radera befintlig egenkontroll för alla mallar
        conn.execute("DELETE FROM mall_egenkontroll")

        # Seeda nya kategorier, artiklar och egenkontroll från Excel
        from seed_data import fyll_i_startdata as _seed, fyll_egenkontroll as _egk
        # Kör bara kategori/artikel-delen (inte mallar/inställningar som redan finns)
        from seed_data import _kat, _art, _lev, _mall_falt

        kat_kabel   = _kat(conn, 'Kablar',                    1)
        kat_ansl    = _kat(conn, 'Anslutningsdon',             2)
        kat_sak     = _kat(conn, 'Säkringslastfrånskiljare',   3)
        kat_kniv    = _kat(conn, 'Knivssäkringar',             4)
        kat_kaps    = _kat(conn, 'Kapsling',                   5)
        kat_skarv   = _kat(conn, 'Kabelskarvar',               6)
        kat_skydd   = _kat(conn, 'Kabelskydd och rör',         7)
        kat_mark    = _kat(conn, 'Märkning',                   8)
        kat_ovrigt  = _kat(conn, 'Övrigt',                     9)

        for i, (namn, enhet) in enumerate([
            ('AML 4G25 1KV SV', 'm'), ('AML 4G50 1KV SV', 'm'),
            ('AML 4G95 1KV SV', 'm'), ('AML 4G150 1KV SV', 'm'),
            ('AML 4G240 1KV SV', 'm'), ('CU-LINA BELAGD 25MM²', 'm'),
        ]):
            _art(conn, namn, kat_kabel, enhet, i)

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
            _art(conn, namn, kat_ansl, 'st', i)

        for i, namn in enumerate([
            'SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',
            'SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V',
            'SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',
            'SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',
            'SÄKRINGSLASFRÅNSK SLF160P',
            'SÄKRINGSLASFRÅNSK SLF250P',
            'SÄKRINGSLASFRÅNSK SLF400P',
            'SÄKRINGSLASFRÅNSK SLF630P',
        ]):
            _art(conn, namn, kat_sak, 'st', i)

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

        for i, (namn, moduler) in enumerate([
            ('KAPSLING CDC 420 K2', 20),
            ('KAPSLING CDC 440 K3', 40),
            ('KAPSLING CDC 460 K4', 60),
        ]):
            _art(conn, namn, kat_kaps, 'st', i, moduler=moduler)

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

        for i, (namn, enhet) in enumerate([
            ('KABELSKYDD PLANT 125-50', 'm'),
            ('KABELRÖR KORR UDV 160',   'm'),
            ('KABELRÖR UDV 110',         'm'),
            ('RAK-BÖJ 110 SRN',          'st'),
            ('RAK-BÖJ 160 SRN',          'st'),
        ]):
            _art(conn, namn, kat_skydd, enhet, i)

        mark_art = (
            [('MÄRKSYST R5000 SIFFRA {} DEKAL'.format(d), 'st') for d in '0123456789'] +
            [('MÄRKLIST TRANSP SKYLTHÅLL PL', 'st'), ('MARKERINGSSTÅNG KSPS 7', 'st'),
             ('E.ON KABELSKÅPSLOGO KLISTER', 'st')] +
            [('MÄRKSYSTEM H50 GUL SIFFRA {}'.format(d), 'st') for d in '0123456789'] +
            [('MÄRKSYSTEM H50 GUL BOKSTAV {}'.format(c), 'st') for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] +
            [('MÄRKSYSTEM H50 GUL BLANK', 'st'), ('BOTTENPLATTA H50', 'st')]
        )
        for i, (namn, enhet) in enumerate(mark_art):
            _art(conn, namn, kat_mark, enhet, i)

        for i, (namn, enhet) in enumerate([
            ('HÅRDAD STÅLSPETS FS-11', 'st'), ('FRÄMRE RÖR FS-21', 'st'),
            ('FÖRLÄNGNINGSRÖR FS-31', 'st'), ('JORDLINA CCS 25 KAP', 'm'),
            ('JORDTAGSSTÅNG ELPRESS A9522463', 'st'), ('KABELSKO KRF 25-12', 'st'),
        ]):
            _art(conn, namn, kat_ovrigt, enhet, i)

        # Säkerställ att alla 4 mallar finns (kan saknas på extremt gamla installationer)
        for mid, namn in [(1,'Kabelförläggning'),(2,'Anslutning i kabelskåp'),
                          (3,'Nytt kabelskåp'),(4,'Anslutning i nätstation')]:
            conn.execute(
                "INSERT OR IGNORE INTO mallar (id,namn,beskrivning,sortering) VALUES (?,?,?,?)",
                (mid, namn, '', mid))

        # Seeda ny egenkontroll
        _egk(conn)

        # Uppdatera mall_inputfalt alternativ-JSON till nya kategorier
        upd = [
            (1, 'kabel_artikel_id',
             '{"kategori_namn":"Kablar"}'),
            (1, 'ror_artikel_id',
             '{"kategori_namn":"Kabelskydd och rör","filter":"Kabelrör|Rak-böj"}'),
            (1, 'kabelforband_artikel_id',
             '{"kategori_namn":"Kabelskydd och rör","filter":"kabelskydd"}'),
            (2, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
            (3, 'kabelskap_artikel_id',
             '{"kategori_namn":"Kapsling"}'),
            (3, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
            (4, 'kabel_artikel_id',
             '{"kategori_namn":"Kablar"}'),
            (4, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
        ]
        for mid, faltnamn, alternativ in upd:
            conn.execute(
                "UPDATE mall_inputfalt SET alternativ=? WHERE mall_id=? AND faltnamn=?",
                (alternativ, mid, faltnamn))

        # Uppdatera etikett för mall 2/3 kabelskor → anslutningsdon
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Anslutningsdon' WHERE faltnamn='kabelskor_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Kapsling (välj ur katalog)' "
            "WHERE mall_id=3 AND faltnamn='kabelskap_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET hjalp='4 anslutningsdon (3L+N)' "
            "WHERE mall_id=4 AND faltnamn='kabelskor_artikel_id'"
        )

        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','15')")
        conn.commit()

    if v < 16:
        # v16: Sätt moduler för anslutningsdon (-1) och säkringslastfrånskiljare (-3/-4)
        modul_map = {
            'ANSLUTNINGSDON ABB ADI 300 ISOLERAT':     -1,
            'ANSLUTNINGSDON ABB ADU 300 OISOLERAT':    -1,
            'ANSLUTNINGSDON ABB ADI 95 ISOLERAT':      -1,
            'ANSLUTNINGSDON ABB ADU 95 OISOLERAT':     -1,
            'ANSLUTNINGSDON AD 350':                   -1,
            'ANSLUTNINGSDON PEN/PE CUZ 95':            -1,
            'ANSLUTNINGSDON PEN/PE CUZ 300':           -1,
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95':  -1,
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300': -1,
            'SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V':    -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V':   -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V':     -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V':     -3,
            'SÄKRINGSLASFRÅNSK SLF160P':               -4,
            'SÄKRINGSLASFRÅNSK SLF250P':               -4,
            'SÄKRINGSLASFRÅNSK SLF400P':               -4,
            'SÄKRINGSLASFRÅNSK SLF630P':               -4,
        }
        for namn, moduler in modul_map.items():
            conn.execute(
                "UPDATE artiklar SET moduler=? WHERE artikelnamn=? AND moduler=0",
                (moduler, namn)
            )
            conn.execute(
                "UPDATE konstruktion_rader SET moduler=? WHERE artikelnamn=? AND moduler=0",
                (moduler, namn)
            )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','16')")
        conn.commit()


    if v < 17:
        # v17: Lägg till AML 4G10 1KV SV som kabel
        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Kablar'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            exists = conn.execute(
                "SELECT 1 FROM artiklar WHERE artikelnamn='AML 4G10 1KV SV' AND kategori_id=?",
                (kat_id,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering) "
                    "VALUES ('AML 4G10 1KV SV', ?, 'm', -1)",
                    (kat_id,)
                )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','17')")
        conn.commit()

    if v < 18:
        # v18: Lägg till E-nummer (artikelnummer) från Byggprotokoll 1.0.xlsm för Onninen
        conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES ('Onninen')")
        lev = conn.execute("SELECT id FROM leverantorer WHERE namn='Onninen'").fetchone()
        if lev:
            lev_id = lev['id']
            enr_map = [
                # Anslutningsdon
                ('ANSLUTNINGSDON ABB ADI 300 ISOLERAT',     'E0732794'),
                ('ANSLUTNINGSDON ABB ADU 300 OISOLERAT',    'E0732796'),
                ('ANSLUTNINGSDON ABB ADI 95 ISOLERAT',      'E0732795'),
                ('ANSLUTNINGSDON ABB ADU 95 OISOLERAT',     'E0732797'),
                ('ANSLUTNINGSDON AD 350',                   'E0732602'),
                ('ANSLUTNINGSDON PEN/PE CUZ 95',            'E0731209'),
                ('ANSLUTNINGSDON PEN/PE CUZ 300',           'E0731210'),
                ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95',  'E0731207'),
                ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300', 'E0731208'),
                # Säkringslastfrånskiljare
                ('SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',    'E0732749'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V',   'E0732747'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',     'E0732771'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',     'E0732772'),
                ('SÄKRINGSLASFRÅNSK SLF160P',               'E0733146'),
                ('SÄKRINGSLASFRÅNSK SLF250P',               'E0733147'),
                ('SÄKRINGSLASFRÅNSK SLF400P',               'E0733148'),
                ('SÄKRINGSLASFRÅNSK SLF630P',               'E0733149'),
                # Knivssäkringar
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
                # Kapsling
                ('KAPSLING CDC 420 K2',  'E0732130'),
                ('KAPSLING CDC 440 K3',  'E0732131'),
                ('KAPSLING CDC 460 K4',  'E0732132'),
                # Kabelskarvar
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
                # Kabelskydd och rör
                ('KABELSKYDD PLANT 125-50', 'E0663009'),
                ('KABELRÖR KORR UDV 160',   'E0663214'),
                ('KABELRÖR UDV 110',        'E0663206'),
                ('RAK-BÖJ 110 SRN',         'E0663185'),
                ('RAK-BÖJ 160 SRN',         'E0663186'),
                # Märkning
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
                # Övrigt
                ('HÅRDAD STÅLSPETS FS-11',          'E0632207'),
                ('FRÄMRE RÖR FS-21',                'E0632201'),
                ('FÖRLÄNGNINGSRÖR FS-31',           'E0632233'),
            ]
            for artikelnamn, enr in enr_map:
                art = conn.execute(
                    "SELECT id FROM artiklar WHERE artikelnamn=? AND aktiv=1",
                    (artikelnamn,)
                ).fetchone()
                if art:
                    conn.execute(
                        "INSERT INTO artikel_leverantor (artikel_id, leverantor_id, artikelnummer) "
                        "VALUES (?,?,?) "
                        "ON CONFLICT(artikel_id, leverantor_id) DO UPDATE SET artikelnummer=excluded.artikelnummer",
                        (art['id'], lev_id, enr)
                    )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','18')")
        conn.commit()

    if v < 19:
        try:
            conn.execute("ALTER TABLE konstruktioner ADD COLUMN projekt_id INTEGER REFERENCES projekt(id)")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','19')")
        conn.commit()

    if v < 20:
        for kolumn in (
            "ALTER TABLE projekt ADD COLUMN kund TEXT",
            "ALTER TABLE projekt ADD COLUMN anslutningspunkt TEXT",
            "ALTER TABLE projekt ADD COLUMN fas TEXT",
        ):
            try:
                conn.execute(kolumn)
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_fas_datum (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                fas         TEXT NOT NULL,
                startdatum  DATE NOT NULL,
                slutdatum   DATE,
                skapad      DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_tillstand (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                namn        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'Inväntas',
                datum       DATE,
                anteckning  TEXT,
                skapad      DATETIME NOT NULL,
                uppdaterad  DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_aktiviteter (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                tidpunkt    DATETIME NOT NULL,
                typ         TEXT NOT NULL DEFAULT 'anteckning',
                beskrivning TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','20')")
        conn.commit()

    if v < 21:
        for kolumn in (
            "ALTER TABLE projekt ADD COLUMN ib_nummer TEXT",
            "ALTER TABLE projekt ADD COLUMN kategori TEXT",
            "ALTER TABLE projekt ADD COLUMN tilldelat_till TEXT",
            "ALTER TABLE projekt ADD COLUMN omrade TEXT",
            "ALTER TABLE projekt ADD COLUMN inkommande_bestallningar TEXT",
            "ALTER TABLE projekt ADD COLUMN bekraftade_bestallningar TEXT",
            "ALTER TABLE projekt ADD COLUMN beredning_start DATE",
            "ALTER TABLE projekt ADD COLUMN beredning_slut DATE",
        ):
            try:
                conn.execute(kolumn)
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_checklistor (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                item_nr    INTEGER NOT NULL,
                utford     INTEGER NOT NULL DEFAULT 0,
                UNIQUE(projekt_id, item_nr)
            )
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','21')")
        conn.commit()

    if v < 22:
        try:
            conn.execute("ALTER TABLE projekt_checklistor ADD COLUMN ej_relevant INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','22')")
        conn.commit()

    if v < 23:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projekt_budget (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id        INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                budget_typ        TEXT NOT NULL,
                beskrivning       TEXT,
                budgeterat_belopp REAL NOT NULL DEFAULT 0,
                skapad            DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projekt_kostnad (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                budget_typ  TEXT NOT NULL,
                beskrivning TEXT,
                leverantor  TEXT,
                belopp      REAL NOT NULL DEFAULT 0,
                datum       DATE,
                faktura_nr  TEXT,
                skapad      DATETIME NOT NULL
            );
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','23')")
        conn.commit()


def _create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS installningar (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nyckel  TEXT UNIQUE NOT NULL,
            varde   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS beredare (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            namn    TEXT UNIQUE NOT NULL,
            aktiv   INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS kategorier (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            namn      TEXT UNIQUE NOT NULL,
            sortering INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS leverantorer (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            namn  TEXT UNIQUE NOT NULL,
            aktiv INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS artiklar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            artikelnamn TEXT NOT NULL,
            kategori_id INTEGER NOT NULL REFERENCES kategorier(id),
            enhet       TEXT NOT NULL,
            beskrivning TEXT,
            sortering   INTEGER NOT NULL DEFAULT 0,
            aktiv       INTEGER NOT NULL DEFAULT 1,
            moduler     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS artikel_leverantor (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            artikel_id    INTEGER NOT NULL REFERENCES artiklar(id) ON DELETE CASCADE,
            leverantor_id INTEGER NOT NULL REFERENCES leverantorer(id),
            artikelnummer TEXT,
            a_pris        REAL,
            UNIQUE(artikel_id, leverantor_id)
        );

        CREATE TABLE IF NOT EXISTS projekt (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            projektnummer    TEXT UNIQUE NOT NULL,
            projektnamn      TEXT NOT NULL,
            beredare         TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'Planerat'
                             CHECK(status IN ('Planerat','Pågående','Klart')),
            startdatum       DATE,
            anteckningar     TEXT,
            kund             TEXT,
            anslutningspunkt TEXT,
            fas              TEXT,
            ib_nummer            TEXT,
            kategori             TEXT,
            tilldelat_till       TEXT,
            omrade               TEXT,
            inkommande_bestallningar TEXT,
            bekraftade_bestallningar TEXT,
            beredning_start      DATE,
            beredning_slut       DATE,
            skapad           DATETIME NOT NULL,
            uppdaterad       DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mallar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            namn        TEXT NOT NULL,
            beskrivning TEXT,
            sortering   INTEGER NOT NULL DEFAULT 0,
            aktiv       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS mall_inputfalt (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id) ON DELETE CASCADE,
            faltnamn    TEXT NOT NULL,
            etikett     TEXT NOT NULL,
            typ         TEXT NOT NULL DEFAULT 'number',
            alternativ  TEXT,
            hjalp       TEXT,
            obligatorisk INTEGER NOT NULL DEFAULT 1,
            sortering   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS mall_egenkontroll (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id) ON DELETE CASCADE,
            punkt       TEXT NOT NULL,
            sortering   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(mall_id, punkt)
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id),
            mall_namn   TEXT NOT NULL,
            inputdata   TEXT NOT NULL DEFAULT '{}',
            anteckningar TEXT,
            status      TEXT NOT NULL DEFAULT 'Utkast',
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll_rader (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            protokoll_id    INTEGER NOT NULL REFERENCES byggprotokoll(id) ON DELETE CASCADE,
            artikel_id      INTEGER REFERENCES artiklar(id),
            artikelnamn     TEXT NOT NULL,
            kategori        TEXT,
            enhet           TEXT NOT NULL,
            antal           REAL NOT NULL,
            leverantor_id   INTEGER REFERENCES leverantorer(id),
            leverantor_namn TEXT,
            artikelnummer   TEXT,
            a_pris          REAL,
            anteckning      TEXT,
            manuell         INTEGER NOT NULL DEFAULT 0,
            sortering       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll_egenkontroll (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            protokoll_id    INTEGER NOT NULL REFERENCES byggprotokoll(id) ON DELETE CASCADE,
            punkt           TEXT NOT NULL,
            utford          INTEGER NOT NULL DEFAULT 0,
            ej_relevant     INTEGER NOT NULL DEFAULT 0,
            sortering       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS konstruktioner (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER REFERENCES projekt(id),
            typ         TEXT NOT NULL,
            byggnr      TEXT,
            namn        TEXT NOT NULL,
            fri_id      TEXT,
            anmarkning  TEXT,
            status      TEXT NOT NULL DEFAULT 'Pågående',
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS konstruktion_rader (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            konstruktion_id   INTEGER NOT NULL REFERENCES konstruktioner(id) ON DELETE CASCADE,
            artikel_id        INTEGER REFERENCES artiklar(id),
            artikelnamn       TEXT NOT NULL,
            enhet             TEXT NOT NULL,
            antal             REAL NOT NULL DEFAULT 1,
            moduler           INTEGER NOT NULL DEFAULT 0,
            anteckning        TEXT,
            sortering         INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS konstruktion_egenkontroll (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            konstruktion_id   INTEGER NOT NULL REFERENCES konstruktioner(id) ON DELETE CASCADE,
            punkt             TEXT NOT NULL,
            utford            INTEGER NOT NULL DEFAULT 0,
            ej_relevant       INTEGER NOT NULL DEFAULT 0,
            sortering         INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS projekt_fas_datum (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            fas         TEXT NOT NULL,
            startdatum  DATE NOT NULL,
            slutdatum   DATE,
            skapad      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_tillstand (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            namn        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Inväntas',
            datum       DATE,
            anteckning  TEXT,
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_aktiviteter (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            tidpunkt    DATETIME NOT NULL,
            typ         TEXT NOT NULL DEFAULT 'anteckning',
            beskrivning TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_checklistor (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            item_nr     INTEGER NOT NULL,
            utford      INTEGER NOT NULL DEFAULT 0,
            ej_relevant INTEGER NOT NULL DEFAULT 0,
            UNIQUE(projekt_id, item_nr)
        );

        CREATE TABLE IF NOT EXISTS projekt_budget (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id        INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            budget_typ        TEXT NOT NULL,
            beskrivning       TEXT,
            budgeterat_belopp REAL NOT NULL DEFAULT 0,
            skapad            DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_kostnad (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            budget_typ  TEXT NOT NULL,
            beskrivning TEXT,
            leverantor  TEXT,
            belopp      REAL NOT NULL DEFAULT 0,
            datum       DATE,
            faktura_nr  TEXT,
            skapad      DATETIME NOT NULL
        );
    """)


def _is_tom(conn):
    return conn.execute("SELECT COUNT(*) FROM artiklar").fetchone()[0] == 0


if __name__ == '__main__':
    init_db()
    print(f"Databas initierad: {os.path.abspath(DB_PATH)}")
