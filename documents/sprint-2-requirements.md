# FoundIt Sprint 2 Requirement Artifacts

Nov 8, 2026 · Jaycob Campos

Sprint 2 has 22 requirements worth 102 points. They are due 11:59 PM Sun Nov 22, 2026. Each artifact gives the owner, the description, the acceptance criteria, and how we test it. Every test runs in pytest on the separate test database unless it says otherwise. The design these build on is in [Architecture](architecture.md).

The team, schedule, and load per person are in [Sprint Plan](sprint-plan.md).

## Summary

| Req | Requirement | Owner | Pts |
| --- | --- | --- | --- |
| 5 | Category guess from photo, parts 5c to 5f | Jaycob | 14 |
| 7 | Photo upload on post | Jaycob | 5 |
| 9 | Filters | Nick | 3 |
| 10 | View profiles | Jonathan | 2 |
| 11 | Edit guessed category | Jaycob | 2 |
| 17 | Edit and delete own posts | Khang | 5 |
| 18 | Inbox conversations | Khang | 5 |
| 19 | Mark resolved | Khang | 2 |
| 21 | Resolved-post history | Jonathan | 3 |
| 24 | Hide private info | Nick | 3 |
| 26 | Report posts | Khang | 3 |
| 27 | Report users | Khang | 3 |
| 29 | Rate limiting | Nick | 5 |
| 31 | Cloud photo storage | Jonathan | 8 |
| 32 | Ownership questions and claims | Andrew | 8 |
| 33 | Review, approve, or deny claims | Andrew | 5 |
| 34 | Notification inbox | Lydia | 5 |
| 41 | Keyword search | Nick | 3 |
| 42 | Tests: posting and search | Lydia | 5 |
| 43 | Private messages | Lydia | 5 |
| 44 | View notifications | Lydia | 3 |
| 46 | Auto-close old posts | Nick | 5 |

## Photos and the image model

### Req 5: Category guess from photo, Sprint 2 parts

**Owner:** Jaycob Campos · **Points:** 14 of 20 · **Description:** The app guesses an item's category from its photo. It uses a pretrained image model that we fine-tuned on our labeled dataset.

**Acceptance criteria**

- 5c, 5 pts: a training pipeline loads the labeled folders. It splits them into train, validation, and test sets with a fixed seed. It saves the best weights by validation accuracy.
- 5d, 3 pts: a results log records each experiment and a confusion matrix on the validation set. It also records the test accuracy, which we measure once on the chosen model.
- 5e, 3 pts: `predict(image_bytes)` returns a category and a confidence from 0 to 1. The model loads once at app start. An unreadable image returns no category instead of an error.
- 5f, 3 pts: on the post form, a guess at or above the confidence threshold fills the category. A low-confidence guess or a model failure leaves it blank, so posting is never blocked.

**How tested:** We check 5e on 10 held-out photos the model never trained on, plus one non-image input. For 5f we write pytest cases with `predict()` replaced by a fake that returns a high guess, a low guess, and an error. The full category tests are Req 13, owned by Lydia, in Sprint 3.

### Req 7: Photo upload on post

**Owner:** Jaycob Campos · **Points:** 5 · **Description:** Users can attach a photo when they post a lost or found item.

**Acceptance criteria**

- The post form has a photo field.
- An accepted photo runs through validation and GPS stripping, then `save_photo()`, and the post's Photo row holds its storage reference.
- A non-image file shows a clear error. Neither the post nor the file is saved.
- The detail page shows the photo through `get_photo()`.

**How tested:** pytest submits the form with a JPEG that has GPS tags. It checks the Photo row exists and the stored file has no GPS data. A second case submits a text file renamed to `.jpg` and checks nothing is saved.

### Req 11: Edit guessed category

**Owner:** Jaycob Campos · **Points:** 2 · **Description:** Posters can change the guessed category before they post.

**Acceptance criteria**

- The guessed category is a normal editable field, not locked.
- The category the poster submits is the one saved, whatever the guess was.

**How tested:** pytest fakes a guess of one category, submits a different one, and checks the saved Item has the submitted category.

### Req 31: Cloud photo storage

**Owner:** Jonathan Kazmaier · **Points:** 8 · **Description:** We store uploaded item photos in a cloud service and get them back to show on posts.

**Acceptance criteria**

- 31a, 2 pts: we choose the service and bucket. Its credentials load from environment variables only.
- 31b, 3 pts: `save_photo()` uploads to the cloud service and returns a storage reference. Its signature matches the Sprint 1 stub, so callers don't change.
- 31c, 2 pts: `get_photo()` returns the photo for display on the detail page.
- 31d, 1 pt: if an upload fails, the user sees an error and no Photo row points to a missing file.

**How tested:** pytest replaces the cloud client with a fake for the save, read, and failure cases. We also do one manual check on the hosted site. We upload a photo, redeploy, and confirm the photo still shows.

## Posts, profiles, and search

### Req 9: Filters

**Owner:** Nick Heyer · **Points:** 3 · **Description:** Users can apply filters to narrow search results.

**Acceptance criteria**

- Applying a filter shows only posts that match it, and it combines with keyword search and sorting.
- Removing filters restores the full results.
- Filters use Item fields. Which filters ship is TBD.

**How tested:** pytest seeds posts with different field values, applies each filter, and checks only matches return. Clearing the filters returns every post.

### Req 10: View profiles

**Owner:** Jonathan Kazmaier · **Points:** 2 · **Description:** Users can view their own profile and other users' profiles.

**Acceptance criteria**

- A profile shows the username and that user's posts.
- Another user's profile never shows their email.
- A profile has a link to send that user a message, used by Req 43.

**How tested:** pytest opens a profile as its owner and as another user. It checks the posts listed and that the email is absent for the other user.

### Req 17: Edit and delete own posts

**Owner:** Khang Phan · **Points:** 5 · **Description:** Users can edit or delete their own item posts.

**Acceptance criteria**

- The owner can change any post field or delete the post.
- Edits are validated the same way as a new post.
- Every edit and delete route checks ownership. Another signed-in user is refused, so nothing changes.

**How tested:** pytest edits and deletes as the owner and checks the database. It repeats both as a second user and as a signed-out visitor, and checks the post is unchanged.

### Req 19: Mark resolved

**Owner:** Khang Phan · **Points:** 2 · **Description:** Users can mark their own posts resolved when the item is returned.

**Acceptance criteria**

- The owner can mark a post resolved, and the `resolved` flag is saved.
- The detail page shows the post as resolved.
- Only the owner can do this.

**How tested:** pytest marks a post resolved as the owner, checks the flag and the detail page, then checks a second user is refused.

### Req 21: Resolved-post history

**Owner:** Jonathan Kazmaier · **Points:** 3 · **Description:** Users can view a history of their resolved posts. This is a spillover candidate.

**Acceptance criteria**

- A history page lists only the signed-in user's resolved posts.
- Each entry opens its detail page.

**How tested:** pytest seeds resolved and open posts for two users and checks each user sees only their own resolved posts.

### Req 24: Hide private info

**Owner:** Nick Heyer · **Points:** 3 · **Description:** The app hides email addresses and private information from public profiles and posts. This is a spillover candidate.

**Acceptance criteria**

- Public pages show only a poster's username.
- A user's email appears on no public page. Only the owner sees it on their account page.

**How tested:** pytest loads browse, detail, search, and profile pages as another user and checks a seeded email string is absent. It loads the account page as the owner and checks the email is present.

### Req 41: Keyword search

**Owner:** Nick Heyer · **Points:** 3 · **Description:** Users can search with keywords to narrow the list of items.

**Acceptance criteria**

- A keyword returns the posts whose text matches it, case-insensitive.
- Search is a database query and does not use the image model.
- No match shows an empty-results message instead of an error.

**How tested:** pytest seeds posts with known titles and descriptions and checks matching, case, and no-match searches. Covered again by Req 42.

### Req 46: Auto-close old posts

**Owner:** Nick Heyer · **Points:** 5 · **Description:** Resolved or old posts past a certain age with no interactions are closed and archived.

**Acceptance criteria**

- A scheduled job closes posts that are resolved, or older than the cutoff with no claims or messages.
- Closed posts leave browse and search but stay in the owner's history.
- The cutoff age is TBD. The Data Model has no closed or archived field, so we add one by migration.

**How tested:** pytest runs the job's function directly on seeded posts. We seed an old post with no interactions, an old post with a message, a new post, and a resolved post. It checks which ones closed.

## Claims, messages, and notifications

### Req 32: Ownership questions and claims

**Owner:** Andrew Kruckemyer · **Points:** 8 · **Description:** Posters can set ownership questions, and users can submit claims with answers and supporting details.

**Acceptance criteria**

- 32a, 2 pts: a poster of a found item can set ownership questions, saved in `ownership_questions`.
- 32b, 2 pts: the claim form shows that post's questions.
- 32c, 3 pts: submitting saves a Claim row with the answers and status pending. We decide where supporting details go before this part.
- 32d, 1 pt: claim rules. We propose that a user can't claim their own post and has at most one pending claim per item. Andrew confirms these.

**How tested:** pytest sets questions as the poster, submits a claim as a second user, and checks the Claim row. It checks the poster is refused on their own post and a second pending claim is refused.

### Req 33: Review, approve, or deny claims

**Owner:** Andrew Kruckemyer · **Points:** 5 · **Description:** Posters can review, approve, or deny claims, and claimants can view their claim status.

**Acceptance criteria**

- The poster sees every claim on their post with its answers.
- Only the poster can approve or deny, and the claim status updates.
- The claimant sees the current status of each of their claims.

**How tested:** pytest approves one claim and denies another as the poster and checks both statuses and the claimant's view. It checks a third user is refused.

### Req 43: Private messages

**Owner:** Lydia Peng · **Points:** 5 · **Description:** Users can message other users from a profile or a post, and reply from their inbox.

**Acceptance criteria**

- A message button on a post and on a profile opens a message form.
- Sending saves a Message row with sender, recipient, item, text, and time.
- Only the sender and recipient can read a message.
- The recipient can reply from their inbox.

**How tested:** pytest sends a message, replies to it, and checks both rows. It checks a third user can't open the conversation.

### Req 18: Inbox conversations

**Owner:** Khang Phan · **Points:** 5 · **Description:** Users can view their conversations in an inbox.

**Acceptance criteria**

- The inbox groups messages into one conversation per other user and item.
- Conversations are ordered by their newest message.
- Opening a conversation shows its messages oldest to newest.

**How tested:** pytest seeds messages across two items and three users and checks the grouping and order each user sees.

### Req 34: Notification inbox

**Owner:** Lydia Peng · **Points:** 5 · **Description:** We store notifications from new claims, claim status updates, and private messages in an inbox.

**Acceptance criteria**

- Submitting a claim notifies the poster. Changing a claim's status notifies the claimant. Sending a message notifies the recipient.
- Each notification is stored unread for the right user.
- The notification inbox lists only the signed-in user's notifications, newest first, with unread ones marked.

**How tested:** pytest runs each of the three events and checks one unread Notification row for the right user. It checks another user's inbox is empty.

### Req 44: View notifications

**Owner:** Lydia Peng · **Points:** 3 · **Description:** Users can open a notification and go straight to the page it is about. This is a spillover candidate.

**Acceptance criteria**

- A claim notification opens that claim. A message notification opens that conversation.
- Opening a notification marks it read.

**How tested:** pytest opens each kind of notification, checks the redirect target, and checks `read` is now true.

## Moderation and security

### Req 26: Report posts

**Owner:** Khang Phan · **Points:** 3 · **Description:** Users can report an inappropriate post for admin review.

**Acceptance criteria**

- A signed-in user can report a post with a reason.
- A Report row is saved with the reporter, `target_item_id`, reason, and an open status for admin review in Req 35.

**How tested:** pytest reports a post and checks the Report row. It checks a signed-out visitor is refused.

### Req 27: Report users

**Owner:** Khang Phan · **Points:** 3 · **Description:** Users can report another user for abusive behavior.

**Acceptance criteria**

- A signed-in user can report another user from their profile with a reason.
- A Report row is saved with the reporter, `target_user_id`, reason, and an open status.
- A user can't report themselves.

**How tested:** pytest reports a second user and checks the Report row, then checks a self-report is refused.

### Req 29: Rate limiting

**Owner:** Nick Heyer · **Points:** 5 · **Description:** The backend limits excessive requests and repeated posting to reduce spam.

**Acceptance criteria**

- 29a, 2 pts: a limiter applies one global request limit.
- 29b, 2 pts: a stricter limit applies to creating posts.
- 29c, 1 pt: going over a limit shows an error page in the shared layout. Nothing is saved.
- The limit values are TBD and live in configuration, not code.

**How tested:** pytest sets low limits in the test config and posts one past the limit. It checks the error page and that the extra post was not saved. Req 45 tests spam resistance again in Sprint 3.

## Tests

### Req 42: Tests for posting and search

**Owner:** Lydia Peng · **Points:** 5 · **Description:** Automated tests cover posting with a photo, browsing, viewing, and searching items.

**Acceptance criteria**

- Tests cover create post with and without a photo, a rejected non-image, browse, detail view, keyword search, and filters.
- The cloud client and the model are replaced with fakes, so the tests run offline.
- All tests pass on the separate test database.

**How tested:** this requirement is the tests. It is done when `pytest` passes in a clean checkout. It runs last in Sprint 2.
