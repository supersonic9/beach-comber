---
name: debug-hypotheses
description: "Structured debugging workflow. Before attempting any fix, list 3 root cause hypotheses ranked by likelihood, each with a diagnostic command to confirm or rule it out. Then wait for the user to choose which to investigate. Trigger on: error messages, unexpected behavior, test failures, config issues."
---

# Debug Hypotheses

When the user describes an error or unexpected behavior, follow this protocol **before writing any fix**:

## Protocol

1. Identify the error or symptom from the user's message.
2. Generate exactly **3 hypotheses** for the root cause, ranked by likelihood (most likely first).
3. For each hypothesis, provide:
   - A clear label (e.g. "H1 — Mismatched env variable")
   - Why it's plausible given the symptoms
   - One diagnostic command or check that would **confirm or rule it out**
4. **Stop. Wait for the user to pick a hypothesis before doing anything else.**

## Output Format

```
I see: [brief restatement of the error]

Root cause hypotheses, ranked by likelihood:

H1 — [Name] (most likely)
Why: ...
Diagnose with: `<command>`

H2 — [Name]
Why: ...
Diagnose with: `<command>`

...

Which would you like to investigate first?
```

## Rules

- Do NOT attempt a fix before being asked.
- Do NOT run diagnostic commands yourself — present them for the user to run.
- If the user provides output from a diagnostic, update the rankings and proceed with the next step.
- Keep hypotheses distinct — don't list variations of the same cause.
