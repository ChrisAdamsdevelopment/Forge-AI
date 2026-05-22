# Forge Module Architecture

## Definition

A Forge module is a portable automation package.

It combines:
- prompt templates
- input schema
- output schema
- tool requirements
- safety contract
- optional workflow steps
- tests
- examples

## Module lifecycle

1. Create
2. Validate
3. Install
4. Review permissions
5. Enable
6. Run
7. Log
8. Rate
9. Export/share
10. Update/fork

## Required module files

```text
module-name/
  module.yaml
  README.md
  prompts/main.md
  schemas/input.schema.json
  schemas/output.schema.json
  policy/tool_policy.yaml
  examples/example_input.json
  examples/example_output.md
  tests/golden_tasks.yaml
```

## Execution modes

### Prompt-only module

Uses no tools. It transforms input into output.

### RAG module

Uses a knowledge collection and cites sources.

### Tool module

Uses approved tools such as filesystem, git, fetch, browser, terminal.

### Workflow module

Runs multiple steps and passes outputs from one step into the next.

### Watcher module

Runs on a schedule or trigger and notifies when conditions match.

## Module trust levels

- local_created
- imported_unreviewed
- imported_reviewed
- signed_trusted
- disabled

Unreviewed imported modules cannot execute terminal or destructive tools.
