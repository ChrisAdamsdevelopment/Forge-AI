# SOP: Coding Workflows

## Goal

Safely inspect, modify, and test code inside approved roots.

## Steps

1. Identify repository root.
2. Read README and package/config files.
3. Inspect relevant files.
4. Build a minimal patch plan.
5. Make the smallest complete change.
6. Run targeted tests.
7. Run build/lint if available.
8. Report exact files changed and tests run.

## Approval required

- installing packages
- deleting files
- running networked scripts
- modifying system configuration
- pushing commits
- changing secrets or auth configuration
