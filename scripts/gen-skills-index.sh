#!/usr/bin/env bash
# Regenerate the baked-skills index table in base-image/skills/README.md from
# each skill's SKILL.md frontmatter (name + description). The skills directory
# is the source of truth; this script just keeps the human-readable table in
# sync so it can't drift. Re-run after adding/removing/renaming a baked skill.
#
#   ./scripts/gen-skills-index.sh
#
# The table is written between the BEGIN/END marker comments in the README; if
# the markers aren't present, a "Baked skills" section is appended.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/base-image/skills"
README="$SKILLS_DIR/README.md"

python3 - "$SKILLS_DIR" "$README" <<'PY'
import sys, os, re, glob

skills_dir, readme = sys.argv[1], sys.argv[2]
BEGIN = "<!-- BEGIN baked-skills (generated — run scripts/gen-skills-index.sh) -->"
END   = "<!-- END baked-skills -->"

def parse_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None, None
    lines = m.group(1).split("\n")
    name, desc, i = None, None, 0
    while i < len(lines):
        line = lines[i]
        nm = re.match(r"^name:\s*(.*)$", line)
        if nm:
            name = nm.group(1).strip().strip("'\"")
            i += 1
            continue
        dm = re.match(r"^description:\s*(.*)$", line)
        if dm:
            rest = dm.group(1).strip()
            if rest in (">", ">-", ">+", "|", "|-", "|+", ""):
                # block scalar: gather subsequent indented lines
                parts, i = [], i + 1
                while i < len(lines):
                    cur = lines[i]
                    if cur.strip() == "":
                        i += 1
                        continue
                    if cur.startswith((" ", "\t")):
                        parts.append(cur.strip())
                        i += 1
                    else:
                        break
                desc = " ".join(parts)
            else:
                desc = rest.strip("'\"")
                i += 1
            continue
        i += 1
    return name, desc

def summarize(desc, limit=180):
    if not desc:
        return ""
    desc = re.sub(r"\s+", " ", desc).strip()
    m = re.search(r"\.\s", desc)
    if m and m.start() < limit:
        return desc[:m.start() + 1]
    return (desc[:limit].rstrip() + "…") if len(desc) > limit else desc

rows = []
for skill_md in sorted(glob.glob(os.path.join(skills_dir, "*", "SKILL.md"))):
    name, desc = parse_frontmatter(skill_md)
    name = name or os.path.basename(os.path.dirname(skill_md))
    rows.append(f"| `{name}` | {summarize(desc).replace('|', '\\|')} |")

table = "| Skill | Description |\n|---|---|\n" + ("\n".join(rows) if rows else "| _(none yet)_ | |")
block = f"{BEGIN}\n{table}\n{END}"

with open(readme, encoding="utf-8") as f:
    content = f.read()

if BEGIN in content and END in content:
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, content, flags=re.S)
else:
    new = content.rstrip() + "\n\n## Baked skills\n\n" + block + "\n"

with open(readme, "w", encoding="utf-8") as f:
    f.write(new)

print(f"gen-skills-index: wrote {len(rows)} skill(s) to {readme}")
PY
