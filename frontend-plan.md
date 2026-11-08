# Sprint 1 frontend plan

Plain HTML first. Every step below is a working page. Visual styling is the last step, after the behavior is in place.

Branch off `posts`. That branch has the Flask app, the account pages, and the post JSON API. `main` only has the README.

```bash
git fetch origin
git checkout -b frontend origin/posts
```

The JSON routes under `/posts/` already have tests. Those URLs stay JSON. New screens get their own URLs and read or write the same `Item` rows.

Stories with no page are out of this plan: users table, data tables, notifications table, hosting, environment secrets, password hashing, GPS stripping, and the account pytest suite.

## 1. Shared layout and 404

Board: Req 1. Architecture: app setup.

`app/templates/base.html` already has the header, nav, and flash messages. Keep that structure.

- Add a 404 template that extends `base.html`, and register a 404 handler so an unknown URL uses it.
- Stop printing `current_user.email` in the nav. The sprint story says a public page shows a username only, and the `User` model has no username column yet. Until that column exists, the nav says "Account" for a signed-in user.
- Login, signup, and logout links stay as they are.

Check: `/` still loads, `/this-page-does-not-exist` shows the 404 inside the same header, and the header never shows an email address.

## 2. Register, log in, and log out

Board: Req 3, 3a, 3b, 3c. Architecture: register and log in.

These pages already work on `posts`: `app/templates/auth/login.html` and `register.html`. Do not rebuild them.

Confirm this behavior still holds after the layout change:

- A new account can be created and lands on the home page.
- A duplicate email gets a clear error.
- Mismatched passwords are rejected.
- A wrong password and an unknown email both show "Invalid email or password."
- Logout returns to the home page.

## 3. Browse posts

Board: Req 8. Architecture: browse items.

Replace the "Listings coming soon" placeholder on `/`.

- The home route loads `Item` rows, newest `created_at` first.
- Each row shows the title, lost/found type, category, and date, and links to that item's detail page.
- An empty database shows a short "no posts yet" line.

Check: two saved items show as two links. `/posts/` still returns JSON.

## 4. Keyword search, filters, and sort

Board: Req 9 and Req 20 are still in the backlog; the architecture sprint list includes them with browse. Build them on the home page.

One GET form on `/`:

- `q` matches title or description, case-insensitive.
- `category` is a text field.
- `listing_type` is lost, found, or either.
- Sort is newest or oldest by `date_reported`.

Submitting the form reloads `/` with query parameters. A "Clear" link goes back to `/` with no parameters.

Leave `GET /posts/` alone. Its tests already cover `category`, `listing_type`, and `created_at` descending, and they expect JSON.

Check: a keyword returns only matching rows, a lost/found choice narrows the list, clearing the form restores every row, and both sort orders work.

## 5. View item details

Board: Req 16, assigned to JonKazz. Architecture: view details.

Add `GET /items/<id>`. Do not change `GET /posts/<id>`, which returns JSON.

The page shows title, description, category, date reported, general location, and lost/found status. When `photo_key` is set and `photo_url()` can build a link, show the image. Otherwise omit the image.

A missing id renders the 404 page.

Check: a real item shows every field above, and `/posts/<id>` is still JSON.

## 6. Create a post

Board: Req 15, 15a, 15b, 15c. Architecture: create post.

Add `GET/POST /items/new`. Login required. The form fields are title, description, category, listing type (lost or found), general location, and date reported.

- Empty required fields redisplay the form with an error on each field.
- A valid submit creates an `Item` owned by the current user and redirects to that item's detail page.
- Include the CSRF token, same as the logout form.

The existing `POST /posts/` JSON route stays for the tests.

Check: a logged-out visitor is sent to login. A logged-in user can create a post and see it on the detail page and on the home list.

## 7. Edit and delete

Board: Req 17. Architecture: edit and delete own posts.

- `GET/POST /items/<id>/edit` for the owner. Same fields as create. Saving returns to the detail page.
- `POST /items/<id>/delete` for the owner, with a confirm button on the detail page. Deleting returns home and the row is gone.
- Anyone who is not the owner does not see these controls. Posting to either URL returns 403.

`PATCH` and `DELETE` on `/posts/<id>` stay as they are.

Check: the owner can change a title and can delete the post. A second account can open the detail page and cannot edit or delete it.

## 8. Mark resolved

Board: Req 19. Architecture: mark resolved.

`Item` has no resolved column on `posts`. This step adds that flag, then the control.

- Add a `resolved` boolean, default false, with a migration.
- On the owner's detail page, a "Mark resolved" button posts to `POST /items/<id>/resolve`.
- The detail page and the home list both show Resolved or Open.
- Another user does not see the button.

Check: marking a post resolved survives a refresh, and the home list shows the new state.

## 9. Photo field

Board: Req 6 (done on `photo-pipeline`) and Req 7 (in progress). Architecture: validate the file, attach a photo, show it from cloud storage.

Add a file input to the create and edit forms.

- A non-image is rejected with a clear error and nothing is stored.
- A real image is handed to the photo pipeline's processing function, then `save_photo()`, and the returned key is stored on `photo_key`.
- If that processing function is not on this branch yet, keep the file input and the rejection error, and skip the save. Do not write raw uploads into S3 from this form. `save_photo()` only accepts a cleaned JPEG.
- The detail page from step 5 already shows the image once `photo_key` is set.

GPS stripping stays on `photo-pipeline`. This form does not read or display location metadata.

Check: a `.txt` file shows an error and creates no photo. After the pipeline function is available, a JPEG shows up on the detail page.

## 10. Make it look better

No new behavior in this step. Do it after steps 1–9 work.

- Add one stylesheet, or Bootstrap from a CDN in `base.html`.
- Space the header, forms, list, and detail page.
- Stack the list and the forms in one column on a phone so the page does not scroll sideways.

Check the same flows from steps 1–9 on a narrow window. Search, create, edit, delete, resolve, and the photo error should behave the same as before.
