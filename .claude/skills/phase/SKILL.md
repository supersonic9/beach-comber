---
name: phase
description: Implement the next phase of the project from the scope/plan document
---

# Implement Next Phase

1. Find the project's phase/scope document — check for `scope.md`, `PLAN.md`, `phases.md`, or similar. If none exists, ask the user where phases are tracked before proceeding.
2. Identify the next unimplemented phase. If it's ambiguous, list the candidates and ask.
3. Summarize what you plan to build and wait for confirmation before writing any code.
4. Implement the phase across all relevant files.
5. If the project uses TypeScript, run `npx tsc --noEmit` to verify no type errors.
6. If tests exist, run them and confirm they pass.
7. Update the scope/phase document to mark the phase complete and note any deviations from the original plan.
