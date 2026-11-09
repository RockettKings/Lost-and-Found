"use strict";

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

async function apiRequest(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && !["GET", "HEAD"].includes(options.method.toUpperCase())) {
    headers.set("X-CSRFToken", csrfToken);
  }

  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers
  });

  if (response.status === 204) {
    return { response, data: null };
  }

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : { error: await response.text() };

  if (!response.ok) {
    const error = new Error(data.error || "The request could not be completed.");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return { response, data };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function setStatus(element, message, isError = false) {
  if (!element) return;
  element.textContent = message || "";
  element.classList.toggle("error", Boolean(isError));
}

function renderFieldErrors(form, errors = {}) {
  form.querySelectorAll("[data-error-for]").forEach((element) => {
    element.textContent = "";
  });
  Object.entries(errors).forEach(([field, message]) => {
    const target = form.querySelector(`[data-error-for="${CSS.escape(field)}"]`);
    if (target) target.textContent = message;
  });
}

function postCard(post) {
  const photo = post.photo_url
    ? `<img class="post-photo-thumb" src="${escapeHtml(post.photo_url)}" alt="Photo of ${escapeHtml(post.title)}">`
    : "";
  return `
    <li class="card post-card">
      <a class="post-title" href="/posts/${post.id}">${escapeHtml(post.title)}</a>
      <div class="tags">
        <span class="tag ${post.listing_type}">${post.listing_type === "lost" ? "Lost" : "Found"}</span>
        <span class="tag ${post.resolved ? "resolved" : "open"}">${post.resolved ? "Resolved" : "Open"}</span>
      </div>
      <div class="meta">${escapeHtml(post.category)} · ${escapeHtml(post.date_reported)}</div>
      ${photo}
    </li>`;
}

async function loadPostList(params = new URLSearchParams()) {
  const list = document.querySelector("#post-list");
  const status = document.querySelector("#post-list-status");
  if (!list) return;

  setStatus(status, "Loading posts…");
  list.replaceChildren();

  try {
    const query = params.toString();
    const { data } = await apiRequest(`/api/posts/${query ? `?${query}` : ""}`);
    const posts = data.posts || [];
    if (!posts.length) {
      setStatus(status, "No matching posts.");
      return;
    }
    list.innerHTML = posts.map(postCard).join("");
    setStatus(status, `${posts.length} post(s) found.`);
  } catch (error) {
    setStatus(status, error.message, true);
  }
}

function setupSearch() {
  const form = document.querySelector("#post-search-form");
  if (!form) return;

  const paramsFromForm = () => {
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form).entries()) {
      if (String(value).trim()) params.set(key, String(value).trim());
    }
    return params;
  };

  const initial = new URLSearchParams(window.location.search);
  for (const [key, value] of initial.entries()) {
    const field = form.elements.namedItem(key);
    if (field) field.value = value;
  }
  if (!form.elements.namedItem("sort").value) form.elements.namedItem("sort").value = "newest";

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const params = paramsFromForm();
    const query = params.toString();
    history.pushState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    loadPostList(params);
  });

  form.addEventListener("reset", () => {
    // Reset events fire before controls return to their defaults.
    window.setTimeout(() => {
      const sort = form.elements.namedItem("sort");
      if (sort) sort.value = "newest";
      history.pushState({}, "", window.location.pathname);
      loadPostList();
    }, 0);
  });

  window.addEventListener("popstate", () => {
    const params = new URLSearchParams(window.location.search);
    for (const field of form.elements) {
      if (field.name && params.has(field.name)) field.value = params.get(field.name);
      else if (field.name === "sort") field.value = "newest";
      else if (field.name) field.value = "";
    }
    loadPostList(params);
  });

  loadPostList(initial);
}

function populateForm(form, post) {
  for (const field of ["title", "description", "category", "listing_type",
    "general_location", "date_reported"]) {
    const input = form.elements.namedItem(field);
    if (input) input.value = post[field] ?? "";
  }

  if (post.photo_url) {
    const area = form.querySelector("#current-photo-area");
    area.innerHTML = `<img class="post-photo-thumb" src="${escapeHtml(post.photo_url)}" alt="Current post photo">`;
    form.querySelector("#remove-photo-label").hidden = false;
  }
}

async function setupPostForm() {
  const form = document.querySelector("#post-form");
  if (!form) return;

  const status = form.querySelector("#post-form-status");
  const mode = form.dataset.mode;
  const postId = form.dataset.postId;
  const dateInput = form.elements.namedItem("date_reported");

  if (mode === "create" && dateInput) {
    const today = new Date();
    const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
      .toISOString().slice(0, 10);
    dateInput.value = localDate;
  }

  if (mode === "edit") {
    try {
      setStatus(status, "Loading post…");
      const { data } = await apiRequest(`/api/posts/${postId}`);
      populateForm(form, data.post);
      setStatus(status, "");
    } catch (error) {
      setStatus(status, error.message, true);
      form.querySelector('button[type="submit"]').disabled = true;
      return;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    renderFieldErrors(form);
    setStatus(status, mode === "create" ? "Creating post…" : "Saving changes…");

    const formData = new FormData(form);
    if (mode === "edit") {
      formData.delete("remove_photo");
      if (form.querySelector("#remove_photo")?.checked) {
        formData.set("remove_photo", "true");
      }
    }

    try {
      const url = mode === "create" ? "/api/posts/" : `/api/posts/${postId}`;
      const method = mode === "create" ? "POST" : "PATCH";
      const { data } = await apiRequest(url, { method, body: formData });
      window.location.href = `/posts/${data.post.id}`;
    } catch (error) {
      const errors = error.data?.errors || {};
      renderFieldErrors(form, errors);
      const general = error.data?.error || errors.body || "Please correct the highlighted fields.";
      setStatus(status, general, true);
    }
  });
}

function detailMarkup(post) {
  const photo = post.photo_url
    ? `<img class="post-detail-photo" src="${escapeHtml(post.photo_url)}" alt="Photo of ${escapeHtml(post.title)}">`
    : "";
  const ownerActions = post.is_owner ? `
    <div class="actions">
      <a class="button secondary" href="/posts/${post.id}/edit">Edit</a>
      ${post.resolved ? "" : '<button class="button" type="button" id="resolve-post">Mark resolved</button>'}
      <button class="button danger" type="button" id="delete-post">Delete post</button>
    </div>` : "";

  return `
    <article class="card">
      <h1>${escapeHtml(post.title)}</h1>
      <div class="tags">
        <span class="tag ${post.listing_type}">${post.listing_type === "lost" ? "Lost" : "Found"}</span>
        <span class="tag ${post.resolved ? "resolved" : "open"}">${post.resolved ? "Resolved" : "Open"}</span>
      </div>
      <dl class="details">
        <dt>Category</dt><dd>${escapeHtml(post.category)}</dd>
        <dt>Date reported</dt><dd>${escapeHtml(post.date_reported)}</dd>
        <dt>Location</dt><dd>${escapeHtml(post.general_location)}</dd>
      </dl>
      <p class="description">${escapeHtml(post.description)}</p>
      ${photo}
      ${ownerActions}
      <p id="detail-status" class="status-message" role="status" aria-live="polite"></p>
    </article>`;
}

async function setupPostDetail() {
  const container = document.querySelector("#post-detail");
  if (!container) return;

  const postId = container.dataset.postId;
  try {
    const { data } = await apiRequest(`/api/posts/${postId}`);
    const post = data.post;
    container.innerHTML = detailMarkup(post);

    const status = container.querySelector("#detail-status");
    const resolveButton = container.querySelector("#resolve-post");
    const deleteButton = container.querySelector("#delete-post");

    resolveButton?.addEventListener("click", async () => {
      resolveButton.disabled = true;
      try {
        await apiRequest(`/api/posts/${postId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ resolved: true })
        });
        window.location.reload();
      } catch (error) {
        setStatus(status, error.message, true);
        resolveButton.disabled = false;
      }
    });

    deleteButton?.addEventListener("click", async () => {
      if (!window.confirm("Delete this post permanently?")) return;
      deleteButton.disabled = true;
      try {
        await apiRequest(`/api/posts/${postId}`, { method: "DELETE" });
        window.location.href = "/";
      } catch (error) {
        setStatus(status, error.message, true);
        deleteButton.disabled = false;
      }
    });
  } catch (error) {
    setStatus(container.querySelector(".status-message"), error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupSearch();
  setupPostForm();
  setupPostDetail();
});
