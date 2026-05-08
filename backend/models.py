from datetime import datetime


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def nu():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def nasta_projektnummer(conn):
    ar = datetime.now().year
    prefix = f"{ar}-"
    rad = conn.execute(
        "SELECT projektnummer FROM projekt WHERE projektnummer LIKE ? ORDER BY projektnummer DESC LIMIT 1",
        (prefix + '%',)
    ).fetchone()
    lopnummer = int(rad['projektnummer'].split('-')[1]) + 1 if rad else 1
    return f"{ar}-{lopnummer:04d}"
