# Ownership claims — Andrew, requirements 32 and 33

Implemented on the `database` branch. This uses the app's existing Flask-Login,
Flask-WTF/CSRF protection, SQLAlchemy, and styles. No new dependencies are needed.

## Setup

After pulling this branch, activate the virtual environment and run:

```sh
python -m flask --app run db upgrade
python -m pytest -q
```

Migration `0004` adds `items.ownership_questions` and the `claims` table. Existing
accounts/posts are preserved. No questions are invented for existing posts.
Downgrading `0004` removes questions and claim history; it keeps accounts and posts.

## Rules

- Only the poster can set questions on a found-item post: 1–3 questions, up to
  200 characters each. Questions freeze after any claim or when the item is resolved.
- A signed-in user can claim an unresolved found item with questions, but not their
  own post. The form checks that its questions haven't changed since it was opened.
- Each answer is required and limited to 1,000 characters. Additional supporting
  details are optional text, up to 2,000 characters. No evidence uploads or chat.
- Each claim saves the question text alongside its answers. These answers and
  details are private; the public post API does not serialize them.
- One pending claim per user per item. A denied user can resubmit while the item
  still accepts claims. There may be many pending claimants, but at most one approved
  claim per item. SQLite partial unique indexes guard competing writes.
- Only the poster can change a pending claim to `approved` or `denied`. Final
  decisions cannot be rewritten. Other pending claims remain for the poster to deny.
- Approval blocks new claims but does not mark the item resolved. Khang's resolution
  workflow remains separate. Pending claims on a resolved item can still be denied.
- Lists show 20 claims per page. A claimant sees only their own history; a poster
  sees claims only for their own items.
- The existing post-update route has one added guard: a found item with claims
  cannot become a lost item. Other edits/resolution still use the existing routes.
- Deleting an item also deletes its claims through a foreign-key cascade. Deleting
  an account that claims/posts still reference is restricted, as with existing posts.

## Pages and form contracts for Jon

These are ordinary server-rendered forms, not new JSON endpoints. They are usable
now; Jon can change layout/styles in `app/templates/claims/` without changing the
field names. They use the existing shared base template.

| Route | Methods | Who / purpose |
| --- | --- | --- |
| `/posts/<item_id>/ownership-questions` | GET, POST | Poster sets or views questions |
| `/posts/<item_id>/claims/new` | GET, POST | Another signed-in user submits a claim |
| `/posts/<item_id>/claims` | GET | Poster reviews received claims |
| `/claims/mine` | GET | Claimant views their own history/statuses |
| `/claims/<claim_id>/review` | POST | Poster approves or denies |

Questions use `questions-0`, `questions-1`, `questions-2`. The submission form uses
`answers-0` etc., `supporting_details`, and the server-provided `questions_version`.
Keep that hidden version field so stale forms cannot silently answer new questions.
Review buttons submit `decision=approved` or `decision=denied`. Every POST needs
the existing CSRF token (`form.hidden_tag()`). The logged-in identity determines
ownership; forms cannot set the claimant, item, or initial status themselves.

Successful POSTs redirect with 303. Invalid form fields return 400, forbidden access
403, nonexistent records 404, conflicting/final/closed states 409, and unexpected
database failures 503 with no private answers in the response. Signed-out users
are redirected to login. Authorization is enforced on the server regardless of links.

The post detail page has links for questions/review or submitting a claim. Signed-in
navigation has **My claims**. No redesign of post forms or the overall site was done.

## Handoff to Lydia

Notification creation/inbox work remains requirement 34. The two integration points
are in `app/claims/routes.py`: successful claim submission (`submit`) and successful
decision (`review`). A new claim should notify the item's poster; a decision should
notify the claimant. Coordinate transaction handling before wiring notifications so
a failed/repeated request cannot create a duplicate or misleading notification.

No notification or messaging tables/routes were added by this feature. The claim
ID, item ID, poster ID, claimant ID, and resulting status are available at these
integration points. Preserve the permission checks and transaction boundaries.

## Manual check

1. Sign in as a poster, create a found item, open it, and save ownership questions.
2. Sign in as a different user and submit answers through **Claim this item**.
3. Sign in as a third user: they cannot read or review the first user's claim.
4. As the poster, open **Review claims**, inspect the answers, and approve or deny.
5. As the claimant, open **My claims** and confirm the updated status.
