# Project Service

FastAPI backend for the ACME project management platform, deployed as one AWS
Lambda. Request path: browser → proxy (local) or CloudFront (AWS) → Lambda →
PostgreSQL.

| File | Purpose |
|---|---|
| `function.py` | Lambda entry point (Mangum adapter) |
| `app/main.py` | Application factory |
| `app/config.py` | Environment variables |
| `app/database.py` | PostgreSQL engine and sessions |
| `app/errors.py` | Shared error format |
| `app/routers/` | One module per feature |
| `app/auth/` | Passwords, tokens, role permissions and record-level rules |
| `app/services/` | Business logic |
| `app/schemas/` | Request and response formats |
| `app/models/` | Database tables, one module per domain |
| `migrations/` | Alembic schema changes |

## Endpoints

| Method | Path | Result |
|---|---|---|
| GET | `/health` | 200 when the service runs |
| GET | `/health/ready` | 200 when PostgreSQL responds, 503 when it does not |
| POST | `/auth/login`, `/auth/refresh` | Get tokens (public) |
| POST | `/auth/logout`, `/auth/change-password` | Any signed-in user |
| GET | `/auth/me` | Any signed-in user |
| All | `/users` | Admin |
| GET | `/departments` | Any signed-in user |
| POST, PUT, DELETE | `/departments` | Admin |
| GET, PUT | `/settings` | Admin |
| GET | `/projects`, `/projects/{id}`, `/projects/options` | Projects the user may view |
| PUT | `/projects/{id}` | Admin, or the project's manager |
| GET | `/deliverables`, `/deliverables/{id}`, `/deliverables/options` | Deliverables the user may view |
| PATCH | `/deliverables/{id}/progress` | Admin, the project's manager or the owner |
| PUT, DELETE | `/deliverables/{id}` | Admin, or the project's manager |
| POST | `/projects/{id}/deliverables` | Admin, or the project's manager |
| POST, DELETE | `/deliverables/{id}/predecessors` | Admin, or the project's manager |
| GET | `/projects/{id}/dependencies` | Admin, or the project's manager |
| GET | `/projects/{id}/milestones` | Anyone who may view the project |
| POST, PUT, DELETE | `/projects/{id}/milestones` | Admin, or the project's manager |
| GET | `/resources`, `/resources/{id}`, `/resources/options`, `/resources/workload` | Admin, project managers |
| POST, PUT, DELETE | `/resources` | Admin |
| GET | `/projects/{id}/assignments` | Admin, project managers who may view the project |
| POST, PUT, DELETE | `/projects/{id}/assignments` | Admin, or the project's manager |
| POST | `/projects/{id}/insights` | Admin, or the project's manager |
| GET | `/dashboard` | Admin, project managers (their own projects) |
| GET | `/budgets`, `/expenses`, `/projects/{id}/budget` | Admin, or the project's manager |
| POST | `/projects/{id}/expenses` | Admin, or the project's manager |
| PUT, DELETE | `/expenses/{id}` | Admin, or the project's manager |
| GET | `/expense-categories` | Admin, project managers |
| POST, PUT, DELETE | `/expense-categories` | Admin |
| POST, DELETE | `/projects` | Admin; deleting needs `confirm_code` |

Send the access token as `Authorization: Bearer <token>`. It lasts 30 minutes; the
refresh token lasts 8 hours. Signing out invalidates every token of the account.
Tokens are signed with `JWT_SECRET`, which Terraform generates.

## Commands (from the repository root)

```sh
# Start everything
./bin/start-dev.sh

# Check the API through the proxy
curl http://localhost:3001/api/project-service/health/ready

# Set up and run the tests (Python 3.13)
python3.13 -m venv .venv
.venv/bin/python -m pip install -r tests/backend/requirements-dev.txt
.venv/bin/python -m pytest tests/backend
```

Database tests are skipped unless `POSTGRES_PASS` is set. They create and drop
their own temporary database and never touch the development one.

## Migrations

```sh
cd backend/project-service
export IS_LOCAL=true POSTGRES_PASS=<local password>
../../.venv/bin/alembic current        # Show the applied version
../../.venv/bin/alembic upgrade head   # Apply new migrations
../../.venv/bin/alembic check          # Confirm the models match
```

## Create the first admin

There is no default account. Apply the migrations, then run this and type a
password of at least 12 characters:

```sh
cd backend/project-service
export IS_LOCAL=true POSTGRES_PASS=<local password>
../../.venv/bin/python -m app.cli --email you@example.com --name "Your Name"
```

## Dependency rules

1. A deliverable is blocked while any direct predecessor is not completed. This is
   calculated from the dependencies, so it clears itself.
2. Blocked work cannot be started or completed.
3. Completed work cannot be reopened while a successor is completed.
4. Circular dependencies are rejected by a database trigger.
5. A deliverable that others depend on cannot be deleted.
6. Completed and cancelled projects accept no changes to their work.

## Workload rules

1. Capacity and allocation are percentages of a full-time week. Hours are derived from
   the `full_time_hours_per_week` setting, so they are not stored.
2. Assignments only add up on days when they overlap.
3. The current load is today's total. The peak load is the highest total on any day of
   the period, which starts today unless stated otherwise.
4. A resource is over-allocated when the peak is higher than their own capacity.
5. Utilization is the peak divided by the capacity.
6. Assignments of completed and cancelled projects do not count.
7. Over-allocation is reported, not refused. Unavailable people cannot be assigned.

## Budget rules

1. Only expenses are stored. Actual is their sum, remaining is planned minus actual, and
   consumed is actual divided by planned. All use exact decimals.
2. Spending exactly the planned amount is not over budget.
3. `budget_warning_percent` sets when a warning starts.

## Risk rules

Only open projects are assessed. The level is the most severe reason.

| Reason | Medium | High |
|---|---|---|
| Deadline passed | | Always |
| Behind schedule | Gap of `schedule_lag_percent` or more | Twice that or more |
| Overdue deliverables | Any | Any critical one |
| Critical deliverable blocked | | Always |
| Budget | Warning | Over budget |
| Over-allocated people | During their time on the project | |

## AI Insights

Explains one project's latest data on request. It saves and changes nothing.

1. All figures come from the existing calculations. The AI provider (Google Gemini) may not
   write digits: it uses placeholders that this service fills with verified values. Text
   with digits or unknown placeholders is discarded.
2. The provider never receives names or emails of people, descriptions or expense texts.
   It does receive project, deliverable and milestone names, job titles and figures.
3. Without a key, or when the provider fails, fixed rules write the observations. They
   are labelled as rule-based.

The key is read from `GEMINI_API_KEY`. Locally, `bin/set-ai-key.sh` stores it in the
LocalStack Lambda. Every generation is one request. On
Google's free tier, requests are limited and Google may use the data to improve its
products, so use it for demo data only.
