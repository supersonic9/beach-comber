## Workflow

When asked to implement a phase or feature, read the relevant scope/design document first and confirm understanding before writing code. Do not start coding until the plan is clear.

After completing implementation work, update the relevant scope.md or design documentation to reflect what was built and any deviations from the plan.

## Code Standards

- This is primarily a TypeScript project. Use TypeScript for all new code. Always run `npx tsc --noEmit` after making changes to verify type-checking passes.
- Do not cast to `unknown` or use `any` in Typescript 
- For styling - use seperate stylesheet files and avoid inline styles 

## Debugging

When debugging environment/config issues, always check for conflicting environment variables (shell env overriding .env files, wrong env var names, dotenv load ordering) before assuming API keys are invalid or accounts are misconfigured.

## Deployment

When working with production databases or deployments (especially Railway), double-check environment variable names, connection string formatting, and test commands locally before running against production.
