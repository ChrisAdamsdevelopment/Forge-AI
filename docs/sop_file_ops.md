# SOP: File Operations

## Safe automatic operations

- list approved directories
- read files inside approved roots
- write new files to output root
- create draft patches
- create backups before edits

## Approval required

- delete file
- overwrite important source file
- mass rename
- move directories
- edit files outside workspace root
- read sensitive directories
- chmod/chown
- package install scripts

## Logging requirement

Every file operation must log:

- timestamp
- tool name
- requested path
- resolved path
- action
- result
- approval id if required
