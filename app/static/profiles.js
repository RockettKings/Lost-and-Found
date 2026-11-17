"use strict";

// Uses apiRequest, escapeHtml, setStatus, renderFieldErrors, and postCard from posts.js.

function profileName(profile) {
  return profile.display_name || `User #${profile.id}`;
}

function pageLink(page, label) {
  return `<a class="button secondary" href="?page=${page}">${label}</a>`;
}

function currentPage() {
  return Number.parseInt(new URLSearchParams(window.location.search).get("page"), 10) || 1;
}

function renderPostPage(list, pager, posts, pagination, emptyMessage) {
  list.innerHTML = posts.length
    ? posts.map(postCard).join("")
    : `<p class="empty">${escapeHtml(emptyMessage)}</p>`;
  pager.innerHTML = [
    pagination.has_prev ? pageLink(pagination.page - 1, "Previous") : "",
    pagination.has_next ? pageLink(pagination.page + 1, "Next") : "",
  ].join("");
}

async function setupProfile() {
  const container = document.querySelector("#profile");
  if (!container) return;

  const status = container.querySelector("#profile-status");
  const summary = container.querySelector("#profile-summary");

  try {
    const { data } = await apiRequest(`/api/profiles/${container.dataset.userId}?page=${currentPage()}`);
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
    renderPostPage(container.querySelector("#profile-posts"), container.querySelector("#profile-pages"),
                   posts, pagination, "No posts yet.");
  } catch (error) {
    setStatus(status, error.message, true);
  }
}

async function setupResolvedHistory() {
  const container = document.querySelector("#resolved-history");
  if (!container) return;

  const status = container.querySelector("#history-status");
  try {
    const { data } = await apiRequest(
      `/api/profiles/${container.dataset.userId}?resolved=true&page=${currentPage()}`);
    status.hidden = true;
    renderPostPage(container.querySelector("#history-posts"), container.querySelector("#history-pages"),
                   data.posts, data.pagination, "You have no resolved posts yet.");
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
  setupResolvedHistory();
  setupProfileForm();
});
