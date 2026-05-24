# Prompt Engineer Module

This module is disabled by default and designed to transform raw user intent into optimized Claude-compatible prompt artifacts.

## Modes

- **A — Single Prompt:** Clean and optimize one prompt.
- **B — Prompt Chain:** Produce sequenced prompts with handoff payloads.
- **C — System Prompt Design:** Produce reusable role/system instructions for repeated tasks.

## Safety and quality constraints

- Preserve user intent and constraints.
- Reduce token overhead and ambiguity.
- Avoid fabricating requirements not provided by the user.
- Emit copy-paste-ready output sections.
