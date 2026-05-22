# Module Marketplace Model

## Goal

Allow users to share Forge modules safely.

## Package format

A module is distributed as a ZIP file containing a manifest and its module folder.

## Import process

1. User imports ZIP.
2. Forge extracts to quarantine.
3. Forge validates manifest.
4. Forge displays permission summary.
5. Forge runs static checks.
6. User edits permissions if desired.
7. User enables module.

## Static checks

- no hidden files by default
- no executable scripts unless declared
- no external URLs unless declared
- no terminal access unless declared
- no broad roots
- no request for secrets unless declared
- no missing schemas
- no invalid YAML/JSON

## Sharing metadata

A shared module should include:

- name
- description
- category
- author
- version
- license
- permissions
- screenshots optional
- example input/output
- test results

## Fork model

Users can fork modules to:

- change prompts
- reduce permissions
- swap models
- add examples
- add tests
- change output format
