# Module Safety Contract

Every module must answer these questions before installation:

## Identity

- Who created this module?
- What does it claim to do?
- What version is it?

## Permissions

- What tools does it request?
- What file roots does it need?
- Does it need network access?
- Does it need terminal access?
- Does it need browser automation?
- Does it read or write files?
- Does it create, delete, rename, or move files?

## Risk classification

| Risk | Meaning |
|---|---|
| low | prompt-only or read-only |
| medium | writes output files or uses web fetch |
| high | terminal, browser automation, package installs, repo modification |
| critical | secrets, system config, deletion, external publishing |

## Required controls

- high risk requires approval before each risky run
- critical risk disabled unless manually edited and enabled
- imported modules cannot request broad filesystem roots by default
- modules cannot hide requested permissions
- all module runs are logged
