import hmac
import logging
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import mistral_client
from .config import settings
from .logbuf import RingBufferHandler
from .skills import SkillStore

LANGUAGES = {"nl": "Nederlands", "en": "English", "de": "Deutsch"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger().setLevel(logging.INFO)
ring = RingBufferHandler(maxlen=500)
ring.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(ring)
logger = logging.getLogger("support_agent.api")

if not settings.app_api_key or not settings.mistral_api_key:
    logger.warning("APP_API_KEY en/of MISTRAL_API_KEY niet gezet in de omgeving")

store = SkillStore(settings.skills_dir)
store.load()

app = FastAPI(title="Support-Agent API", version="1.0.0")


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if (
        not settings.app_api_key
        or not x_api_key
        or not hmac.compare_digest(x_api_key.encode(), settings.app_api_key.encode())
    ):
        raise HTTPException(status_code=401, detail="Ongeldige of ontbrekende API-key (header X-API-Key)")


class ProcessRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20000)
    target_language: str = "nl"
    source_language: str = "auto"
    extra: str = ""

    @field_validator("target_language")
    @classmethod
    def _valid_target(cls, v: str) -> str:
        v = v.lower()
        if v not in LANGUAGES:
            raise ValueError(f"target_language moet een van {sorted(LANGUAGES)} zijn")
        return v

    @field_validator("source_language")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        v = v.lower()
        if v != "auto" and v not in LANGUAGES:
            raise ValueError(f"source_language moet 'auto' of een van {sorted(LANGUAGES)} zijn")
        return v


def build_prompts(skill, req: ProcessRequest) -> tuple:
    target_name = LANGUAGES[req.target_language]
    source_name = LANGUAGES.get(req.source_language, "onbekend (automatisch)")
    extra = req.extra.strip() or "geen"
    system = (
        skill.body
        + "\n\n# Aanroepcontext\n"
        + f"- Invoertaal: {source_name}\n"
        + f"- Doeltaal: {target_name} ({req.target_language})\n"
        + f"- Extra informatie van de gebruiker: {extra}\n\n"
        + "Pas de uitvoertaal aan op de doeltaal: lever de bewerkte tekst in de doeltaal (in een code block), "
        + "geef de feedback over de wijzigingen in het Nederlands en voeg ter controle een vertaling van het "
        + "resultaat in de invoertaal toe (niet in een code block), als die verschilt van de doeltaal."
    )
    user = f'Tekst om te verwerken:\n"""\n{req.text}\n"""'
    return system, user


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/skills")
async def list_skills(_=Depends(require_api_key)):
    return {"skills": store.list()}


@app.post("/api/skills/reload")
async def reload_skills(_=Depends(require_api_key)):
    count = store.load()
    return {"reloaded": count}


@app.get("/api/log")
async def get_log(limit: int = Query(200, ge=1, le=500), _=Depends(require_api_key)):
    return {"entries": ring.entries(limit)}


@app.post("/api/process")
async def process(req: ProcessRequest, _=Depends(require_api_key)):
    skill = store.get(req.skill)
    if skill is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Onbekende skill: {req.skill}",
                "available": [s["name"] for s in store.list()],
            },
        )
    system, user = build_prompts(skill, req)
    t0 = time.perf_counter()
    logger.info(
        "process: skill=%s %s->%s chars=%d",
        skill.name,
        req.source_language,
        req.target_language,
        len(req.text),
    )
    try:
        result = await mistral_client.complete(
            system=system,
            user=user,
            model=settings.mistral_model,
            base_url=settings.mistral_base_url,
            api_key=settings.mistral_api_key,
        )
    except mistral_client.MistralError as exc:
        logger.error("Mistral fout: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(
        "process ok: skill=%s %s->%s duration_ms=%s",
        skill.name,
        req.source_language,
        req.target_language,
        duration_ms,
    )
    return {
        "result": result,
        "skill": skill.name,
        "target_language": req.target_language,
        "source_language": req.source_language,
        "model": settings.mistral_model,
        "duration_ms": duration_ms,
    }
