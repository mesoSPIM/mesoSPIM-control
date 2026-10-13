"""Skills: short procedures in Markdown that the model loads when a request matches one.

A skill is one file with a head and a body:

    ---
    name: centring
    description: Move the sample to the middle of the image.
    tools: look, move_relative, calibrate
    ---
    When it applies, the steps with the tool for each, when it is done, what to report.

The prompt lists only each skill's name and description; `load_skill` returns the body when the
model decides a request matches. The microscope's skills live in a `skills` folder next to its
config file, so each lab keeps its own; none ship with mesoSPIM.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    tools: tuple[str, ...]
    body: str
    path: Path | None = None


def parse(text: str, path: Path | None = None) -> Skill:
    """One skill from its file text; ValueError says what is wrong with it."""
    where = path.name if path is not None else "skill"
    if len(text) > config.SKILL_MAX_CHARS:
        raise ValueError(f"{where}: {len(text)} characters, more than {config.SKILL_MAX_CHARS}")
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in (line.strip() for line in lines[1:]):
        raise ValueError(f"{where}: starts with a head between two '---' lines")
    end = 1 + [line.strip() for line in lines[1:]].index("---")
    head = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            head[key.strip().lower()] = value.strip()
    name, description = head.get("name", ""), head.get("description", "")
    if not name or not description:
        raise ValueError(f"{where}: the head needs a name and a description")
    tools = tuple(t.strip() for t in head.get("tools", "").split(",") if t.strip())
    body = "\n".join(lines[end + 1:]).strip()
    if not body:
        raise ValueError(f"{where}: has no steps after the head")
    return Skill(name, description, tools, body, path)


def load(folder) -> tuple[dict[str, Skill], list[str]]:
    """Every skill in the folder by name, and a line for each file that could not be used."""
    skills, problems = {}, []
    if folder is None or not Path(folder).is_dir():
        return skills, problems
    for path in sorted(Path(folder).glob("*.md")):
        try:
            skill = parse(path.read_text(encoding="utf-8"), path)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            problems.append(f"skill not loaded: {error}")
            logger.warning("skill %s not loaded: %s", path, error)
            continue
        if skill.name in skills:
            problems.append(f"skill not loaded: {path.name} repeats the name {skill.name!r}")
            continue
        skills[skill.name] = skill
    return skills, problems


def folder_of(cfg) -> Path | None:
    """The microscope's skills folder: `skills` next to its config file, when it has one."""
    config_file = getattr(cfg, "__file__", None)
    return Path(config_file).parent / config.SKILLS_FOLDER if config_file else None


def unknown_tools(skills: dict[str, Skill], offered) -> list[str]:
    """A line for each skill that names a tool the assistant does not offer."""
    offered = set(offered)
    return [f"skill {s.name}: no tool {', '.join(missing)}" for s in skills.values()
            if (missing := [t for t in s.tools if t not in offered])]
