# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: **Security → Report a vulnerability** on this repository
(private vulnerability reporting). Include steps to reproduce and the impact you observed.

You can expect an acknowledgement within a few days. Please give reasonable time for a fix
before any public disclosure.

## Scope

In scope: the GhostCommit application code in this repository (backend API, frontend, the
haunter job, Docker and deployment configuration).

Out of scope: third-party services GhostCommit integrates with (GitHub, Backboard, OpenRouter,
Resend, Render). Please report issues in those to their own security teams.

## Known, accepted risk

Commit contents and READMEs are sent to the language model, so a malicious repository could try
to steer the ghost's wording (prompt injection). Output is always rendered as escaped text and is
only ever shown to the owner of that repository.
