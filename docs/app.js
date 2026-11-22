// Loads data/grants.json, then filters, sorts and draws the table.
// Every filter is kept in the page address so a view can be bookmarked.

const form = document.getElementById("filters");
const rowsEl = document.getElementById("rows");
const countEl = document.getElementById("count");
const DAY = 24 * 60 * 60 * 1000;

let calls = [];
let dataDate = ""; // the day the data was fetched, e.g. "2026-01-31"
let weekAgo = "";

fetch("data/grants.json", { cache: "no-store" })
  .then((reply) => {
    if (!reply.ok) throw new Error("HTTP " + reply.status);
    return reply.json();
  })
  .then(start)
  .catch((error) => {
    document.getElementById("updated").textContent = "";
    showWarning("The grant data could not be loaded (" + error.message + "). Please try again later.");
  });

function start(data) {
  calls = data.calls;
  const generated = new Date(data.generated_at);
  dataDate = data.generated_at.slice(0, 10);
  weekAgo = new Date(generated - 7 * DAY).toISOString().slice(0, 10);

  document.getElementById("updated").textContent =
    "Last updated: " + generated.toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" }) + ".";

  const hoursOld = (Date.now() - generated) / (60 * 60 * 1000);
  if (hoursOld > 48) {
    showWarning(
      "Warning: this data is " + Math.floor(hoursOld / 24) + " days old. The daily update has not been " +
      "running, so new calls and deadline changes may be missing."
    );
  }

  fillSelect("programme");
  fillSelect("type");
  fillSelect("status");
  readAddress();
  draw();

  form.addEventListener("input", update);
  form.addEventListener("reset", () => setTimeout(update));
  window.addEventListener("popstate", () => { readAddress(); draw(); });
  document.querySelectorAll("th button").forEach((button) => {
    button.addEventListener("click", () => {
      const same = form.sort.value === button.dataset.sort;
      form.dir.value = same && form.dir.value === "asc" ? "desc" : "asc";
      form.sort.value = button.dataset.sort;
      update();
    });
  });
}

function showWarning(text) {
  const box = document.getElementById("warning");
  box.textContent = text;
  box.hidden = false;
}

function fillSelect(name) {
  const values = [...new Set(calls.map((c) => c[name]).filter(Boolean))].sort();
  for (const value of values) form[name].add(new Option(value, value));
}

// ---- Filters <-> page address -------------------------------------------

function fields() {
  return [...form.elements].filter((el) => el.name);
}

function isDefault(el) {
  return el.tagName === "SELECT" ? el.selectedIndex === 0 : el.value === "";
}

function readAddress() {
  const params = new URLSearchParams(location.search);
  for (const el of fields()) {
    if (el.tagName === "SELECT") el.selectedIndex = 0;
    else el.value = "";
    if (params.has(el.name)) el.value = params.get(el.name);
    if (el.tagName === "SELECT" && el.selectedIndex < 0) el.selectedIndex = 0;
  }
}

function update() {
  const params = new URLSearchParams();
  for (const el of fields()) {
    if (!isDefault(el)) params.set(el.name, el.value);
  }
  const query = params.toString();
  history.replaceState(null, "", query ? "?" + query : location.pathname);
  draw();
}

// ---- Filtering and sorting ------------------------------------------------

function isNewToday(c) { return c.first_seen !== "" && c.first_seen === dataDate; }
function isNewThisWeek(c) { return c.first_seen !== "" && c.first_seen > weekAgo; }
function isChanged(c) { return c.changed_on !== "" && c.changed_on > weekAgo; }

function matches(c) {
  const f = form;
  const words = f.q.value.toLowerCase().split(/\s+/).filter(Boolean);
  const text = [c.title, c.identifier, c.call, c.programme, c.type].join(" ").toLowerCase();
  if (!words.every((word) => text.includes(word))) return false;

  if (f.programme.value && c.programme !== f.programme.value) return false;
  if (f.type.value && c.type !== f.type.value) return false;
  if (f.status.value && c.status !== f.status.value) return false;

  if (f.new.value === "today" && !isNewToday(c)) return false;
  if (f.new.value === "week" && !isNewThisWeek(c)) return false;
  if (f.new.value === "changed" && !isChanged(c)) return false;

  if (f.from.value || f.to.value) {
    if (!c.next_deadline) return false;
    if (f.from.value && c.next_deadline < f.from.value) return false;
    if (f.to.value && c.next_deadline > f.to.value) return false;
  }
  if (f.min.value || f.max.value) {
    if (c.budget === null) return false;
    if (f.min.value && c.budget < Number(f.min.value)) return false;
    if (f.max.value && c.budget > Number(f.max.value)) return false;
  }
  return true;
}

const SORT_KEYS = {
  deadline: (c) => c.next_deadline,
  title: (c) => c.title.toLowerCase(),
  programme: (c) => c.programme.toLowerCase(),
  type: (c) => c.type,
  status: (c) => c.status,
  opening: (c) => c.opening_date,
  budget: (c) => c.budget,
  first_seen: (c) => c.first_seen,
};

function sorted(list) {
  const key = SORT_KEYS[form.sort.value] || SORT_KEYS.deadline;
  const flip = form.dir.value === "desc" ? -1 : 1;
  return list.sort((a, b) => {
    const x = key(a);
    const y = key(b);
    const xEmpty = x === "" || x === null;
    const yEmpty = y === "" || y === null;
    if (xEmpty || yEmpty) return xEmpty - yEmpty; // blanks always go last
    if (x < y) return -flip;
    if (x > y) return flip;
    return 0;
  });
}

// ---- Drawing ---------------------------------------------------------------

function make(tag, text, className) {
  const el = document.createElement(tag);
  if (text) el.textContent = text;
  if (className) el.className = className;
  return el;
}

function cell(label, text, className) {
  const td = make("td", text, className);
  td.dataset.label = label;
  return td;
}

function draw() {
  const list = sorted(calls.filter(matches));
  countEl.textContent = "Showing " + list.length + " of " + calls.length + " calls";

  const fragment = document.createDocumentFragment();
  for (const c of list) {
    const tr = document.createElement("tr");

    const main = document.createElement("td");
    if (isNewToday(c)) main.append(make("span", "New today", "badge new"));
    else if (isNewThisWeek(c)) main.append(make("span", "New this week", "badge new"));
    if (isChanged(c)) main.append(make("span", "Changed", "badge changed"));
    const link = make("a", c.title || c.identifier);
    link.href = c.url;
    link.target = "_blank";
    link.rel = "noopener";
    main.append(link, make("span", c.identifier, "small"));
    if (isChanged(c)) main.append(make("span", c.change + " (" + c.changed_on + ")", "small"));
    tr.append(main);

    tr.append(cell("Programme", c.programme));
    tr.append(cell("Type", c.type));
    tr.append(cell("Status", c.status));
    tr.append(cell("Opens", c.opening_date, "nowrap"));

    const deadline = cell("Deadline", c.next_deadline, "nowrap");
    if (c.deadlines.length > 1) {
      deadline.append(make("span", "All: " + c.deadlines.join(", "), "small"));
    }
    tr.append(deadline);

    tr.append(cell("Budget (€)", c.budget === null ? "" : c.budget.toLocaleString("en"), "number"));
    fragment.append(tr);
  }
  rowsEl.replaceChildren(fragment);
}
