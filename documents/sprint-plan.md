# FoundIt Sprint Plan

Nov 8, 2026 · Jaycob Campos

We have three sprints and 219 points, and we finish Sun Nov 29, 2026. The design is in [Architecture](architecture.md). What counts as done for each Sprint 2 requirement is in [Sprint 2 Requirements](sprint-2-requirements.md).

## Team

Each person holds two roles, and Jaycob is also Project Manager.

| Person | Name | Roles |
| --- | --- | --- |
| A | Jaycob Campos | Project Manager, ML Lead, ML Engineer |
| B | Khang Phan | Backend Lead, Posts, Profiles and Reports Dev |
| C | Andrew Kruckemyer | Database and DevOps, Claims Dev |
| D | Nick Heyer | Security, Admin and Docs, Search and Browse Dev |
| E | Jonathan Kazmaier | Frontend Lead, Image Pipeline Dev |
| F | Lydia Peng | QA Lead, Messaging and Notifications Dev |

## Sprints

Sprint 1 is lighter for midterms and Sprint 3 is lighter for Thanksgiving, so Sprint 2 carries the most work.

| Sprint | Due, 11:59 PM | Days | Points | Also due that night |
| --- | --- | --- | --- | --- |
| 1 | Sun Nov 8, 2026 | 11 | 71 | Sprint 2 requirements |
| 2 | Sun Nov 22, 2026 | 14 | 102 | Sprint 3 requirements |
| 3 | Sun Nov 29, 2026 | 7 | 46 | None |

### Load per person

| Person | Roles | Sprint 1 | Sprint 2 | Sprint 3 | Total |
| --- | --- | --- | --- | --- | --- |
| Jaycob | PM, ML Lead, ML Engineer | 14 | 21 | 5 | 40 |
| Khang | Backend Lead, Posts, Profiles and Reports | 18 | 18 | 5 | 41 |
| Andrew | Database and DevOps, Claims | 20 | 13 | 8 | 41 |
| Nick | Security, Admin and Docs, Search and Browse | 11 | 19 | 5 | 35 |
| Jonathan | Frontend Lead, Image Pipeline | 3 | 13 | 10 | 26 |
| Lydia | QA Lead, Messaging and Notifications | 5 | 18 | 13 | 36 |

## Changes from the original plan

We re-estimated points for a team that writes code by hand, so the total went from 187 to 219. Copy these changes into the requirements spreadsheet.

### Sprint moves

- Reqs 25 and 39 moved into Sprint 1.
- Req 5 was split. Parts 5a and 5b are in Sprint 1, and 5c to 5f are in Sprint 2.
- Reqs 7, 31, 41, and 42 moved from Sprint 1 to Sprint 2, so we do photo attach and cloud storage together.

### Point changes

| Req | Old | New | Why |
| --- | --- | --- | --- |
| 2 | 2 | 3 | First ORM model and relationships |
| 3 | 3 | 5 | Sessions and validation are new |
| 5 | 13 | 20 | First hand-written ML project, dataset and training pipeline |
| 6 | 2 | 3 | Check real file content, not only the extension |
| 17 | 3 | 5 | Ownership check on every route |
| 18 | 3 | 5 | Grouping messages into conversations |
| 25 | 3 | 5 | EXIF handling, orientation, proof the data is gone |
| 30 | 3 | 5 | Ban enforced across routes |
| 31 | 5 | 8 | First cloud SDK |
| 38 | 5 | 8 | Seven tables, keys, migrations |
| 40 | 3 | 5 | First pytest and fixtures |
| 45 | 5 | 8 | Spans claims, messaging, edits, spam resistance |
| 46 | 3 | 5 | Scheduled job is a new concept |

### Ownership changes

| Req | From | To | Why |
| --- | --- | --- | --- |
| 6, 7, 25 | Jonathan | Jaycob | The model needs the cleaned photo, so Jaycob owns the photo input path |
| 2 | Andrew | Khang | Khang owns login, which needs the users table |
| 45 | Lydia | Andrew | Andrew owns claims |
| 13, 14 | Jaycob | Lydia | Frees Jaycob's time for the model |
| 35 | Nick | Jonathan | The admin page is mostly UI |
| 10, 21 | Khang | Jonathan | Page-heavy work |
| 18, 30 | Lydia, Nick | Khang | Balance |
| 46 | Khang | Nick | Closing old posts is an admin action |

## Sprint 2 order

We do the risky items first, and a checkpoint on Sun Nov 15 decides what ships.

- **Week 1, Nov 8 to 15:** Reqs 31, 5c, 32, 7, 10, and 29. Req 10 is early because private messages need profiles.
- **Checkpoint, Sun Nov 15:** we decide if the model is good enough to ship or if the fallback ships. We also decide spillover.
- **Week 2, Nov 15 to 22:** everything else. The posting and search tests, Req 42, go last.
- **Spillover candidates:** Reqs 21, 44, and 24, 9 points in all. Nothing else should move, since Sprint 3 has little slack.
- **If Sprint 3 runs over:** keep 45, 37, 12, 13, 14, 35, and 36. Cut 20, 28, and 30 first.

### Decisions due

| Decision | Owner | Decide by |
| --- | --- | --- |
| Hosting provider and cloud storage provider | Andrew, Jonathan | Sprint 2 week 1 |
| Category list and the source of the training photos | Jaycob | Sprint 2 week 1 |
| Image formats accepted | Jaycob | Sprint 2 week 1 |
| Whether the Req 39 trigger wiring is built inside Req 34 | Andrew, Lydia | Sprint 2 week 1 |
| Where a claim's supporting details go, and the claim rules | Andrew | Before Req 32c |
| Where the model weights file lives | Jaycob | Before Req 5e |
| Which filters ship | Nick | Before Req 9 |
| Rate limit values | Nick | Before Req 29a |
| Cutoff age for closing old posts | Nick | Before Req 46 |
| Minimum test accuracy and the fallback confidence threshold | Jaycob | Checkpoint, Sun Nov 15 |
| Midterm dates, and whether a fourth sprint exists | Jaycob | When known |
