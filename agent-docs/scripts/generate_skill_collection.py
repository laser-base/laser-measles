#!/usr/bin/env python3
"""Generate skill collections from MDX content files.

Transforms a structured MDX content directory into standardized Agent Skills
markdown files following the Agent Skills specification (https://agentskills.io/specification).

Python port of generate-skill-collection.ts.

Dependencies:
    pip install pydantic pyyaml
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

# ============================================================================
# Directory constants
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_DOCS_DIR = SCRIPT_DIR.parent
REPO_ROOT = AGENT_DOCS_DIR.parent
CONTENT_DIR = REPO_ROOT / "docs"
SKILLS_DIR = REPO_ROOT / "skills-collections"
TEMPLATES_DIR = AGENT_DOCS_DIR / "skills-collections" / "_templates"
SKILL_TEMPLATES_DIR = TEMPLATES_DIR / "skills"
GENERATED_DIR = SKILLS_DIR / ".generated"
SNIPPETS_DIR = AGENT_DOCS_DIR / "_snippets"
DEFAULT_COLLECTION_NAME = "laser-measles"
EXCLUDED_DOC_DIRS = {"customization", "includes", "images", "overrides"}

# ============================================================================
# Skill Metadata Schema (Agent Skills Specification)
# ============================================================================


class SkillMetadata(BaseModel):
    """Validates skill metadata per the Agent Skills specification."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=1024)
    license: Optional[str] = None
    compatibility: Optional[str] = Field(default=None, min_length=1, max_length=500)
    metadata: Optional[dict[str, str]] = None
    allowed_tools: Optional[str] = Field(default=None, alias="allowed-tools")

    model_config = {"populate_by_name": True}


# ============================================================================
# Data structures
# ============================================================================


class CollectionPage:
    __slots__ = ("title", "description", "url", "slug_path", "raw_content")

    def __init__(self, title: str, description: str, url: str, slug_path: str, raw_content: str):
        self.title = title
        self.description = description
        self.url = url
        self.slug_path = slug_path
        self.raw_content = raw_content


class ExtractedSkillRule:
    __slots__ = ("id", "skills", "title", "description", "content", "source_slug")

    def __init__(self, id: str, skills: list[str], title: str, description: str, content: str, source_slug: str):
        self.id = id
        self.skills = skills
        self.title = title
        self.description = description
        self.content = content
        self.source_slug = source_slug


# ============================================================================
# Frontmatter parsing (no external dependency beyond PyYAML)
# ============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from text. Returns (metadata_dict, content_body)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    content = text[m.end() :]
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        data = {}
    return data, content


# ============================================================================
# Meta.json handling (Fumadocs-style)
# ============================================================================

_meta_cache: dict[str, Optional[dict]] = {}


def load_meta_json(dir_path: Path) -> Optional[dict]:
    key = str(dir_path)
    if key in _meta_cache:
        return _meta_cache[key]

    meta_path = dir_path / "meta.json"
    if not meta_path.exists():
        _meta_cache[key] = None
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        _meta_cache[key] = meta
        return meta
    except (json.JSONDecodeError, OSError):
        _meta_cache[key] = None
        return None


def get_inherited_skills(file_path: Path) -> list[str]:
    """Walk directory tree from CONTENT_DIR to file, collecting skills from meta.json (child overrides parent)."""
    relative = file_path.relative_to(CONTENT_DIR)
    parts = list(relative.parent.parts)

    inherited: list[str] = []
    current_dir = CONTENT_DIR
    for part in parts:
        current_dir = current_dir / part
        meta = load_meta_json(current_dir)
        if meta and "skills" in meta:
            inherited = meta["skills"]
    return inherited


def get_page_ordering(dir_path: Path) -> Optional[list[str]]:
    meta = load_meta_json(dir_path)
    if meta and "pages" in meta:
        return meta["pages"]
    return None


def sort_pages_by_meta_order(
    pages: list[CollectionPage],
    ordering: Optional[list[str]],
    base_path: str,
) -> list[CollectionPage]:
    """Sort pages according to meta.json ordering following Fumadocs conventions.

    - Explicit order from `pages` array
    - "..." = include remaining files alphabetically
    - "z...a" = include remaining in reverse order
    - Files not in `pages` and no "..." = appended at end alphabetically
    """
    if ordering is None:
        return sorted(pages, key=lambda p: p.slug_path)

    result: list[CollectionPage] = []
    remaining = {p.slug_path: p for p in pages}
    base_prefix = f"{base_path}/" if base_path else ""

    for item in ordering:
        if item == "...":
            result.extend(sorted(remaining.values(), key=lambda p: p.slug_path))
            remaining.clear()
        elif item == "z...a":
            result.extend(sorted(remaining.values(), key=lambda p: p.slug_path, reverse=True))
            remaining.clear()
        elif not item.startswith("!") and not item.startswith("---"):
            target_slug = base_prefix + re.sub(r"^\(.*?\)/", "", item)
            if target_slug in remaining:
                result.append(remaining.pop(target_slug))
            else:
                to_remove = [slug for slug in remaining if slug == target_slug or slug.startswith(f"{target_slug}/")]
                for slug in to_remove:
                    result.append(remaining.pop(slug))

    # Append unmatched pages (when no "..." present)
    if remaining:
        result.extend(sorted(remaining.values(), key=lambda p: p.slug_path))

    return result


def sort_pages_recursively(pages: list[CollectionPage]) -> list[CollectionPage]:
    """Sort pages respecting nested meta.json orderings by grouping per directory."""
    by_directory: dict[str, list[CollectionPage]] = {}
    for page in pages:
        dir_name = str(Path(page.slug_path).parent)
        if dir_name == ".":
            dir_name = ""
        by_directory.setdefault(dir_name, []).append(page)

    sorted_groups: list[CollectionPage] = []
    for dir_name in sorted(by_directory):
        dir_pages = by_directory[dir_name]
        full_dir_path = CONTENT_DIR / dir_name if dir_name else CONTENT_DIR
        ordering = get_page_ordering(full_dir_path)
        sorted_groups.extend(sort_pages_by_meta_order(dir_pages, ordering, dir_name))
    return sorted_groups


# ============================================================================
# Filename conflict resolution
# ============================================================================


def resolve_filename_conflicts(pages: list[CollectionPage]) -> dict[str, str]:
    """Resolve filename conflicts by prefixing with parent folder names where needed."""
    filename_groups: dict[str, list[CollectionPage]] = {}
    for page in pages:
        base_name = page.slug_path.rsplit("/", 1)[-1]
        filename_groups.setdefault(base_name, []).append(page)

    slug_to_filename: dict[str, str] = {}
    for _base_name, group in filename_groups.items():
        if len(group) == 1:
            slug_to_filename[group[0].slug_path] = group[0].slug_path.rsplit("/", 1)[-1]
        else:
            slug_to_filename.update(_resolve_conflict_group(group))
    return slug_to_filename


def _resolve_conflict_group(pages: list[CollectionPage]) -> dict[str, str]:
    """Add parent folder prefixes until all names in the group are unique."""
    for depth in range(1, 11):
        candidate_names: dict[str, list[str]] = {}
        for page in pages:
            parts = page.slug_path.split("/")
            candidate = "-".join(parts[-depth:])
            candidate_names.setdefault(candidate, []).append(page.slug_path)

        if all(len(slugs) == 1 for slugs in candidate_names.values()):
            return {slugs[0]: candidate for candidate, slugs in candidate_names.items()}

    # Fallback: full slug path with hyphens
    return {page.slug_path: page.slug_path.replace("/", "-") for page in pages}


# ============================================================================
# Content processing
# ============================================================================


def file_path_to_url(file_path: Path) -> str:
    relative = str(file_path.relative_to(CONTENT_DIR))
    url = "/" + re.sub(r"\.(mdx?|py)$", "", relative)
    url = re.sub(r"/index$", "", url)
    url = re.sub(r"\(.*?\)/", "", url)  # Remove route groups like (docker)/
    return url


def url_to_slug_path(url: str) -> str:
    return url.strip("/") or "index"


def get_topic_path(slug_path: str) -> str:
    parts = slug_path.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else slug_path


def strip_frontmatter(content: str) -> str:
    return re.sub(r"^---[\s\S]*?---\n", "", content)


def dedent(text: str) -> str:
    lines = text.split("\n")
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    if not indents:
        return text
    min_indent = min(indents)
    if min_indent == 0:
        return text
    return "\n".join(line[min_indent:] if len(line) >= min_indent else line for line in lines)


def expand_snippets(content: str) -> str:
    """Expand snippet references (simplified version of remark-mdx-snippets).

    Looks for self-closing JSX tags (e.g. ``<SnippetName />``) and replaces them
    with the contents of matching files in the snippets directory.
    """
    if not SNIPPETS_DIR.exists():
        return content

    def _replace_snippet(match: re.Match) -> str:
        snippet_name = match.group(1)
        for ext in (".mdx", ".md"):
            snippet_path = SNIPPETS_DIR / f"{snippet_name}{ext}"
            if snippet_path.exists():
                snippet_content = snippet_path.read_text(encoding="utf-8")
                _, body = parse_frontmatter(snippet_content)
                return body.strip()
        return match.group(0)

    return re.sub(r"<(\w+)\s*/\s*>", _replace_snippet, content)


def strip_react_fragments(content: str) -> str:
    content = re.sub(r"^<>\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n</>$", "", content, flags=re.MULTILINE)
    content = content.replace("<>\n", "")
    content = content.replace("\n</>", "")
    return content


def process_markdown(content: str) -> str:
    """Process markdown content: expand snippets and clean up."""
    content = expand_snippets(content)
    return strip_react_fragments(content)


def should_include_doc(file_path: Path) -> bool:
    """Filter out docs that are infrastructure rather than user-facing content."""
    relative = file_path.relative_to(CONTENT_DIR)
    return not any(part in EXCLUDED_DOC_DIRS for part in relative.parts)


def discover_content_files() -> list[Path]:
    """Find repository documentation sources that should become skill rules."""
    markdown_files = [path for path in CONTENT_DIR.rglob("*.md") if should_include_doc(path)]
    tutorial_sources = sorted((CONTENT_DIR / "tutorials").glob("tut_*.py"))
    return sorted({*markdown_files, *tutorial_sources})


def stem_to_title(stem: str) -> str:
    cleaned = re.sub(r"^(tut_|test_)", "", stem)
    return " ".join(word.capitalize() for word in cleaned.split("_"))


def extract_title_from_markdown(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def extract_description_from_markdown(content: str) -> str:
    lines = content.splitlines()
    paragraph_lines: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            if paragraph_lines:
                break
            continue
        if stripped.startswith("#"):
            if paragraph_lines:
                break
            continue
        if not paragraph_lines and (stripped.startswith("[![") or stripped.startswith("![") or stripped.startswith("- ")):
            continue
        if stripped.startswith("!!!") or stripped.startswith("-->"):
            continue
        paragraph_lines.append(stripped)

    return " ".join(paragraph_lines).strip()


def normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def strip_leading_title(content: str, title: str) -> str:
    stripped = content.lstrip()
    match = re.match(r"^#\s+(.+?)\s*$", stripped, re.MULTILINE)
    if match and normalize_heading_text(match.group(1)) == normalize_heading_text(title):
        return stripped[match.end() :].lstrip("\n")
    return stripped


def convert_jupytext_python_to_markdown(text: str) -> str:
    """Convert tutorial .py sources with jupytext markers into markdown with code fences."""
    blocks: list[str] = []
    current_kind: Optional[str] = None
    current_lines: list[str] = []

    def flush_current_block() -> None:
        if not current_lines:
            return
        if current_kind == "markdown":
            markdown_lines: list[str] = []
            for line in current_lines:
                if line.startswith("# "):
                    markdown_lines.append(line[2:])
                elif line == "#":
                    markdown_lines.append("")
                elif line.startswith("#"):
                    markdown_lines.append(line[1:].lstrip())
                else:
                    markdown_lines.append(line)
            block = "\n".join(markdown_lines).strip()
            if block:
                blocks.append(block)
            return

        code = "\n".join(current_lines).strip()
        if code:
            blocks.append(f"```python\n{code}\n```")

    for line in text.splitlines():
        if line.startswith("# %%"):
            flush_current_block()
            current_kind = "markdown" if "[markdown]" in line else "code"
            current_lines = []
            continue

        if current_kind is None:
            current_kind = "code"
        current_lines.append(line)

    flush_current_block()
    return "\n\n".join(blocks).strip() + "\n"


def load_doc_source(file_path: Path) -> tuple[dict[str, Any], str, str, str]:
    """Load a docs source file and return (frontmatter, title, description, markdown_content)."""
    fallback_title = stem_to_title(file_path.stem)

    if file_path.suffix in {".md", ".mdx"}:
        raw = file_path.read_text(encoding="utf-8")
        fm, content = parse_frontmatter(raw)
    elif file_path.suffix == ".py":
        raw = file_path.read_text(encoding="utf-8")
        fm = {}
        content = convert_jupytext_python_to_markdown(raw)
    else:
        raise ValueError(f"Unsupported documentation source type: {file_path}")

    title = fm.get("title") or extract_title_from_markdown(content, fallback_title)
    description = fm.get("description") or extract_description_from_markdown(content)
    return fm, title, description, content


def extract_skill_rules(content: str, source_slug: str) -> list[ExtractedSkillRule]:
    """Extract <SkillRule> blocks from MDX content using regex."""
    rules: list[ExtractedSkillRule] = []
    pattern = re.compile(r"<SkillRule\s+(.*?)>(.*?)</SkillRule>", re.DOTALL)

    for match in pattern.finditer(content):
        attrs_str = match.group(1)
        children = match.group(2).strip()

        props = _parse_jsx_attrs(attrs_str)
        rule_id = props.get("id")
        skills_raw = props.get("skills")
        title = props.get("title")

        if not rule_id or not skills_raw or not title:
            print(f"  Warning: SkillRule missing required props (id, skills, title) in {source_slug}")
            continue

        skills = skills_raw if isinstance(skills_raw, list) else [skills_raw]

        rules.append(
            ExtractedSkillRule(
                id=rule_id,
                skills=skills,
                title=title,
                description=props.get("description", ""),
                content=children,
                source_slug=source_slug,
            )
        )
    return rules


def _parse_jsx_attrs(attrs_str: str) -> dict[str, Any]:
    """Parse JSX-style attributes (string values and simple expressions)."""
    props: dict[str, Any] = {}

    # String attributes: key="value" or key='value'
    for m in re.finditer(r"""(\w+)=["']([^"']*)["']""", attrs_str):
        props[m.group(1)] = m.group(2)

    # Expression attributes: key={value} or key={["a", "b"]}
    for m in re.finditer(r"(\w+)=\{(.*?)\}", attrs_str):
        key = m.group(1)
        expr = m.group(2).strip()
        if expr.startswith("[") and expr.endswith("]"):
            try:
                props[key] = json.loads(expr.replace("'", '"'))
            except json.JSONDecodeError:
                props[key] = expr
        else:
            props[key] = expr

    return props


# ============================================================================
# Template handling
# ============================================================================


def find_template_path(collection_name: str) -> Path:
    candidates = [
        SKILL_TEMPLATES_DIR / collection_name / "SKILL.mdx",
        SKILL_TEMPLATES_DIR / collection_name / "SKILL.md",
        TEMPLATES_DIR / collection_name / "SKILL.mdx",
        TEMPLATES_DIR / collection_name / "SKILL.md",
    ]

    for template_path in candidates:
        if template_path.exists():
            return template_path

    candidate_list = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        f'Missing template for skill "{collection_name}". Looked for:\n{candidate_list}'
    )


def load_template(collection_name: str) -> tuple[Optional[SkillMetadata], str]:
    """Load and validate a skill template. Returns (metadata_or_None, content)."""
    template_path = find_template_path(collection_name)

    raw = template_path.read_text(encoding="utf-8")
    fm, content = parse_frontmatter(raw)

    if fm.get("name") or fm.get("description"):
        try:
            skill_metadata = SkillMetadata(**fm)
        except Exception as e:
            raise ValueError(f"Invalid skill metadata in {template_path}:\n{e}") from e

        if skill_metadata.name != collection_name:
            raise ValueError(
                f'Skill name "{skill_metadata.name}" in {template_path} '
                f'must match collection name "{collection_name}"'
            )
        return skill_metadata, content

    return None, raw


def load_and_process_file(relative_path: str) -> str:
    """Load a content file by path (relative to content dir) and return processed markdown."""
    file_path = CONTENT_DIR / relative_path
    if not file_path.exists():
        raise FileNotFoundError(f"Include file not found: {relative_path}")

    raw = file_path.read_text(encoding="utf-8")
    _, content = parse_frontmatter(raw)
    return dedent(process_markdown(content))


def apply_template(template: str, collection_name: str, table: str, rules_count: int) -> str:
    """Apply template variable substitutions and {{INCLUDE:path}} directives."""
    result = (
        template.replace("{{COLLECTION_NAME}}", to_title_case(collection_name))
        .replace("{{RULES_TABLE}}", table)
        .replace("{{RULES_COUNT}}", str(rules_count))
    )

    for match in re.finditer(r"\{\{INCLUDE:([^}]+)\}\}", result):
        placeholder = match.group(0)
        include_path = match.group(1).strip()
        try:
            included_content = load_and_process_file(include_path)
            result = result.replace(placeholder, included_content)
            print(f"    Included: {include_path}")
        except Exception as e:
            print(f"    Warning: Could not include {include_path}: {e}")
            result = result.replace(placeholder, f"<!-- Include failed: {include_path} -->")

    return result


# ============================================================================
# Output generation helpers
# ============================================================================


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def to_title_case(s: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-_]", s))


def generate_table(pages: list[CollectionPage], filename_map: dict[str, str]) -> str:
    header = "| Title | Topic | Description |\n| --- | --- | --- |"
    rows: list[str] = []
    for page in pages:
        title = escape_table_cell(page.title)
        description = escape_table_cell(page.description or "")
        topic_path = get_topic_path(page.slug_path)
        filename = filename_map.get(page.slug_path, page.slug_path.replace("/", "-"))
        link = f"[{title}](./rules/{filename}.md)"
        rows.append(f"| {link} | {topic_path} | {description} |")
    return "\n".join([header, *rows])


def _escape_yaml_string(s: str) -> str:
    return s.replace('"', '\\"')


def find_readme_template_path() -> Optional[Path]:
    candidates = [
        TEMPLATES_DIR / "README.mdx",
        TEMPLATES_DIR / "README.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("Generating skill collections...")

    if not CONTENT_DIR.exists():
        print(f"Content directory not found: {CONTENT_DIR}")
        sys.exit(1)

    source_files = discover_content_files()
    print(f"Found {len(source_files)} documentation source files")

    collections: dict[str, list[CollectionPage]] = {}

    for file_path in source_files:
        fm, title, description, content = load_doc_source(file_path)

        # Skills from frontmatter (highest priority) or inherited from parent meta.json
        skills: list[str] | None = fm.get("skills")
        if not skills and file_path.suffix in {".md", ".mdx"}:
            skills = get_inherited_skills(file_path)

        url = file_path_to_url(file_path)
        slug_path = url_to_slug_path(url)

        # EXCLUSIVE LOGIC:
        # - If file has skills (frontmatter or inherited) -> full-file rule
        # - If file has NO skills -> extract <SkillRule> blocks, else fall back to default collection
        if skills:
            for collection_name in skills:
                collections.setdefault(collection_name, []).append(
                    CollectionPage(title, description, url, slug_path, content)
                )
        else:
            extracted_rules = extract_skill_rules(content, slug_path)
            for rule in extracted_rules:
                for skill in rule.skills:
                    collections.setdefault(skill, []).append(
                        CollectionPage(
                            rule.title,
                            rule.description,
                            "",
                            f"{rule.source_slug}/{rule.id}",
                            rule.content,
                        )
                    )

            if not extracted_rules:
                collections.setdefault(DEFAULT_COLLECTION_NAME, []).append(
                    CollectionPage(title, description, url, slug_path, content)
                )

    if not collections:
        print("No documentation pages found. Skipping generation.")
        return

    # Sort pages in each collection according to meta.json ordering
    for name in collections:
        collections[name] = sort_pages_recursively(collections[name])

    print(f"Found {len(collections)} skill collection(s):")
    for name, pages in collections.items():
        print(f"  - {name}: {len(pages)} rule(s)")

    # Clean and recreate generated directory
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    skills_dir = GENERATED_DIR / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Build root README with skills table
    skills_table_rows: list[str] = []
    for collection_name in collections:
        try:
            skill_metadata, _ = load_template(collection_name)
            if skill_metadata:
                name = skill_metadata.name
                desc = escape_table_cell(skill_metadata.description)
                skills_table_rows.append(f"| [{name}](./skills/{name}/SKILL.md) | {desc} |")
            else:
                skills_table_rows.append(
                    f"| [{collection_name}](./skills/{collection_name}/SKILL.md) | *No description* |"
                )
        except Exception:
            skills_table_rows.append(
                f"| [{collection_name}](./skills/{collection_name}/SKILL.md) | *Template missing* |"
            )

    collections_list = (
        f"| Skill | Description |\n| --- | --- |\n" + "\n".join(skills_table_rows)
        if skills_table_rows
        else "*No skills available*"
    )

    readme_template_path = find_readme_template_path()
    if readme_template_path:
        readme_template = readme_template_path.read_text(encoding="utf-8")
        root_readme = readme_template.replace("{{COLLECTIONS_LIST}}", collections_list)
    else:
        root_readme = f"# Inkeep Skills\n\n## Available Collections\n\n{collections_list}\n"
    (GENERATED_DIR / "README.md").write_text(root_readme, encoding="utf-8")

    # Generate per-collection outputs
    for collection_name, collection_pages in collections.items():
        collection_dir = skills_dir / collection_name
        rules_dir = collection_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        filename_map = resolve_filename_conflicts(collection_pages)

        skill_metadata, template_content = load_template(collection_name)
        table = generate_table(collection_pages, filename_map)
        body_content = apply_template(template_content, collection_name, table, len(collection_pages))

        # Generate SKILL.md with proper frontmatter per Agent Skills spec
        if skill_metadata:
            fm_lines = ["---"]
            fm_lines.append(f"name: {skill_metadata.name}")
            fm_lines.append(f"description: {skill_metadata.description}")
            if skill_metadata.license:
                fm_lines.append(f"license: {skill_metadata.license}")
            if skill_metadata.compatibility:
                fm_lines.append(f"compatibility: {skill_metadata.compatibility}")
            if skill_metadata.metadata:
                fm_lines.append("metadata:")
                for key, value in skill_metadata.metadata.items():
                    fm_lines.append(f'  {key}: "{value}"')
            if skill_metadata.allowed_tools:
                fm_lines.append(f"allowed-tools: {skill_metadata.allowed_tools}")
            fm_lines.append("---")
            skill_md = "\n".join(fm_lines) + "\n\n" + body_content
        else:
            print(
                f'  Warning: No skill metadata in template for "{collection_name}". '
                "SKILL.md will lack required frontmatter."
            )
            skill_md = body_content

        (collection_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        print(f"  Created {collection_name}/SKILL.md")

        # Generate individual rule files (flattened into rules/ directory)
        for page in collection_pages:
            filename = filename_map.get(page.slug_path, page.slug_path.replace("/", "-"))
            rule_file_path = rules_dir / f"{filename}.md"

            try:
                processed_content = process_markdown(page.raw_content)
            except Exception:
                print(f"  Warning: Could not process {page.url}, using raw content")
                processed_content = strip_frontmatter(page.raw_content)

            topic_path = get_topic_path(page.slug_path)
            fm_lines = [
                "---",
                f'title: "{_escape_yaml_string(page.title)}"',
            ]
            if page.description:
                fm_lines.append(f'description: "{_escape_yaml_string(page.description)}"')
            fm_lines.append(f'topic-path: "{topic_path}"')
            fm_lines.append("---")

            body_content = strip_leading_title(processed_content, page.title)
            body = f"# {page.title}\n\n{body_content}" if body_content else f"# {page.title}\n"
            rule_file_path.write_text("\n".join(fm_lines) + "\n\n" + body, encoding="utf-8")

        print(f"  Created {len(collection_pages)} rule file(s) in {collection_name}/rules/")

    print("Skill collections generated successfully!")


if __name__ == "__main__":
    main()
