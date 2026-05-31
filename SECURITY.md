# Security Policy

## Intended Use

Forge-AI is intended for a single trusted operator working on systems they own
or have explicit written authorization to administer or test. This includes a
personal workstation, a home lab, an internal development environment, or a
contracted penetration test with a defined scope.

**This project provides powerful system automation capabilities. Use only on
systems you own and control. Unauthorized use may violate computer misuse laws
in your jurisdiction.**

## Dual-Use Notice

Forge-AI combines browser automation, terminal execution, filesystem access,
persistent memory, local model orchestration, optional router administration,
and authorized security assessment tooling. Those capabilities are useful for
legitimate local automation and defensive testing, but they could be misused if
run against third-party systems or configured with excessive privileges.

The maintainer's position is that dual-use risk should be documented honestly,
paired with safe defaults, and reviewed continuously. Contributions that add
credential theft, stealth, persistence, unauthorized access, destructive
payloads, or evasion are not accepted.

## Supported Versions

Forge-AI is an early-stage project. Security fixes target the default branch
unless a release branch is explicitly documented.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately before public disclosure.

- Email/contact: open a private security advisory on GitHub for
  `ChrisAdamsdevelopment/Forge-AI`, or contact the maintainer through the
  published GitHub profile if advisories are unavailable.
- Include: affected commit or version, reproduction steps, impact, logs or
  screenshots when safe to share, and whether the issue is actively exploited.
- Do not include real third-party secrets, personal data, or exploit output from
  systems you are not authorized to test.

The maintainer will attempt to acknowledge reports within 7 days, assess impact,
and coordinate a fix and disclosure timeline appropriate to severity.

## Scope

In scope:

- Exposure of secrets or credentials through repository files, logs, or APIs
- Unsafe default filesystem access or path traversal in Forge tools
- Authentication, authorization, or network exposure issues in Forge services
- Prompt-injection paths that can trigger unintended tool execution
- Router, MCP, memory, RAG, and module-loading vulnerabilities in this codebase
- Documentation errors that materially mislead users about safe deployment

Out of scope:

- Attacks against third-party services without written authorization
- Social engineering, spam, denial-of-service, or physical attacks
- Vulnerabilities caused solely by unsafe local `.env` values or deliberate
  operator misuse outside documented safeguards
- Reports requiring destructive payloads, credential theft, persistence, evasion,
  or exfiltration to demonstrate impact

## Safe Harbor

Good-faith security research is welcome when it:

1. Targets only systems you own or are authorized to test.
2. Uses the minimum access needed to validate the issue.
3. Avoids persistence, lateral movement, data destruction, and secret collection.
4. Stops immediately if personal data or third-party secrets are encountered.
5. Reports findings privately and allows reasonable remediation time.

The maintainer will not pursue action against researchers who follow this policy
and act in good faith.

## Deployment Security Checklist

- Copy `.env.example` to `.env` and keep `.env` out of git.
- Set `FORGE_ALLOWED_ROOTS` to the narrowest directories the agent needs.
- Leave `NGROK_DOMAIN` unset unless remote access is required.
- Use strong local firewall rules for MCP and FastAPI ports.
- Store router credentials only in environment variables or a local `.env`.
- Review [THREAT_MODEL.md](THREAT_MODEL.md) before exposing Forge to any network.
