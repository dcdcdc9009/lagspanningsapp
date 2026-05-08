# Lågspänningsberedningssystem

Webbaserat beredningssystem för lågspänningsarbeten (0.4–1 kV).

## Lokalt (dev)

```bash
cd backend
pip install -r requirements.txt
python app.py
# Öppna http://localhost:5000
```

Standardlösenord för Admin-fliken: **admin**

## Deploy till Railway (gratis)

1. Skapa konto på [railway.app](https://railway.app)
2. Skjut upp koden till GitHub (se nedan)
3. "New Project" → "Deploy from GitHub repo" → välj `lagspanningsapp`
4. Railway detekterar `Procfile` och driftsätter automatiskt
5. Lägg till miljövariabler under **Variables**:
   - `SECRET_KEY` = `<valfri lång slumpsträng>`
   - `DATABASE_PATH` = `/data/lagspanning.db`
6. Lägg till en **Volume** (persistent disk) monterad på `/data`
7. Appens URL visas under **Settings → Domains**

## Skjuta upp till GitHub

```bash
cd "C:\Users\Danie\Desktop\Claude\lagspanningsapp"

# Skapa repo på github.com/new (namn: lagspanningsapp, public)
git remote add origin https://github.com/DITT_ANVÄNDARNAMN/lagspanningsapp.git
git push -u origin master
```

## Projektstruktur

```
lagspanningsapp/
  backend/
    app.py            # Flask API (~550 rader)
    database.py       # SQLite-schema + init
    seed_data.py      # Startdata: 145 artiklar, 4 mallar, priser
    mall_berakning.py # Beräkningslogik mall 1-4
    pdf_generator.py  # PDF: byggprotokoll + materiallista
    models.py         # Hjälpfunktioner
    requirements.txt
  frontend/
    index.html        # SPA-skal
    static/
      style.css       # ~550 rader
      app.js          # SPA ~850 rader
  wsgi.py             # Gunicorn-entrypoint
  Procfile            # Railway/Render
  runtime.txt         # python-3.11.9
```

## Mallar

| # | Mall | Nyckelparametrar |
|---|------|-----------------|
| 1 | Kabelförläggning | kabellängd, rör, kabelände-typ |
| 2 | Anslutning i kabelskåp | antal kablar, säkring, kabelskor |
| 3 | Nytt kabelskåp | skåp, säkringsfack, överspänningsskydd |
| 4 | Anslutning i nätstation | kabellängd, genomföringar, kabelskor |
