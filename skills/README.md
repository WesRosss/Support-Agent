# Skills

Elke skill is één Markdown-bestand in deze map. De webapp laadt alle `*.md`-bestanden
(bij het opstarten en via `POST /api/skills/reload`) en koppelt ze op **naam** of **id**.

## Formaat

```markdown
---
name: mijn-skill            # unieke naam; de Windows-client stuurt deze mee
id: 01a0d49d-...            # optioneel: origineel Vibe-skill-id
description: Korte omschrijving
---

De body van de skill wordt als system prompt naar het LLM gestuurd.
De server voegt automatisch de aanroepcontext toe (invoer-/doeltaal, extra info).
```

## Nieuwe skill toevoegen

1. Maak een `.md`-bestand aan in deze map (zie bovenstaand formaat).
2. Herlaad zonder herstart:

   ```bash
   curl -X POST https://JOUW-DOMEIN/api/skills/reload -H "X-API-Key: $APP_API_KEY"
   ```

   Of herstart de container: `docker compose restart app`.

Omdat skills lokaal als `.md` staan, werkt de app met **elk Vibe-account**: je kopieert
de skill-body uit het gewenste account naar een `.md`-bestand met dezelfde `name`.

## Voorbeeld: TOPdesk-ticket samenvatten

```markdown
---
name: topdesk-samenvatting
id:
description: Vat een TOPdesk-ticket samen voor de klant
---

Vat het volgende TOPdesk-ticket samen in maximaal 5 bullets:
- wat is het probleem van de melder,
- welke melding/status is er,
- wat is de proposed oplossing of volgende stap.

Schrijf in de doeltaal, zakelijk maar begrijpelijk voor een eindgebruiker.
Voeg daarna in het Nederlands een korte "elevator pitch" van 2 zinnen toe.
```
