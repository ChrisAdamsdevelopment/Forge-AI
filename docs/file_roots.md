# File Roots Policy

## Principle

Forge should not access the full computer by default. It should operate inside explicit roots.

## Recommended roots

| Root | Purpose | Access |
|---|---|---|
| `/srv/forge/workspace` | Active project files | read/write with approval for destructive actions |
| `/srv/forge/knowledge` | Curated RAG source docs | read-only by default |
| `/srv/forge/output` | Generated outputs | read/write |
| `/srv/forge/inbox` | Files dropped for analysis | read/write |
| `/srv/forge/modules` | Installed modules | read-only until module install/update |
| `/srv/forge/logs` | Audit logs | append-only |

## Never default-access

- home directory root
- password manager files
- browser profile directories
- SSH key directories
- cloud sync roots unless explicitly selected
- system folders
- financial/legal/medical archives unless intentionally scoped

## Root declaration example

```json
{
  "roots": [
    {"name": "workspace", "path": "/srv/forge/workspace", "mode": "read_write"},
    {"name": "knowledge", "path": "/srv/forge/knowledge", "mode": "read_only"},
    {"name": "output", "path": "/srv/forge/output", "mode": "read_write"}
  ]
}
```
