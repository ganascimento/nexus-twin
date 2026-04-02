---
name: build-feature
description: "Development orchestrator for the Nexus Twin project. Executes a feature end-to-end: reads specs.md and tasks.md, applies TDD (Phase 1: tests, Phase 2: implementation), dispatches parallel subagents, and updates state.md. Usage: /build-feature 03"
---

You are the development orchestrator for the Nexus Twin project. Your job is to execute a feature from start to finish following the development process defined in `CLAUDE.md`.

## Step 1 — Mandatory context reading

Read these files before any other action:
- `CLAUDE.md` — conventions, architecture, TDD rules (§9)
- `.specs/state.md` — current progress across all features

## Step 2 — Confirm which feature to execute

Check the argument passed to the command (`$ARGUMENTS`):

- **If a number was passed** (e.g., `/feature 03`): use the feature with that number.
- **If no argument was passed**: identify the next feature with `pending` status in `state.md` and present to the user:

```
Next pending feature: 02 — db_models
Dependencies done: ✓ 01 (project_setup)

Proceed with this feature? (y/n) — or provide a different number.
```

Wait for confirmation before continuing.

## Step 3 — Read the feature files

Read both files for the confirmed feature:
- `.specs/features/XX_name/specs.md` — objective and acceptance criteria
- `.specs/features/XX_name/tasks.md` — execution plan and orchestration

If either file is empty or missing, stop and inform the user:
```
⚠ specs.md or tasks.md for feature XX is empty. Fill them in before executing.
```

Also update `state.md` now: set the feature status to `in_progress`.

## Step 4 — Check if TDD applies

Assess whether the feature contains **testable logic** — behavior, business rules, transformations, queries, validations.

**TDD does NOT apply when:**
- The feature is pure scaffolding (e.g., `01_project_setup`)
- Artifacts are declarative with no behavior (creating folders, configuring dependencies)
- Validation is done through environment checks (healthcheck, `tsc --noEmit`)

**TDD APPLIES when:**
- The feature implements logic with inputs/outputs (repositories, services, guardrails, agents, simulation engine, tools)
- There are business rules that can be violated
- Behavior can be tested in isolation with mocks

If TDD **does not apply**, inform the user and skip to Step 6.

If TDD **applies**, continue to Step 5.

## Step 5 — Phase 1: Tests (only if TDD applies)

⚠ **This phase ends with a mandatory pause. Do not advance to implementation without explicit user approval.**

Execute the feature's test plan:

1. Read the acceptance criteria from `specs.md` — each criterion must have at least one corresponding test
2. Read `CLAUDE.md §9` to recall the project's TDD conventions
3. Create all test files under `backend/tests/unit/` and/or `backend/tests/integration/` as indicated in `tasks.md`
4. Use `FakeListChatModel` from LangChain to mock LLM calls in agent tests
5. Use a mocked `WorldState` for tests that depend on world state
6. **Do not implement any production logic in this phase** — stubs and `NotImplementedError` are acceptable in production files so the tests can exist

When Phase 1 is complete, present to the user:

```
✓ Phase 1 complete — X test files created

Files created:
- backend/tests/unit/test_foo.py (N tests)
- backend/tests/unit/test_bar.py (N tests)

Criteria covered:
- [ ] criterion 1 → test_foo::test_normal_case, test_foo::test_edge_case
- [ ] criterion 2 → test_bar::test_validation

⏸ Waiting for approval to start Phase 2 (implementation).
Review the tests and reply: approved / revise [what to change]
```

**Stop and wait.** Do not continue until the user replies with "approved" or equivalent.

## Step 6 — Phase 2: Implementation

Execute the implementation plan from `tasks.md` exactly as written:

1. **Respect the parallelization plan**: independent groups must be dispatched as parallel subagents via the `Agent` tool in a single message; groups with dependencies run sequentially
2. **Each subagent** must receive in its prompt:
   - Which files to read before starting (always include `CLAUDE.md` and the feature's `specs.md`)
   - Which files to create or modify
   - The exact scope of the group — no extrapolation to other features
3. **Mandatory conventions** (from `CLAUDE.md §8`):
   - All code in English
   - No docstrings
   - No redundant comments
   - Expressive, self-explanatory names
4. If TDD applies: the implementation must make the Phase 1 tests pass — run `pytest` at the end of each group to verify

## Step 7 — Final validation

After all groups complete:

1. If TDD applies: run `pytest backend/tests/` and confirm all feature tests pass
2. Check each acceptance criterion in `specs.md` — mark the ones that are satisfied
3. If any criterion is not satisfied, fix it before proceeding

## Step 8 — Update state.md

Once all acceptance criteria are confirmed satisfied:

1. Update `.specs/state.md`: change the feature status from `in_progress` to `done`
2. If any relevant implementation decision was made (library choice, non-obvious trade-off, deviation from spec), record it in the "Implementation Decisions" section with the format: `[feature_XX] decision — reason`

## Step 9 — Final report

Present to the user:

```
✓ Feature XX — name complete

Criteria satisfied:
- [x] criterion 1
- [x] criterion 2
...

Tests: X passing / 0 failing  (or "N/A — TDD not applicable")
state.md: updated → done

Next pending feature: XX — name
```
