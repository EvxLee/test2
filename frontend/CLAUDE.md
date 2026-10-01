# Atlas Frontend — Claude Code Guide

## Project Overview

React 19 + React Router v7 (SSR enabled) + Vite + TypeScript (strict mode). Styled with Tailwind CSS v4. Authenticates via Keycloak OAuth 2.0 PKCE.

## Feature Development Workflow

1. **Plan first.** Before writing code, use plan mode to outline the approach. Identify which files need changes and how they connect.
2. **Create a plan document.** Save it to `.claude/plan/` in markdown format with a checklist of tasks.
3. **Review and iterate.** Read through the plan carefully. If details are missing or unclear, iterate with Claude Code until the plan is complete and you fully understand the approach.
4. **Implement.** Follow the plan and write the code according to the conventions below.
5. **Update the plan.** As you complete each item, mark it as done in the plan document.
6. **Manual testing.** Verify the feature works as intended before moving to test code.
7. **Plan the tests.** Outline what test code is needed to validate the feature.
8. **Write and run tests.** Implement the test code. Run `npm test` and confirm all tests pass. Do not commit code that fails tests, type checking, or build.

Before committing, ensure:
- Type checking passes (`npm run typecheck`)
- Tests pass (`npm test`)
- Dev server builds cleanly (`npm run build`)
- Code follows the conventions below

## Conventions

- TypeScript strict mode. No `any` types — define interfaces for all props and data.
- Functional components with explicit prop interfaces.
- Use `useState` for local state, React Context for shared state (see `contexts/`).
- Tailwind utility classes for styling. No inline style objects unless unavoidable.
- Use `lucide-react` for icons, `framer-motion` for animations.
- Path aliases: `~/` and `app/` both resolve to the `app/` directory.
- Place reusable components in `app/components/`, route-specific ones in `app/routes/`.
- Data fetching with `axios` and Bearer token auth.

## Project Structure

```
app/
├── routes/        # Page components (React Router file-based routing)
├── components/    # Shared UI components
├── contexts/      # React Context providers
├── types/         # TypeScript type definitions
├── lib/           # Utility functions
└── auth.ts        # Keycloak auth helpers
```

## Testing

- Framework: Vitest + React Testing Library (jsdom environment).
- Config: `vitest.config.ts` (separate from `vite.config.ts` to avoid `@react-router/dev/vite` plugin conflicts).
- `npm test` — run all tests once. `npm run test:watch` — watch mode.
- Place test files next to the source file they test with a `.test.ts` / `.test.tsx` suffix.

## Git

- Branch from and merge into `develop`.
- Do not commit `.env` files or secrets.
