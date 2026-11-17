"use strict";

// Uses apiRequest, escapeHtml, setStatus, renderFieldErrors, and postCard from posts.js.

function profileName(profile) {
  return profile.display_name || `User #${profile.id}`;
}

function pageLink(page, label) {
  return `<a class="button secondary" href="?page=${page}">${label}</a>`;
}

async function setupProfile() {
  const container = document.querySelector("#profile");
  if (!container) return;

  const status = container.querySelector("#profile-status");
  const summary = container.querySelector("#profile-summary");
  const list = container.querySelector("#profile-posts");
  const pager = container.querySelector("#profile-pages");
  const page = Number.parseInt(new URLSearchParams(window.location.search).get("page"), 10) || 1;

  try {
    const { data } = await apiRequest(`/api/profiles/${container.dataset.userId}?page=${page}`);
    const { profile, posts, pagination } = data;
    const name = profileName(profile);
    const joined = new Date(profile.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" });
    const stats = profile.stats;

    document.title = `${name} · Lost and Found`;
    status.hidden = true;
    summary.innerHTML = `
      <h1>${escapeHtml(name)}</h1>
      ${profile.bio ? `<p class="description">${escapeHtml(profile.bio)}</p>` : ""}
      <p class="meta">Member since ${escapeHtml(joined)} · ${stats.total_posts} posts · ${stats.total_resolved} resolved</p>`;
    list.innerHTML = posts.length ? posts.map(postCard).join("") : '<p class="empty">No posts yet.</p>';
    pager.innerHTML = [
      pagination.has_prev ? pageLink(pagination.page - 1, "Previous") : "",
      pagination.has_next ? pageLink(pagination.page + 1, "Next") : "",
    ].join("");
  } catch (error) {
    setStatus(status, error.message, true);
  }
}

function setupProfileForm() {
  const form = document.querySelector("#profile-form");
  if (!form) return;

  const status = form.querySelector("#profile-form-status");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    renderFieldErrors(form);
    setStatus(status, "Saving…");

    // The API rejects a blank name, so leave it out to keep the current one unset.
    const payload = { bio: form.elements.bio.value };
    const name = form.elements.display_name.value.trim();
    if (name) payload.display_name = name;

    try {
      await apiRequest("/api/profiles/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      window.location.assign("/profiles/me");
    } catch (error) {
      renderFieldErrors(form, error.data?.errors);
      setStatus(status, error.data?.errors ? "Please fix the highlighted fields." : error.message, true);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupProfile();
  setupProfileForm();
});
