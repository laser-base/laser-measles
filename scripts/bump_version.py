#!/usr/bin/env python3
"""AI-driven version bumper for Python projects using pyproject.toml.

Reads commits since the last version tag, asks Claude to categorize them and
produce changelog prose, then writes the new version into pyproject.toml and
prepends a section to CHANGELOG.md. Prints the new version string to stdout
so a GitHub Action can capture it.

Usage:
    python3 scripts/bump_version.py [REPO_ROOT]

    REPO_ROOT defaults to the current working directory.
"""

import json
import logging
import re
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: 'anthropic' package not found. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

NO_CHANGES_SENTINEL = "no_changes"


def get_last_version_tag() -> str | None:
    """Return the most recent semver tag, or None if no tags exist.

    Returns:
        Tag name such as 'v1.2.3', or None.
    """
    logger.info("Fetching last version tag from git")
    result = subprocess.run(
        ["git", "tag", "--sort=-v:refname", "--list", "v*"],
        capture_output=True,
        text=True,
        check=False,
    )
    tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    tag = tags[0] if tags else None
    logger.info("Last version tag: %s", tag or "(none)")
    return tag


def get_commits_since(tag: str | None) -> list[dict[str, str]]:
    """Return commits reachable from HEAD but not from tag.

    Args:
        tag: Lower-bound git ref. None means all commits on HEAD.

    Returns:
        List of dicts with 'hash', 'subject', and 'body' keys,
        ordered newest-first.

    Raises:
        subprocess.CalledProcessError: If git log fails.
    """
    range_spec = f"{tag}..HEAD" if tag else "HEAD"
    logger.info("Collecting commits: %s", range_spec)

    result = subprocess.run(
        # \x1f = unit separator between fields; \x1e = record separator between commits
        ["git", "log", range_spec, "--pretty=format:%H%x1f%s%x1f%b%x1e"],
        capture_output=True,
        text=True,
        check=True,
    )

    commits: list[dict[str, str]] = []
    for record in result.stdout.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x1f")
        commits.append(
            {
                "hash": parts[0].strip() if len(parts) > 0 else "",
                "subject": parts[1].strip() if len(parts) > 1 else "",
                "body": parts[2].strip() if len(parts) > 2 else "",
            }
        )

    logger.info("Found %d commit(s) since %s", len(commits), tag or "beginning of history")
    return commits


def get_current_version(pyproject_path: Path) -> str:
    """Read the version field from pyproject.toml.

    Args:
        pyproject_path: Absolute path to pyproject.toml.

    Returns:
        Version string, e.g. '1.2.3'.

    Raises:
        KeyError: If [project] or version key is absent.
        FileNotFoundError: If pyproject_path does not exist.
    """
    logger.info("Reading current version from %s", pyproject_path)
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    version: str = data["project"]["version"]
    logger.info("Current version: %s", version)
    return version


def analyze_commits_with_claude(
    commits: list[dict[str, str]],
    current_version: str,
) -> dict:
    """Call Claude to categorize commits and write changelog prose.

    Args:
        commits: Commit list as returned by get_commits_since.
        current_version: Current semver string, provided as context.

    Returns:
        Dict with keys:
            bump_type (str): 'major', 'minor', or 'patch'.
            summary (str): One-line release summary.
            sections (list): Each entry has 'heading' (str) and
                'items' (list[str]) keys.

    Raises:
        anthropic.APIError: On network or API failure.
        json.JSONDecodeError: If Claude returns malformed JSON.
        KeyError: If required keys are missing from Claude's response.
    """
    logger.info("Sending %d commit(s) to Claude for analysis", len(commits))

    commit_lines = "\n".join(f"- {c['subject']}" + (f"\n  {c['body']}" if c["body"] else "") for c in commits)

    prompt = f"""You are a release engineer. Analyze the git commits below and produce structured release notes.

Current version: {current_version}

Commits since last release:
{commit_lines}

Reply with a single JSON object — no markdown fences, no prose outside the JSON. Use this exact shape:
{{
  "bump_type": "major" | "minor" | "patch",
  "summary": "<one-line human-readable release summary>",
  "sections": [
    {{
      "heading": "<e.g. Features, Bug Fixes, Breaking Changes, Improvements, Internal>",
      "items": ["<past-tense user-facing changelog item>"]
    }}
  ]
}}

Classification rules:
- "major"  — any commit that introduces a breaking change.
- "minor"  — any commit that adds a new feature with no breaking changes.
- "patch"  — all commits are bug fixes, refactors, docs, tests, or chores.

Writing rules:
- Write items in past tense from a user perspective (e.g. "Added X", "Fixed Y").
- Skip merge commits, version bumps, and purely cosmetic changes.
- Group items under the most relevant heading.
- Use a single "Breaking Changes" heading for any breaking items."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    logger.info("Received Claude response, parsing JSON")

    # Strip accidental markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result: dict = json.loads(raw)
    logger.info(
        "Analysis: bump_type=%s, sections=%d",
        result["bump_type"],
        len(result.get("sections", [])),
    )
    return result


def bump_semver(version: str, bump_type: str) -> str:
    """Increment a semver string.

    Args:
        version: Current version, e.g. '1.2.3' or '1.2.3.post1'.
        bump_type: One of 'major', 'minor', 'patch'.

    Returns:
        Bumped version string.

    Raises:
        ValueError: If version is not a recognisable semver or bump_type
            is not one of the three allowed values.
    """
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(.*)", version)
    if not match:
        raise ValueError(f"Not a valid semver string: {version!r}")

    major, minor, patch, suffix = (
        int(match[1]),
        int(match[2]),
        int(match[3]),
        match[4],
    )

    if bump_type == "major":
        major, minor, patch = major + 1, 0, 0
        suffix = ""
    elif bump_type == "minor":
        minor, patch = minor + 1, 0
        suffix = ""
    elif bump_type == "patch":
        patch += 1
        suffix = ""
    else:
        raise ValueError(f"Invalid bump_type: {bump_type!r}. Must be major, minor, or patch.")

    new_version = f"{major}.{minor}.{patch}{suffix}"
    logger.info("Version bump: %s → %s (%s)", version, new_version, bump_type)
    return new_version


def write_new_version(pyproject_path: Path, new_version: str) -> None:
    """Replace the version string in pyproject.toml using regex substitution.

    Preserves all comments and formatting in the file.

    Args:
        pyproject_path: Path to pyproject.toml.
        new_version: Version string to write.

    Raises:
        RuntimeError: If the version line cannot be located in the file.
    """
    logger.info("Writing version %s to %s", new_version, pyproject_path)
    content = pyproject_path.read_text(encoding="utf-8")

    updated, n_subs = re.subn(
        r'^(version\s*=\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if n_subs == 0:
        raise RuntimeError(f'Could not find version = "..." in {pyproject_path}')

    pyproject_path.write_text(updated, encoding="utf-8")
    logger.info("pyproject.toml updated")


def build_changelog_section(version: str, analysis: dict) -> str:
    """Render a CHANGELOG.md section from a Claude analysis dict.

    Args:
        version: New version string.
        analysis: Dict as returned by analyze_commits_with_claude.

    Returns:
        Formatted markdown string, ending with a trailing newline.
    """
    today = datetime.now(tz=...).date()
    lines: list[str] = [f"## [{version}] - {today}", ""]

    if analysis.get("summary"):
        lines += [analysis["summary"], ""]

    for section in analysis.get("sections", []):
        heading = section.get("heading", "Changes")
        items = section.get("items", [])
        if not items:
            continue
        lines += [f"### {heading}", ""]
        lines.extend(f"- {item}" for item in items)
        lines.append("")

    return "\n".join(lines)


def prepend_to_changelog(changelog_path: Path, new_section: str) -> None:
    """Insert new_section before the first existing ## entry in CHANGELOG.md.

    Creates the file with a standard header if it does not exist.

    Args:
        changelog_path: Path to CHANGELOG.md.
        new_section: Formatted markdown block to prepend.
    """
    logger.info("Updating %s", changelog_path)

    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
    else:
        existing = "# Changelog\n\nAll notable changes to this project are documented here.\n\n"

    if "## " in existing:
        insert_pos = existing.index("## ")
        updated = existing[:insert_pos] + new_section + "\n" + existing[insert_pos:]
    else:
        updated = existing.rstrip("\n") + "\n\n" + new_section

    changelog_path.write_text(updated, encoding="utf-8")
    logger.info("CHANGELOG.md updated")


def main() -> None:
    """Orchestrate the version bump: detect changes, call Claude, write files."""
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    pyproject_path = repo_root / "pyproject.toml"
    changelog_path = repo_root / "CHANGELOG.md"

    logger.info("Repo root: %s", repo_root)

    if not pyproject_path.exists():
        logger.error("pyproject.toml not found at %s", pyproject_path)
        sys.exit(1)

    last_tag = get_last_version_tag()
    commits = get_commits_since(last_tag)

    if not commits:
        logger.info("No commits since last tag — nothing to bump")
        print(NO_CHANGES_SENTINEL)
        return

    current_version = get_current_version(pyproject_path)
    analysis = analyze_commits_with_claude(commits, current_version)
    new_version = bump_semver(current_version, analysis["bump_type"])

    write_new_version(pyproject_path, new_version)

    section = build_changelog_section(new_version, analysis)
    prepend_to_changelog(changelog_path, section)

    # Emit to stdout so the Action can capture it via $()
    print(new_version)
    logger.info("Done — new version: %s", new_version)


if __name__ == "__main__":
    main()
