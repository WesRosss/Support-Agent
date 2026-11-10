import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("support_agent.skills")


@dataclass
class Skill:
    name: str
    skill_id: str
    description: str
    body: str
    file: str


def parse_skill_file(path: Path) -> Skill:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    meta: dict = {}
    body_lines = lines
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                for line in lines[1:i]:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meta[key.strip().lower()] = value.strip()
                body_lines = lines[i + 1:]
                break
    body = "\n".join(body_lines).strip()
    return Skill(
        name=meta.get("name", path.stem),
        skill_id=meta.get("id", ""),
        description=meta.get("description", ""),
        body=body,
        file=path.name,
    )


class SkillStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._skills: dict = {}

    def load(self) -> int:
        skills: dict = {}
        for file in sorted(self.directory.glob("*.md")):
            if file.name.lower() == "readme.md":
                continue
            try:
                skill = parse_skill_file(file)
                skills[skill.name.lower()] = skill
                if skill.skill_id:
                    skills[skill.skill_id.lower()] = skill
                logger.info("Skill geladen: %s (%s)", skill.name, file.name)
            except Exception:
                logger.exception("Kan skill-bestand niet laden: %s", file)
        self._skills = skills
        return len({s.name for s in skills.values()})

    def get(self, key: str):
        return self._skills.get(key.strip().lower())

    def list(self) -> list:
        unique = {skill.name: skill for skill in self._skills.values()}
        return [
            {"name": s.name, "id": s.skill_id, "description": s.description}
            for s in unique.values()
        ]
