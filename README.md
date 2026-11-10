# Support-Agent

Handige applicatie die mij helpt: een webapp in Docker op een Debian-server die
teksten verwerkt volgens een **Vibe-skill** (vertalen/verbeteren EN/DE/NL), aangeroepen
vanuit een **Windows tray-applicatie** met een sneltoets — zoals DeepL, maar dan met
je eigen skills.

```
Windows PC (tray-app)                         Debian server (Docker)
┌────────────────────────┐   HTTPS + API-key  ┌──────────────────────────────┐
│ Ctrl+Shift+T           │ ─────────────────▶ │ Caddy (TLS, Let's Encrypt)   │
│ selectie → POST        │   POST /api/process│ ┌──────────────────────────┐ │
│ /api/process           │ ◀───────────────── │ │ FastAPI-app              │ │
│ pop-up + klembord      │   {"result": ...}  │ │  skills/*.md → Mistral   │ │
└────────────────────────┘                    │ └──────────────────────────┘ │
                                              └──────────────────────────────┘
```

## Server (Debian) installeren

Vereisten: Docker + Docker Compose plugin, een domeinnaam met DNS A-record naar het
openbare IP van de server, en poorten 80/443 open/forwarded.

```bash
git clone https://github.com/WesRosss/Support-Agent.git
cd Support-Agent
cp .env.example .env
# vul in .env: DOMAIN, APP_API_KEY (openssl rand -hex 32), MISTRAL_API_KEY, MISTRAL_MODEL
docker compose up -d --build
```

Caddy regelt automatisch een HTTPS-certificaat (Let's Encrypt) voor `DOMAIN`.
De app zelf is alleen bereikbaar via Caddy en vereist altijd de header `X-API-Key`.

Controle:

```bash
curl https://JOUW-DOMEIN/health
curl -H "X-API-Key: $APP_API_KEY" https://JOUW-DOMEIN/api/skills
```

## Skills

Skills zijn gewone `.md`-bestanden in [`skills/`](skills/) (frontmatter met `name`,
optioneel `id`, `description`; de body is de system prompt). Zie
[`skills/README.md`](skills/README.md) voor het formaat en een TOPdesk-voorbeeld.

Nieuwe/zm skill toevoegen: bestand in `skills/` plaatsen, daarna
`curl -X POST https://JOUW-DOMEIN/api/skills/reload -H "X-API-Key: $APP_API_KEY"`
of `docker compose restart app`. Omdat skills lokaal als `.md` staan, werkt de app
met elk Vibe-account: kopieer de skill-body uit dat account naar een `.md`-bestand.

## API

Alle `/api/*` endpoints vereisen header `X-API-Key: <APP_API_KEY>`.

| Endpoint | Beschrijving |
|---|---|
| `GET /health` | healthcheck (geen key nodig) |
| `GET /api/skills` | lijst van beschikbare skills (naam/id/description) |
| `POST /api/skills/reload` | skills opnieuw laden uit `skills/` |
| `POST /api/process` | tekst verwerken volgens een skill |
| `GET /api/log?limit=200` | laatste serverlog-regels |

`POST /api/process`:

```json
{
  "skill": "support-communication",
  "text": "Hello, the system is not working well",
  "target_language": "nl",
  "source_language": "auto",
  "extra": "optionele extra context voor de skill"
}
```

- `skill`: naam of id van een `.md`-skill (de Windows-client stuurt de naam mee)
- `target_language` / `source_language`: `nl`, `en` of `de` (`source_language` mag `auto`)
- `extra`: vrije tekst die als extra context in de prompt mee gaat

Response: `{"result": "...", "skill": "...", "target_language": "...", "source_language": "...", "model": "...", "duration_ms": 123}`

Fouten: `401` ongeldige/ontbrekende key, `404` onbekende skill, `422` ongeldige invoer, `502` Mistral-fout.

Voorbeeld:

```bash
curl -X POST https://JOUW-DOMEIN/api/process \
  -H "X-API-Key: $APP_API_KEY" -H "Content-Type: application/json" \
  -d '{"skill":"support-communication","text":"Hello, the system is not working well","target_language":"nl"}'
```

## Windows-client

Zie [`windows-client/README.md`](windows-client/README.md): tray-icoon met menu
(skill, doeltaal, log, instellingen), sneltoets `Ctrl+Shift+T` kopieert de selectie
en stuurt deze naar de server, resultaat staat direct op het klembord en in een
pop-up waarmee je een andere taal (NL/EN/DE) of extra info kunt kiezen.

Taalkeuze: bij `auto` wordt de invoertaal gedetecteerd; is de invoer Nederlands, dan
gaat het naar de laatst gebruikte andere taal (standaard EN); bij EN/DE-invoer
standaard naar NL.

## Ontwikkelen

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q          # server tests (Mistral wordt gemockt)
docker compose config               # valideer compose-bestand
```

## Beveiliging

- `.env` staat in `.gitignore` en bevat de sleutels — nooit committen.
- HTTPS via Caddy/Let's Encrypt; de app draait niet los op een poort.
- Elke `/api/*` aanroep vereist `X-API-Key` (constant-time compare).
