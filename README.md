# PDF Generator API Skills

Public [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for
[PDF Generator API](https://pdfgeneratorapi.com) — drop-in expertise that lets Claude (and other
skill-aware agents) build, replicate, validate and debug PDF Generator API templates and
integrations without you having to teach it the platform first.

Each skill is self-contained: instructions, the official JSON schema, a distilled component
reference, runnable helper scripts and validated examples. No API key or network access is needed
for the default workflow — everything runs locally against the bundled schema.

## Skills in this repository

| Skill | What it does |
| --- | --- |
| **[pdfgeneratorapi-template-builder](pdfgeneratorapi-template-builder/)** | Creates a template definition either from a plain-language description or by replicating an uploaded document (PDF, Word, image). Measures the source, writes the template JSON plus a matching example dataset, hydrates it into the import-safe shape, and validates it locally (schema + layout lint) before handing it over. Also used to validate or fix existing templates. |

Each skill folder has its own README with install steps, example prompts, script reference and
requirements — start there.

More skills — integration scaffolding, data-mapping and troubleshooting helpers — will land here as
they are ready.

## Install

Every skill ships two ways: a `source/` directory (the skill itself, browsable and diffable) and a
packaged `<skill-name>.skill` bundle (a zip, for uploaders that want a single file).

**Claude Code** — copy `source/` into your personal or project skills directory, named after the
skill:

```bash
git clone https://github.com/pdfgeneratorapi/skills.git
mkdir -p ~/.claude/skills
cp -r skills/<skill-name>/source ~/.claude/skills/<skill-name>
```

Use `.claude/skills/` inside a repository instead of `~/.claude/skills/` to share the skill with
everyone working on that project. Start a new session afterwards and the skill is picked up
automatically — it activates on its own when a request matches its description.

**Claude apps (web, desktop)** — upload `<skill-name>/<skill-name>.skill` under
**Settings → Capabilities → Skills**. If the uploader only accepts `.zip`, rename the file; the
bundle is a plain zip archive.

Then just ask in natural language — *"create a PDF Generator API template for an invoice with a
line-item table"*, or attach a document and ask for it to be converted. See the skill's own README
for what it produces and how to use the result.

## Repository layout

```
<skill-name>/
├── README.md                   # what this skill does, install, usage, requirements
├── source/                     # the skill — copy this into your skills directory
│   ├── SKILL.md                # name, description and the workflow the agent follows
│   ├── references/             # progressively-loaded docs: schema, component reference, playbooks
│   ├── scripts/                # deterministic helpers the agent runs instead of guessing
│   └── examples/               # validated template + data pairs to pattern-match against
└── <skill-name>.skill          # packaged bundle of source/, for upload-based installs
```

Only `source/` becomes the installed skill; the README and the bundle sit outside it.

## Building a bundle

After editing a skill's `source/`, repackage it so the two stay in sync. The archive must contain a
single top-level directory named after the skill:

```bash
cd <skill-name>
python3 - <<'PY'
import pathlib, zipfile
name = pathlib.Path.cwd().name
src = pathlib.Path("source")
with zipfile.ZipFile(f"{name}.skill", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(src.rglob("*")):
        if f.is_file() and not any(s.startswith(".") for s in f.parts):
            z.write(f, f"{name}/{f.relative_to(src)}")
PY
```

## Contributing

Issues and pull requests are welcome — corrections to the component reference, additional validated
examples, and new skills especially. When changing a skill, please:

- keep `SKILL.md` focused; move detail into `references/` so it loads only when relevant,
- make sure every example still passes `python3 scripts/validate_template.py <template> --data <data>`,
- update the packaged `.skill` bundle in the same commit.

## Links

- [PDF Generator API](https://pdfgeneratorapi.com)
- [API documentation](https://docs.pdfgeneratorapi.com)
- [Support portal](https://support.pdfgeneratorapi.com)

## License

[MIT](LICENSE) © PDF Generator API
