## Workflow

When asked to implement a phase or feature, read the relevant scope/design document first and confirm understanding before writing code. Do not start coding until the plan is clear.

After completing implementation work, update the relevant scope.md or design documentation to reflect what was built and any deviations from the plan.

## Code Standards

- This is a Python project. Use Python 3.11+ for all new code.
- Use type hints throughout. Run `python -m mypy <file>` when adding non-trivial logic.
- No bare `except:` — always catch specific exceptions.

## Debugging

When debugging environment/config issues, always check for conflicting environment variables (shell env overriding .env files, wrong env var names, dotenv load ordering) before assuming API keys are invalid or accounts are misconfigured.

## Deployment

When working with production databases or deployments (especially Railway), double-check environment variable names, connection string formatting, and test commands locally before running against production.
