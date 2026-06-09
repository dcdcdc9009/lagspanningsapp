# Beredning-Projektledning

Webbaserat projektlednings- och beredningssystem för elkraftsprojekt (lågspänning 0.4–1 kV).

**Live:** https://beredning-projektledning.up.railway.app
**GitLab:** https://gitlab.com/dcdcdc90/lagspanningsapp

---

## Funktioner

### Projekt
- Skapa, redigera och ta bort projekt
- Lista- och kortvy med sök, fas- och beredare-filter
- Checklista per projekt (38 punkter i 5 grupper: Uppstart, Kartläggning, Handlingar, Tillstånd, Kvalitet)
- Markera checklistepunkter som Utförd eller Ej relevant (båda räknas mot total-procent)
- Fas-hantering med tidslinje och historik
- Aktivitetslogg per projekt
- Tillståndshantering
- Röd flagg vid överskridna fas-trösklar

### Byggprotokoll / Materiallista
- Skapa byggprotokoll per projekt med egenkontroll
- Flera konstruktionstyper med mallar (kabelförläggning, kabelskåp, nätstation m.fl.)
- Automatisk materialberäkning baserat på mall-parametrar
- Exportera Byggprotokoll som PDF (en konstruktion per sida)
- Exportera Materiallista som PDF
- Exportera Materiallista som Excel

### Artiklar
- Artikelregister med kategorier och enheter
- Leverantörspriser per artikel (inkl. E-nummer för Onninen)
- Aktiv/inaktiv-flagga

### Admin
- Hantera beredare, leverantörer och kategorier
- Hantera artiklar med E-nummer
- Hantera egenkontroll-mallar per konstruktionstyp
- Appinställningar

### Säkerhet
- Inloggning krävs för all åtkomst
- Separata lösenord för användare och admin
- Rate limiting: max 5 inloggningsförsök per minut per IP
- Session-timeout: 8 timmar
- Säkra cookie-inställningar (HttpOnly, Secure på Railway)

---

## Teknisk stack

| Del | Teknik |
|-----|--------|
| Backend | Python 3.11, Flask 3.0 |
| Databas | SQLite (WAL-läge, persistent volym på Railway) |
| Frontend | Vanilla JS (SPA), CSS |
| PDF | ReportLab + svglib |
| Excel | Inbyggd xlsx-generering |
| Webbserver | Gunicorn (gthread, 4 trådar) |
| Deploy | Railway (Hobby-plan, $5/mån) |
| Versionskontroll | GitLab |

---

## Projektstruktur

```
lagspanningsapp/
├── backend/
│   ├── app.py              # Flask REST API
│   ├── database.py         # SQLite-schema och init
│   ├── models.py           # Hjälpfunktioner (rows_to_list m.fl.)
│   ├── seed_data.py        # Startdata: artiklar, mallar, priser
│   ├── mall_berakning.py   # Materialberäkning för konstruktionsmallar
│   ├── pdf_generator.py    # PDF-generering (byggprotokoll + materiallista)
│   ├── excel_generator.py  # Excel-export av materiallista
│   └── requirements.txt
├── frontend/
│   ├── index.html          # SPA-skal
│   └── static/
│       ├── app.js          # All frontend-logik (SPA)
│       ├── style.css       # Mörkt tema, responsiv layout
│       └── bg-network.jpg  # Bakgrundsbild (Unsplash, Conny Schneider)
├── data/
│   └── lagspanning.db      # SQLite-databas (lokal dev)
├── wsgi.py                 # Gunicorn-entrypoint
├── Procfile                # Railway deploy-kommando
├── runtime.txt             # python-3.11.9
└── requirements.txt        # Toppnivå (pekar på backend/requirements.txt)
```

---

## Köra lokalt

```bash
cd backend
pip install -r requirements.txt
python app.py
# Öppna http://localhost:5000
```

Standardlösenord: se appinställningar i Admin-fliken.

---

## Deploy till Railway

Appen deployas manuellt med Railway CLI:

```bash
# Sätt token från railway.app/account/tokens
$env:RAILWAY_API_TOKEN="ditt-token-här"

# Pusha till GitLab
git push gitlab master

# Deploya till Railway
railway.exe up --detach
```

### Miljövariabler på Railway

| Variabel | Beskrivning |
|----------|-------------|
| `SECRET_KEY` | Slumpmässig hemlig nyckel för sessioner |
| `DATABASE_PATH` | `/data/lagspanning.db` |

### Persistent lagring

Lägg till en **Volume** på Railway monterad på `/data` — annars nollställs databasen vid varje deploy.

---

## Konstruktionsmallar

| Mall | Beskrivning |
|------|-------------|
| Kabelförläggning | Kabellängd, rörtyp, kabeländetyp |
| Anslutning i kabelskåp | Antal kablar, säkring, kabelskor |
| Nytt kabelskåp | Skåp, säkringsfack, överspänningsskydd |
| Anslutning i nätstation | Kabellängd, genomföringar, kabelskor |

---

## Beredare

| Kod | Namn |
|-----|------|
| DACA | Daniel Carlsson |
| BJNI | Björn Nilsson |
| JIBU | Jimmy Buch |
| ANMA | Antonio Malm |
| RAGR | Rasmus Grahn |
