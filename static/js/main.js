/* ==========================================================
   SokoSense - frontend logic
   Each feature only runs if its element exists on the current page.
   ========================================================== */

const $ = (sel) => document.querySelector(sel);

// Escape text before inserting it into HTML
const esc = (s = "") =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json();
}

const loadError = (what) =>
  `<li class="state-msg">Could not load ${what}. Check that the Flask server is running, then refresh the page.</li>`;

/* ---------- Mobile menu ---------- */
function setupNav() {
  const toggle = $(".nav-toggle");
  const menu = $("#nav-menu");
  if (!toggle || !menu) return;
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!open));
    menu.classList.toggle("open", !open);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && menu.classList.contains("open")) {
      toggle.setAttribute("aria-expanded", "false");
      menu.classList.remove("open");
      toggle.focus();
    }
  });
}

/* ---------- Home: WhatsApp chat plays message by message ---------- */
function playHeroChat() {
  const chat = $("#hero-chat");
  if (!chat) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const bubbles = [...chat.querySelectorAll(".bubble")];
  chat.classList.add("animate");
  bubbles.forEach((b, i) => setTimeout(() => b.classList.add("shown"), 500 + i * 1100));
}

/* ---------- Awards page ---------- */
async function loadAwards() {
  const list = $("#awards-list");
  if (!list) return;
  try {
    const awards = await getJSON("/api/awards");
    list.innerHTML = awards.length
      ? awards.map((a) => `
        <li class="award">
          <span class="award-year">${esc(a.year)}</span>
          <div>
            <h2 class="award-title">${esc(a.title)}</h2>
            <p class="award-org">${esc(a.organizer)}</p>
            <p>${esc(a.description)}</p>
          </div>
        </li>`).join("")
      : `<li class="state-msg">No awards added yet.</li>`;
  } catch (e) {
    console.error(e);
    list.innerHTML = loadError("awards");
  }
}

/* ---------- Events page ---------- */
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function eventWhen(ev) {
  // If a full date (YYYY-MM-DD) is given, show it; otherwise show the year only
  if (ev.date) {
    const [y, m, d] = ev.date.split("-").map(Number);
    return `${d} ${MONTHS[m - 1]} ${y}`;
  }
  return String(ev.year);
}

function renderEvents(events) {
  const list = $("#events-list");
  if (!events.length) {
    list.innerHTML = `<li class="state-msg">No events for this year.</li>`;
    return;
  }
  list.innerHTML = events.map((ev) => `
    <li class="event">
      ${ev.image
        ? `<img class="event-img" src="${esc(ev.image)}" alt="${esc(ev.title)}" loading="lazy">`
        : `<div class="event-img event-img-empty" aria-hidden="true">${esc(ev.year)}</div>`}
      <div>
        <span class="event-year">${esc(eventWhen(ev))}</span>
        <h2>${esc(ev.title)}</h2>
        <p class="event-meta">${esc(ev.location)}<span class="event-role">${esc(ev.role)}</span></p>
        <p>${esc(ev.description)}</p>
      </div>
    </li>`).join("");
}

async function loadEvents() {
  const list = $("#events-list");
  const filters = $("#event-filters");
  if (!list) return;
  try {
    const events = await getJSON("/api/events");
    const years = [...new Set(events.map((e) => String(e.year)))].sort().reverse();

    filters.innerHTML = ["All", ...years]
      .map((y, i) => `<button class="filter-btn" data-year="${y}" aria-pressed="${i === 0}">${y === "All" ? "All years" : y}</button>`)
      .join("");

    filters.addEventListener("click", async (e) => {
      const btn = e.target.closest(".filter-btn");
      if (!btn) return;
      filters.querySelectorAll(".filter-btn").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      const y = btn.dataset.year;
      try {
        renderEvents(await getJSON(y === "All" ? "/api/events" : `/api/events?year=${y}`));
      } catch (err) {
        list.innerHTML = loadError("events");
      }
    });

    renderEvents(events);
  } catch (e) {
    console.error(e);
    list.innerHTML = loadError("events");
  }
}

/* ---------- Team page ---------- */
const initials = (name) => name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");

// Photo if the file exists, otherwise the person's initials
function photoHTML(m, i) {
  return m.photo
    ? `<img class="member-photo" data-i="${i}" src="${esc(m.photo)}" alt="Photo of ${esc(m.name)}">`
    : `<span class="member-photo" aria-hidden="true">${esc(initials(m.name))}</span>`;
}

// If a photo has not been added yet (or the link is broken), show initials instead
function fallbackToInitials(container, team) {
  container.querySelectorAll("img.member-photo").forEach((img) =>
    img.addEventListener("error", () => {
      const span = document.createElement("span");
      span.className = "member-photo";
      span.setAttribute("aria-hidden", "true");
      span.textContent = initials(team[img.dataset.i].name);
      img.replaceWith(span);
    })
  );
}

async function loadTeam() {
  const list = $("#team-list");
  if (!list) return;
  try {
    const team = await getJSON("/api/team");
    list.innerHTML = team.map((m, i) => `
      <li class="member" tabindex="0">
        ${photoHTML(m, i)}
        <span class="member-name">${esc(m.name)}</span>
        <span class="member-role">${esc(m.role)}</span>
        ${m.bio || m.linkedin ? `
        <div class="member-card">
          <p class="member-card-name">${esc(m.name)}</p>
          ${m.bio ? `<p class="member-bio">${esc(m.bio)}</p>` : ""}
          ${m.linkedin ? `<a class="member-link" href="${esc(m.linkedin)}" target="_blank" rel="noopener">View LinkedIn</a>` : ""}
        </div>` : ""}
      </li>`).join("");
    fallbackToInitials(list, team);
  } catch (e) {
    console.error(e);
    list.innerHTML = loadError("the team");
  }
}

/* ---------- Contact page ---------- */
function setupContactForm() {
  const form = $("#contact-form");
  if (!form) return;
  const status = $("#form-status");
  const submit = form.querySelector('button[type="submit"]');

  const setFieldError = (name, msg) => {
    const p = form.querySelector(`.field-error[data-for="${name}"]`);
    if (!p) return;
    p.textContent = msg || "";
    p.closest(".field").classList.toggle("has-error", Boolean(msg));
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    ["name", "email", "message"].forEach((f) => setFieldError(f, ""));
    status.textContent = "";
    status.className = "form-status";
    submit.disabled = true;
    submit.textContent = "Sending…";

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      const result = await res.json();
      if (result.ok) {
        form.reset();
        status.textContent = result.message;
        status.classList.add("ok");
      } else {
        Object.entries(result.errors || {}).forEach(([f, msg]) => setFieldError(f, msg));
        status.textContent = "Fix the highlighted fields, then send again.";
        status.classList.add("err");
      }
    } catch (err) {
      status.textContent = "Message not sent. Check your internet connection and try again.";
      status.classList.add("err");
    } finally {
      submit.disabled = false;
      submit.textContent = "Send message";
    }
  });
}

/* ---------- Start ---------- */
document.addEventListener("DOMContentLoaded", () => {
  setupNav();
  playHeroChat();
  loadAwards();
  loadEvents();
  loadTeam();
  setupContactForm();
});
