# Support-Agent Windows-client

Tray-applicatie voor Windows. Met de sneltoets (standaard **Ctrl+Shift+T**) wordt de
geselecteerde tekst naar de Support-Agent webapp gestuurd; het resultaat verschijnt in
een pop-up en staat direct op het klembord.

## Installeren ( development )

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python support_agent.py
```

Bij de eerste start wordt een config aangemaakt in `%APPDATA%\SupportAgent\config.json`.
Vul daar in:

```json
{
  "server_url": "https://app.jouwdomein.nl",
  "api_key": "APP_API_KEY-uit-jouw-.env",
  "skill": "support-communication",
  "target_language": "auto",
  "last_used_language": "en",
  "extra": "",
  "hotkey": "ctrl+shift+t"
}
```

- `server_url` / `api_key`: zelfde waarden als `DOMAIN` en `APP_API_KEY` op de server.
- `skill`: naam van een skill uit `skills/` op de server (zie `GET /api/skills`).
- `target_language`: `auto`, `nl`, `en` of `de`. Bij `auto` wordt de invoertaal
  gedetecteerd: Nederlandse invoer gaat naar de laatst gebruikte andere taal
  (`last_used_language`, standaard `en`); Engelse/Duitse invoer gaat naar `nl`.
- `extra`: standaard extra informatie die bij elke aanroep mee gaat (in de pop-up
  aan te passen).
- `hotkey`: globale sneltoets (bijv. `ctrl+shift+t`). Start de app eventueel als
  administrator als de sneltoets niet reageert.

## Testen op Ubuntu/Linux (CLI-modus)

De tray-app zelf draait alleen op Windows, maar de hele keten — taaldetectie,
server-aanroep, skill, resultaat — test je op Ubuntu met de CLI-modus:

```bash
# 1. Server lokaal draaien (zonder Docker kan ook):
cd ..
pip install -r requirements.txt
APP_API_KEY=test-key MISTRAL_API_KEY=<jouw-mistral-key> \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# (met Docker: .env met DOMAIN=localhost -> docker compose up -d --build,
#  dan --server https://localhost)

# 2. Client in CLI-modus:
cd windows-client
pip install requests pyperclip        # pystray/pillow/keyboard/tkinter zijn hier niet nodig
python support_agent.py --cli "Ichliebe meinem frau" --server http://127.0.0.1:8000 --api-key test-key
# doeltaal forceren:
python support_agent.py --cli "Hello, the system is not working well" --server http://127.0.0.1:8000 --api-key test-key --target nl
# tekst via stdin:
echo "Hallo wereld, hoe gaat het met je?" | python support_agent.py --cli - --server http://127.0.0.1:8000 --api-key test-key
```

Bij `auto` detecteert de client de invoer (NL → laatst gebruikte andere taal, EN/DE → NL).
Op een headless Ubuntu zonder klembord-backend print de CLI alleen het resultaat;
installeer `xclip` (`sudo apt install xclip`) als je het klembord wilt testen.

## Als .exe bouwen (PyInstaller)

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name SupportAgent support_agent.py
# resultaat: dist\SupportAgent.exe
```

Plaats daarna `config.json` in `%APPDATA%\SupportAgent\` (wordt anders automatisch
aangemaakt met placeholder-waarden). Logbestand: `%APPDATA%\SupportAgent\support-agent.log`.

## Tray-menu

- **Vertaal selectie** — zelfde als de sneltoets.
- **Skill** — radio-menu met alle skills van de server.
- **Doeltaal** — `Auto`, `Nederlands`, `English`, `Deutsch`.
- **Extra info default...** — standaard extra informatie voor de pop-up.
- **Log tonen (lokaal)** — opent het lokale logbestand.
- **Serverlog tonen** — haalt de laatste 200 regels op via `GET /api/log`.
- **Instellingen openen** — opent `config.json` (wijzigingen direct actief na opslaan).
- **Afsluiten**.

## Pop-up

Toont skill, gedetecteerde invoertaal, doeltaal en extra info; onderaan het resultaat.
Met **Opnieuw** verwerk je dezelfde tekst opnieuw met een andere doeltaal/skill/extra
info — het nieuwe resultaat overschrijft het klembord. **Kopieer naar klembord** kopieert
handmatig; **Sluiten** sluit de pop-up.
