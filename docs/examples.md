# Good Output Examples

## Research answer pattern

### Finding
The project should start with local control plane plus optional remote GPU inference.

### Evidence
- Local control keeps prompts, files, logs, and tool policies private.
- Remote GPU can be rented only when heavy models are needed.

### Confidence
High for budget-first architecture. Medium for exact model choice until hardware is measured.

### Next step
Run a hardware inventory module and classify the laptop's RAM, CPU, GPU, and storage.

## Coding answer pattern

### Diagnosis
The backend URL is hardcoded to localhost, which will break production deployment.

### Fix
Move the backend URL into an environment variable and fail fast in production if unset.

### Test
Run `npm run build`, then verify registration calls the deployed API URL.

## Module answer pattern

### Module
Repo Inspector

### Purpose
Analyze a code repository and produce a risk-ranked implementation report.

### Inputs
- repo_path
- task_description
- depth

### Tools
- filesystem read
- git status
- terminal test command with approval

### Output
- summary
- files inspected
- findings
- recommended patch plan
