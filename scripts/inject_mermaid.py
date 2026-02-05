from pathlib import Path

README = Path("README.md")
MMD = Path("docs/classes_mesoSPIM.mmd")

start = "<!-- PYREVERSE:START -->"
end = "<!-- PYREVERSE:END -->"

text = README.read_text(encoding="utf-8")
before, rest = text.split(start)
_, after = rest.split(end)

diagram = f"""{start}

```mermaid
{MMD.read_text(encoding="utf-8")}
{end}"""

README.write_text(before + diagram + after, encoding="utf-8")