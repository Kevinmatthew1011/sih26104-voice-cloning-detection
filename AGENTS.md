# AGENTS.md

## Always-On Project Rules

- Follow the project workflow:
  IDEA → PRD → TECH STACK → ARCHITECTURE → DATABASE → BUILD → TEST → REVIEW → DEBUG.

- Before modifying code:
  - inspect the relevant files first;
  - understand the existing implementation;
  - preserve current architecture and conventions;
  - avoid rewriting working code unnecessarily.

- Prefer small, focused changes over broad refactors.

- Never fabricate:
  - datasets;
  - benchmark results;
  - evaluation metrics;
  - model performance;
  - test results.

- Do not modify `.env`, private keys, certificates, credentials, or secrets unless explicitly requested.

- Do not run destructive Git or filesystem commands without explicit approval.

- Do not commit, push, reset, clean, delete branches, or rewrite Git history without explicit approval.

- Do not install, remove, or upgrade dependencies without explicit approval.

- Use existing project services, validators, schemas, factories, and abstractions instead of bypassing them.

- When a task matches a project skill in `.agents/skills/`, load and follow that skill.

- After implementation:
  - run the relevant tests;
  - run applicable build/lint/type checks;
  - review the diff;
  - fix the root cause of failures rather than weakening tests.

- Never claim a task is complete unless the required verification actually passed.

- Preserve the stable `main` branch unless explicitly instructed otherwise.
