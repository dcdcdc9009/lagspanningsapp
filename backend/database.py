import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'lagspanning.db')
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    try:
        _create_tables(conn)
        conn.commit()

        tom = _is_tom(conn)
        if tom:
            # Helt ny databas – fyll allt
            from seed_data import fyll_i_startdata
            fyll_i_startdata(conn)
            conn.commit()
        else:
            # Befintlig databas – kör migrationer + nya artiklar
            _migrera(conn)

        # Alltid: säkerställ egenkontroll-data för alla mallar
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
        # v2: Ta bort alla priser, lägg till nya artiklar
        conn.execute("DELETE FROM artikel_leverantor")
        from seed_data import fyll_nya_artiklar
        fyll_nya_artiklar(conn)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','2')"
        )
        conn.commit()
        v = 2

    if v < 3:
        # v3: Lägg till beskrivning-kolumn, ta bort eventuella dubletter
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN beskrivning TEXT")
        except Exception:
            pass  # Kolumnen finns redan
        # Ta bort dubletter – behåll lägst id per (artikelnamn, kategori_id)
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
        # v4: Ta bort mellanspänningsprodukter (PXE- och LJTM-kabelskarvar)
        for namn in ['Kabelskarv PXE-SU5-SE01', 'Kabelskarv LJTM-W-4X035-150']:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','4')"
        )
        conn.commit()

    if v < 5:
        # v5: Uppdatera Mall 1 – ta bort rörkopplingstyp & antal kabeländar,
        #     byt etikett på kabelförband, lägg till filter på skyddsrör
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
        # v6: Ta bort ej relevanta artiklar, lägg till R5000 per siffra/bokstav
        ta_bort = [
            # Kabelskåp
            'ABB RK 5-fack', 'ABB RK 7-fack', 'ABB RK 10-fack', 'ABB RK 12-fack',
            'ABB Combiflex 4-fack', 'ABB Combiflex 6-fack',
            'Elmeko kabelskåp 4-fack', 'Elmeko kabelskåp 6-fack', 'Elmeko kabelskåp 8-fack',
            'Elmeko kabelskåp 10-fack', 'Elmeko kabelskåp 12-fack',
            'Ensto utomhus 4-fack', 'Ensto utomhus 6-fack',
            'Ensto utomhus 8-fack', 'Ensto utomhus 12-fack',
            'Hager kabelskåp 4-fack', 'Hager kabelskåp 6-fack', 'Hager kabelskåp 8-fack',
            'Schneider Linergy 6-fack', 'Schneider Linergy 12-fack',
            'Pehaka kabelskåp 4-fack', 'Pehaka kabelskåp 6-fack', 'Pehaka kabelskåp 8-fack',
            # Rör
            'Styv PVC-rör Ø50mm', 'Styv PVC-rör Ø63mm',
            'Styv PVC-rör Ø110mm', 'Styv PVC-rör Ø160mm',
            'Stålrör Ø50mm (väggenomföring)', 'Stålrör Ø100mm (väggenomföring)',
            # Rörkopplingar
            'Rörkoppling Ø50mm', 'Rörkoppling Ø63mm', 'Rörkoppling Ø75mm',
            'Rörkoppling Ø90mm', 'Rörkoppling Ø110mm', 'Rörkoppling Ø160mm',
            # Övrigt
            'Markeringsband röd', 'Kabelskyddsnät röd', 'Kabelskyddsplatta (grön/svart)',
            'Kabelstege plast 200mm bredd', 'Kabelstege plast 300mm bredd',
            'Kabelsand', 'Betongfundament kabelskåp', 'Silikon och fogmassa',
            'Kabelgenomföring flerfack',
            'Märksystem H50 gul siffra 0-9', 'Märksystem H50 gul bokstav A-Z',
            'Märksystem H50 gul blank', 'Märksystem R5000 siffra 0-9 dekal',
        ]
        for namn in ta_bort:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))

        # Lägg till R5000 per siffra och bokstav
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
            aktiv       INTEGER NOT NULL DEFAULT 1
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
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            projektnummer TEXT UNIQUE NOT NULL,
            projektnamn   TEXT NOT NULL,
            beredare      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'Planerat'
                          CHECK(status IN ('Planerat','Pågående','Klart')),
            startdatum    DATE,
            anteckningar  TEXT,
            skapad        DATETIME NOT NULL,
            uppdaterad    DATETIME NOT NULL
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
    """)


def _is_tom(conn):
    return conn.execute("SELECT COUNT(*) FROM artiklar").fetchone()[0] == 0


if __name__ == '__main__':
    init_db()
    print(f"Databas initierad: {os.path.abspath(DB_PATH)}")
