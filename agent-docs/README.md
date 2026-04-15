# Agent-docs

This directory contains the local tooling and templates used to turn the laser-measles documentation into an agent-skill collection.

## What The Script Does

The generator script is [agent-docs/scripts/generate_skill_collection.py](agent-docs/scripts/generate_skill_collection.py).

For this repository, it:

- Reads user-facing docs from [docs](docs)
- Includes Markdown docs such as [docs/index.md](docs/index.md), [docs/install.md](docs/install.md), and [docs/usage.md](docs/usage.md)
- Converts jupytext tutorial sources such as [docs/tutorials/tut_basic_model.py](docs/tutorials/tut_basic_model.py) into Markdown rule files
- Skips documentation infrastructure folders such as `docs/customization`, `docs/includes`, and image assets
- Loads skill templates from [agent-docs/skills-collections/_templates](agent-docs/skills-collections/_templates)
- Writes generated output to [skills-collections/.generated](skills-collections/.generated)

The generated collection currently falls back to a single `laser-measles` skill when source docs do not contain explicit `skills:` metadata or embedded `SkillRule` blocks.

## How To Run It

Run the script from the repository root:

```bash
python agent-docs/scripts/generate_skill_collection.py
```

If you are using the local virtual environment in this repo, the explicit command is:

```bash
/home/krosenfeld/projects/project-laser-measles/laser-measles/.venv/bin/python agent-docs/scripts/generate_skill_collection.py
```

The script does not take command-line arguments at the moment. It resolves repository paths relative to the script location, so it should be run from within this repository and not copied elsewhere without updating its path assumptions.

## Generated Output

After a successful run, you should see:

- A generated collection index at [skills-collections/.generated/README.md](skills-collections/.generated/README.md)
- A skill overview file at [skills-collections/.generated/skills/laser-measles/SKILL.md](skills-collections/.generated/skills/laser-measles/SKILL.md)
- Individual rule files under [skills-collections/.generated/skills/laser-measles/rules](skills-collections/.generated/skills/laser-measles/rules)

Typical console output looks like this:

```text
Generating skill collections...
Found 18 documentation source files
Found 1 skill collection(s):
	- laser-measles: 18 rule(s)
	Created laser-measles/SKILL.md
	Created 18 rule file(s) in laser-measles/rules/
Skill collections generated successfully!
```

## Notes

- The generated files under [skills-collections/.generated](skills-collections/.generated) are build artifacts and may be regenerated at any time.
- The script is repository-specific right now. It has been adapted to this MkDocs plus jupytext layout rather than the original upstream MDX content layout.
- If you want more than one skill collection, add explicit metadata or rule markup to the source docs and extend the templates under [agent-docs/skills-collections/_templates](agent-docs/skills-collections/_templates).

## References

- https://github.com/inkeep/agents/tree/main/agents-docs
- https://inkeep.com/blog/docs-to-agent-skills