# EU grant opportunities – daily list

This repository publishes a web page listing every open and forthcoming EU grant
call. It refreshes itself once a day. Nobody needs to run anything by hand.

## What it does

Once a day, GitHub automatically:

1. Downloads the current grant calls from the public
   [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home).
2. Saves them in this repository (in the `docs/data` folder).
3. Publishes a web page where anyone can search, filter and sort the calls.

The page also offers the full list as a CSV file and an Excel file. Their
addresses never change, so you can link to them:

- `YOUR-PAGE-ADDRESS/data/grants.csv`
- `YOUR-PAGE-ADDRESS/data/grants.xlsx`

It is free to run, needs no passwords or keys, and uses no paid services.

### What is on the page

- **Three kinds of call:** grant topics, cascade funding calls (smaller grants
  handed out by existing EU projects), and EU external action calls.
- **"New today" and "New this week" labels** on calls that have just appeared.
- **A "Changed" label** when a call's deadline or status changed in the last
  seven days, with the old and new values.
- **Bookmarkable filters.** Whatever you search or filter for is stored in the
  page address. Copy the address from your browser to share or bookmark that view.

### Good to know

- The EU's data still lists hundreds of old calls as "open" years after they
  closed. This tool leaves out any call whose last deadline has passed.
- Budgets are shown when the EU publishes them. Many calls have none listed.
- Always check the EU portal itself before relying on a date or amount.

## Setting it up

Do this once after creating the repository from a template, or after the
repository has been transferred to a new owner. It takes about five minutes.
The repository must be **public** (free page hosting requires that).

### 1. Turn on Actions

1. Open the repository on GitHub and click the **Actions** tab.
2. If you see a green button saying **"I understand my workflows, go ahead and
   enable them"**, click it.
3. In the list on the left, click **Update grant data**. If a banner says the
   workflow is disabled, click **Enable workflow**.

### 2. Turn on Pages

1. Click the **Settings** tab, then **Pages** in the left-hand menu.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

That is all. There is nothing to save.

### 3. Run it once

Follow "Running it by hand" below. The first run takes 5–10 minutes.

### 4. Find the page address

Go to **Settings → Pages**. The address is shown at the top ("Your site is live
at…"). It normally looks like `https://OWNER.github.io/REPOSITORY/`.

The address changes if the repository is renamed or moved to another owner, so
look it up again after a transfer and update any bookmarks or links.

## Running it by hand

1. Click the **Actions** tab.
2. Click **Update grant data** in the list on the left.
3. Click the **Run workflow** button on the right, then the green
   **Run workflow** button.
4. After a few seconds a new run appears in the list. A yellow dot means it is
   running, a green tick means it worked, a red cross means it failed.

## If the warning banner appears

The page shows a yellow warning when its data is more than 48 hours old. That
means the daily update has stopped working. Your existing data is safe: a failed
update never replaces good data with an empty list.

1. Click the **Actions** tab and look at the most recent runs.
2. **If the latest runs have a red cross:** the download from the EU failed.
   This is usually a temporary problem on the EU's side. Run it by hand (see
   above). If it still fails the next day, click the failed run, open the
   **Fetch grant calls** step, and pass the error message shown there to someone
   technical.
3. **If there are no recent runs at all:** GitHub has switched the schedule off.
   Click **Update grant data** on the left, then **Enable workflow**, then run
   it by hand once.

### Why GitHub might switch the schedule off

GitHub's rule is: *"In a public repository, scheduled workflows are
automatically disabled when no repository activity has occurred in 60 days."*
This tool saves new data to the repository every day, which is intended to count
as activity and keep the schedule alive. GitHub does not spell out exactly what
counts as "activity", so if the schedule is ever switched off anyway, re-enable
it as described in step 3 above.

GitHub also switches schedules off in **forks**. Create copies with **Use this
template** rather than **Fork** where you can, and follow "Turn on Actions"
either way.

## For technical maintainers

| File | Purpose |
|---|---|
| `fetch_grants.py` | Downloads the calls and writes the data files. Needs Python 3 and `openpyxl`. |
| `.github/workflows/update.yml` | The daily schedule, the manual run button, and publishing. |
| `docs/index.html`, `style.css`, `app.js` | The page. Plain HTML, CSS and JavaScript, no build step. |
| `docs/data/grants.json` | The data the page reads, plus first-seen and change tracking. |
| `docs/data/grants.csv`, `grants.xlsx` | The downloads. |

To run locally: `pip install -r requirements.txt`, then `python fetch_grants.py`.
To preview the page: `python -m http.server --directory docs` and open
`http://localhost:8000`.

To change the time of the daily run, edit the `cron` line in
`.github/workflows/update.yml` (times are in UTC). Changes to the page go live
on the next run.

The data comes from the portal's public search API
(`https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA`). The
`SEDIA` value is a public identifier used by the portal's own website, not a
secret.
