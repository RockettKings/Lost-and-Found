# FoundIt Sprint 3 Requirement Artifacts

Nov 22, 2026 · Jaycob Campos

Sprint 3 has 10 requirements worth 46 points, plus the Req 5g integration check, which is not pointed yet. They are due 11:59 PM Sun Nov 29, 2026. This is the last sprint, and it is short because of Thanksgiving on Thu Nov 26. Each artifact gives the owner, the description, the acceptance criteria, and how we test it. Every test runs in pytest on the separate test database unless it says otherwise. The design is in [Architecture](architecture.md), and the team and load per person are in [Sprint Plan](sprint-plan.md).

## Summary

| Req | Requirement | Owner | Pts |
| --- | --- | --- | --- |
| 5g | Photo path integration check | Jaycob | TBD |
| 12 | Photo search | Jaycob | 5 |
| 13 | Tests: category guess | Lydia | 5 |
| 14 | Tests: photo search | Lydia | 5 |
| 20 | Sort posts | Nick | 2 |
| 28 | Phone-friendly pages | Jonathan | 5 |
| 30 | Admin bans | Khang | 5 |
| 35 | Admin report review page | Jonathan | 5 |
| 36 | Tests: admin permissions | Lydia | 3 |
| 37 | README | Nick | 3 |
| 45 | Tests: claim flow end to end | Andrew | 8 |

### Load per person

| Person | Sprint 3 work | Pts |
| --- | --- | --- |
| Jaycob | 12, 5g | 5 + 5g |
| Khang | 30 | 5 |
| Andrew | 45 | 8 |
| Nick | 20, 37 | 5 |
| Jonathan | 28, 35 | 10 |
| Lydia | 13, 14, 36 | 13 |

## Before Sprint 3 starts

Sprint 3 builds on Sprint 2 code that still lives on separate branches. So on Sun Nov 22, each owner merges their finished Sprint 2 branch into main and checks that `pytest` passes on main. Nobody starts Sprint 3 work until their Sprint 2 branch is merged.

Spillover from Sprint 2 is decided at the Sprint 2 review. Only Reqs 21, 44, and 24 should move, as planned. Anything that spills over goes ahead of the owner's Sprint 3 work.

## Photos and the image model

### Req 12: Photo search

**Owner:** Jaycob Campos · **Points:** 5 · **Description:** Users can upload a photo to search for items in matching categories. The image model decides the category.

**Acceptance criteria**

- The search page has a photo field.
- The photo runs through the same validation as a post photo. A non-image file shows a clear error.
- The search photo is never saved. It is not uploaded to cloud storage and no Item points to it.
- `predict()` guesses the category, and the page shows the guess with the open posts in that category, newest first.
- Resolved and closed posts are not shown.
- A low-confidence guess or a model failure shows a message and a link to keyword search instead of an error.
- We propose the results show found posts only, since the searcher lost the item. Jaycob confirms this before building it.

**How tested:** Req 14, owned by Lydia, tests photo search. Jaycob also tries it by hand on the hosted site with a photo of a real item.

### Req 5g: Photo path integration check

**Owner:** Jaycob Campos · **Points:** TBD · **Description:** We confirm the whole photo path works end to end on the hosted site.

**Acceptance criteria**

- A post with a photo runs through `process_photo()`, is saved with the real `save_photo()`, and shows on the detail page.
- The saved photo has no GPS data.
- A non-image upload is rejected and nothing is saved.
- The model's guess fills the category, or the category stays blank on the fallback. The poster can change it, per Req 11.

**How tested:** a manual check on the hosted site after the final deploy. Jaycob posts a JPEG with GPS tags, downloads the stored photo, and confirms the GPS data is gone. He then tries a text file renamed to `.jpg`. The results go in the Sprint 3 meeting log.

## Posts and pages

### Req 20: Sort posts

**Owner:** Nick Heyer · **Points:** 2 · **Description:** Users can sort item posts by newest or oldest first.

**Acceptance criteria**

- The browse page has a sort control with newest and oldest. Newest is the default.
- Sorting combines with keyword search and filters.
- The posts API already takes `sort=newest` or `sort=oldest`. The work left is the page control and its test.

**How tested:** pytest seeds posts with different dates and checks the order for each sort, alone and with a keyword. It also checks a bad sort value is refused.

### Req 28: Phone-friendly pages

**Owner:** Jonathan Kazmaier · **Points:** 5 · **Description:** The app's main pages work on phone screens without horizontal scrolling.

**Acceptance criteria**

- 28a, 1 pt: the shared layout is responsive and keeps the viewport tag.
- 28b, 1 pt: the navigation works on a narrow screen.
- 28c, 2 pts: forms and post cards fit the screen width.
- 28d, 1 pt: a phone-width check of every main page.
- Which pages count as main pages and the phone width we check are TBD. Jonathan sets both before 28d.

**How tested:** a manual check in the browser's device mode at the chosen width. Jonathan opens each main page, confirms there is no horizontal scroll, and takes a screenshot for the sprint record.

## Moderation and admin

### Req 30: Admin bans

**Owner:** Khang Phan · **Points:** 5 · **Description:** Admins can ban users from posting or interacting with other users.

**Acceptance criteria**

- An admin can ban and unban a user. Only admins can do this, and an admin can't ban themselves.
- A banned flag is added to the users table by migration.
- A banned user is refused on every route that creates or changes something. That covers posts, edits, claims, messages, and reports. Nothing is saved.
- A banned user sees a clear message that the account is banned.
- Admin rights still come only from the `flask make-admin` command, never from the website.
- What a banned user can still read is TBD. Khang decides before he builds it.

**How tested:** pytest bans a user as an admin, then tries each blocked action as that user and checks nothing was saved. It unbans the user and checks posting works again. Req 36 tests who can ban.

### Req 35: Admin report review page

**Owner:** Jonathan Kazmaier · **Points:** 5 · **Description:** Admins can open an admin page to review reports and delete inappropriate, redundant, or invalid posts.

**Acceptance criteria**

- An admin-only page lists open post and user reports, newest first, with the reporter, the target, and the reason.
- From a post report, the admin can delete the post or dismiss the report. Either one closes the report.
- From a user report, the admin can go to Req 30's ban action or dismiss the report.
- Any other user, signed in or not, is refused.
- This needs the Report table from Reqs 26 and 27.

**How tested:** pytest seeds reports, deletes a post and dismisses a report as an admin, and checks the post and report statuses. Req 36 tests who can open the page.

## Tests

### Req 13: Tests for the category guess

**Owner:** Lydia Peng · **Points:** 5 · **Description:** Tests check the category guess works on a few sample photos.

**Acceptance criteria**

- A small set of labeled sample photos lives in the tests folder. None of them were used in training.
- For each photo, `predict()` returns a category from the category list and a confidence from 0 to 1.
- At least the minimum accuracy Jaycob set at the Sprint 2 checkpoint is correct on the sample set.
- An unreadable image returns no category instead of an error.
- With `predict()` replaced by a fake, the post form fills the category on a high guess and leaves it blank on a low guess or an error.
- If the model weights file is not present, the real-model tests skip with a clear reason and the fake-model tests still run.

**How tested:** this requirement is the tests. It is done when `pytest` passes in a clean checkout.

### Req 14: Tests for photo search

**Owner:** Lydia Peng · **Points:** 5 · **Description:** Tests check photo search finds a matching item in sample data.

**Acceptance criteria**

- Tests seed posts in several categories, plus a resolved post in the searched category.
- With `predict()` replaced by a fake, a search returns only the open posts in the guessed category.
- A non-image upload is refused, and a low guess or a model error shows the fallback message.
- The cloud client is a fake, and the tests check that a search uploads nothing.

**How tested:** this requirement is the tests. It is done when `pytest` passes in a clean checkout.

### Req 36: Tests for admin permissions

**Owner:** Lydia Peng · **Points:** 3 · **Description:** Tests check that admin actions work and that only admins can use them.

**Acceptance criteria**

- Every admin route refuses a signed-out visitor and a signed-in user who is not an admin. That covers the report page, deleting a post, dismissing a report, and banning and unbanning.
- An admin can do each of those actions.
- No website route can change `is_admin`.

**How tested:** this requirement is the tests. It is done when `pytest` passes in a clean checkout.

### Req 45: Tests for the claim flow end to end

**Owner:** Andrew Kruckemyer · **Points:** 8 · **Description:** Tests cover a missing item from posting to claim, including claim status, private messages, editing and deleting posts, and spam resistance.

**Acceptance criteria**

- 45a, 2 pts: shared fixtures for a poster, a claimant, a third user, and a found post with ownership questions.
- 45b, 2 pts: the claim flow. The claimant submits a claim, the poster approves or denies it, and the claimant sees the new status.
- 45c, 1 pt: messaging. The claimant and poster message each other, and the third user can't read it.
- 45d, 1 pt: edit and delete. The owner can, and the other two users are refused.
- 45e, 2 pts: spam resistance. With low limits in the test config, the request one past the limit is refused and nothing is saved.

**How tested:** this requirement is the tests. It is done when `pytest` passes in a clean checkout.

## Docs

### Req 37: README

**Owner:** Nick Heyer · **Points:** 3 · **Description:** The README explains the app's purpose, setup, required environment variables, how to run it, and how to run the tests.

**Acceptance criteria**

- It covers purpose, setup, every environment variable in `.env.example`, how to run the app, and how to run the tests.
- It explains the admin commands `flask make-admin`, `flask remove-admin`, and `flask close-old-posts`.
- It says where the model weights file goes.
- It links to the hosted site.

**How tested:** a teammate who did not write it follows it on a clean checkout. They run the app and `pytest` with no help.

## Sprint 3 order

Sprint 3 has 7 days and a holiday in the middle, so the order matters.

- **Sun Nov 22:** merge all Sprint 2 branches into main and confirm `pytest` passes.
- **Mon Nov 23 to Wed Nov 25:** Reqs 12, 30, 35, 20, and 28. Lydia starts the Req 13 tests and Andrew starts 45a and 45b, since they already have the code they need.
- **Thu Nov 26:** Thanksgiving. No work is planned.
- **Fri Nov 27 to Sat Nov 28:** Reqs 14 and 36, which need 12, 30, and 35 merged. Andrew finishes 45. Final deploy.
- **Sun Nov 29:** Req 5g on the hosted site, Req 37 last so it matches the final app, and the final review.
- **If we run over:** keep 45, 37, 12, 13, 14, 35, 36, and 5g. Cut 20, 28, and 30 first. If 30 is cut, Req 36 drops the ban cases.

### Dependencies

| Req | Needs |
| --- | --- |
| 5g | 7, 11, 31, and 5f merged and deployed |
| 12 | 5e and the weights file |
| 13 | 5e, 5f, and the weights file |
| 14 | 12 |
| 30 | `is_admin` from Sprint 2, already on Nick's branch |
| 35 | Report table from 26 and 27 |
| 36 | 30 and 35 |
| 45 | 17, 29, 32, 33, and 43 |
| 37 | The final environment variables and deploy |

### Decisions due

| Decision | Owner | Decide by |
| --- | --- | --- |
| Points for 5g | Jaycob | Sun Nov 22 |
| Whether photo search shows found posts only | Jaycob | Before Req 12 |
| What a banned user can still read | Khang | Before Req 30 |
| Which pages are main pages, and the phone width we check | Jonathan | Before Req 28d |
| Where the sample photos for Req 13 come from | Jaycob, Lydia | Before Req 13 |
