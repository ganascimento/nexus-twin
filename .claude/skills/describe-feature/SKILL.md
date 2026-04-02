---
name: describe-feature
description: "Spec writer for the Nexus Twin project. Generates specs.md and tasks.md for a given feature folder based on CLAUDE.md, prd.md, design.md, and state.md. Usage: /describe-feature 02_db_models"
---

You are a spec writer for the Nexus Twin project. Your job is to generate `specs.md` and `tasks.md` for a feature based on existing project documentation.

## Step 1 — Validate argument

Check `$ARGUMENTS`. It must contain the feature folder name (e.g., `02_db_models`).

If no argument was provided, stop immediately and respond:

```
⚠ You must provide the feature folder name.
Usage: /describe-feature 02_db_models
```

Do not proceed without a valid argument.

## Step 2 — Mandatory context reading

Read all of these before writing anything:

- `CLAUDE.md` — full architecture, folder structure (§3), stack (§2), conventions (§8), TDD rules (§9)
- `.specs/prd.md` — product requirements, world seed data, tick definitions
- `.specs/design.md` — full database schema, HTTP endpoints, Redis channels
- `.specs/state.md` — which features are done and which are pending (to understand what this feature can depend on)
- `.specs/features/01_project_setup/specs.md` — use as format reference for specs.md
- `.specs/features/01_project_setup/tasks.md` — use as format reference for tasks.md

Also check if the target feature folder exists:
`.specs/features/$ARGUMENTS/`

If the folder does not exist, stop and respond:
```
⚠ Folder .specs/features/$ARGUMENTS/ not found.
Check the folder name and try again.
```

## Step 3 — Analyze the feature

Before writing, reason through the following:

1. **What does this feature deliver?** Identify the exact slice of the system it covers based on `CLAUDE.md §3` and the folder name.
2. **What are its hard dependencies?** Which features must be `done` in `state.md` before this one can start? List them explicitly.
3. **Does TDD apply?** Assess whether the feature has testable logic (behavior, business rules, queries, validations) or is pure scaffolding/configuration. This determines whether the tasks.md needs a test phase.
4. **What can be parallelized?** Identify which implementation tasks have no dependency on each other and can run as parallel subagents.
5. **What is strictly out of scope?** Identify adjacent concerns that belong to other features and must be explicitly excluded.

## Step 4 — Write specs.md

Write `.specs/features/$ARGUMENTS/specs.md` in **pt-BR** following this structure:

```markdown
# Feature XX — Name

## Objetivo

One paragraph explaining what this feature delivers and why it exists.
What does it unlock for the features that depend on it?

---

## Critérios de Aceitação

Group criteria by layer when relevant (Backend, Frontend, Infraestrutura).
Each criterion must be:
- Objective and verifiable — not "works correctly" but "returns 200 with X payload"
- Tied to something in specs.md, design.md, or CLAUDE.md
- Written as a checkbox: `- [ ] ...`

---

## Fora do Escopo

Bullet list of adjacent concerns explicitly excluded from this feature.
Reference which feature covers each excluded item when known.
```

Rules for writing criteria:
- Reference exact field names, status values, and constraints from `design.md` when applicable
- For API features: reference the exact endpoints from `design.md §2`
- For agent features: reference the exact StateGraph structure from `CLAUDE.md §4.2`
- For database features: reference the exact schema from `design.md §1`
- Avoid vague criteria — every criterion must be falsifiable

## Step 5 — Write tasks.md

Write `.specs/features/$ARGUMENTS/tasks.md` in **pt-BR** following this structure:

```markdown
# Tasks — Feature XX: Name

## Antes de Começar

List the exact files the agent must read before writing any code.
Always include CLAUDE.md and the feature's specs.md.
Add design.md sections relevant to this feature.
Do NOT include files from unrelated features.

---

## Plano de Execução

Explain which groups run in parallel and which are sequential.
State dependencies explicitly.

---

### Grupo N — Description (one agent)

**Tarefa:** One sentence describing what this subagent does.

Numbered list of concrete implementation steps.
Each step names the exact file to create or modify.
Steps reference field names, class names, and method signatures from CLAUDE.md and design.md.
No ambiguity — the agent should not need to make design decisions.

---

## Condição de Conclusão

All acceptance criteria in specs.md are satisfied.
[If TDD applies]: all tests pass with pytest.
Update state.md: set feature XX status to `done`.
```

Rules for writing tasks:
- **Groups 1–N in parallel** means they are dispatched as parallel subagents via the Agent tool in a single message
- Each group must be self-contained — a subagent executing it should not need to read another group's output to do its work
- If TDD applies: Group 1 must always be the test phase, with an explicit pause instruction: "Stop after creating tests. Do not implement production logic. Wait for user approval."
- Reference exact class names, method names, and file paths from `CLAUDE.md §3`
- For complex features (agents, simulation engine), specify which files to read to avoid hallucination on business rules

## Step 6 — Present a summary

After writing both files, present to the user:

```
✓ specs.md and tasks.md created for feature XX — name

specs.md:
- N acceptance criteria across X layers
- Dependencies: features XX, XX must be done first
- TDD applies: yes/no — reason

tasks.md:
- N groups (X in parallel, Y sequential)
- [If TDD applies] Group 1 is the test phase with mandatory pause

Review the files and let me know if anything needs adjustment.
```
