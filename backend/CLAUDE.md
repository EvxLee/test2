# Atlas Backend — Claude Code Guide

## Project Overview

Flask REST API with SQLAlchemy ORM, PostgreSQL (pgvector), and Alembic migrations. Integrates with Monday.com, HubSpot, PitchBook, and AWS Bedrock.

## Feature Development Workflow

1. **Plan first.** Before writing code, use plan mode to outline the approach. Identify which files need changes and how they connect.
2. **Create a plan document.** Save it to `.claude/plan/` in markdown format with a checklist of tasks.
3. **Review and iterate.** Read through the plan carefully. If details are missing or unclear, iterate with Claude Code until the plan is complete and you fully understand the approach.
4. **Implement.** Follow the plan and write the code according to the conventions below.
5. **Update the plan.** As you complete each item, mark it as done in the plan document.
6. **Manual testing.** Verify the feature works as intended before moving to test code.
7. **Plan the tests.** Outline what test code is needed to validate the feature.
8. **Write and run tests.** Implement the test code. Run `pytest` and confirm all tests pass. Do not commit code that fails tests or linting.

Before committing, ensure:
- All tests pass (`pytest`)
- Linting passes (`flake8` and `autopep8`)
- Code follows the conventions below

## Conventions

- Python 3.11+. Use modern type hints (`str | None`, `Mapped[]`).
- Follow PEP 8. Run `flake8` and `autopep8` before committing.
- SQLAlchemy 2.0 declarative style with `Mapped` type annotations.
- 4-space indentation, UTF-8, LF line endings.
- Organize new features into their own module under `product/api/`.

## Testing

```bash
# From the backend/ directory
pytest
```

Use pytest fixtures and mocks. Write tests for new functionality.

## Database Changes

- Create Alembic migrations for any model changes: `alembic revision --autogenerate -m "description"`
- Review generated migrations before applying.

## Git

- Branch from and merge into `develop`.
- Do not commit `.env` files or secrets.
