# Tasker-Style Module System

## Goal

Forge should let users build, run, share, import, and modify reusable AI modules the way Tasker lets Android users build reusable automations.

A Forge module is a portable workflow package.

## Module use cases

- summarize a folder
- research a company
- inspect a GitHub repo
- clean metadata from media files
- generate YouTube SEO
- triage logs
- draft legal-style evidence timelines
- convert notes into a project plan
- run a terminal test suite
- create a song release checklist
- monitor a URL and summarize changes
- run a local RAG query against a chosen knowledge pack

## Module package contents

A module folder contains:

- `module.yaml`
- `README.md`
- `prompts/main.md`
- `prompts/critique.md` optional
- `schemas/input.schema.json`
- `schemas/output.schema.json`
- `policy/tool_policy.yaml`
- `examples/example_input.json`
- `examples/example_output.md`
- `tests/golden_tasks.yaml`

## Module execution model

1. User picks module.
2. Forge renders the module input form from JSON Schema.
3. Forge validates input.
4. Forge loads module prompt templates.
5. Forge checks requested tools against module policy.
6. Forge asks for approval if needed.
7. Forge runs steps.
8. Forge writes output to the module output folder.
9. Forge logs all tool calls and decisions.
10. Forge offers export/share.

## Module safety model

Modules must declare:

- requested tools
- file roots
- network access
- whether terminal is needed
- destructive actions
- secrets needed
- whether human approval is required

Modules imported from other users start disabled until reviewed.

## Module marketplace idea

Forge can support a simple community module exchange:

- modules are zipped folders
- every module has a manifest
- every manifest has permissions
- users can inspect before enabling
- modules can be rated and forked
- risky modules are clearly labeled
