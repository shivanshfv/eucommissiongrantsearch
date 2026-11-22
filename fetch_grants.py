"""Fetch open and forthcoming EU grant calls and write them to docs/data/.

Run with:  python fetch_grants.py

It writes three files (JSON, CSV, XLSX). If anything goes wrong, it stops
with an error and leaves the existing files untouched.
"""

import csv
import json
import os
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook

API = "https://api.tech.ec.europa.eu/search-api/prod/rest"
PAGE_SIZE = 100
PAUSE_SECONDS = 2
TIMEOUT_SECONDS = 180
ATTEMPTS = 3

# Codes used by the EU Funding & Tenders Portal.
TYPES = {"1": "Grant topic", "2": "External action call", "8": "Cascade funding call"}
STATUSES = {"31094501": "Forthcoming", "31094502": "Open"}

QUERY = {
    "bool": {
        "must": [
            {"terms": {"type": list(TYPES)}},
            {"terms": {"status": list(STATUSES)}},
        ]
    }
}

DATA_DIR = Path(__file__).parent / "docs" / "data"
JSON_FILE = DATA_DIR / "grants.json"
CSV_FILE = DATA_DIR / "grants.csv"
XLSX_FILE = DATA_DIR / "grants.xlsx"


def user_agent():
    agent = "eu-grant-calls-daily-fetcher/1.0 (one run per day)"
    repo = os.environ.get("GITHUB_REPOSITORY")  # set automatically on GitHub
    if repo:
        agent += f" +https://github.com/{repo}"
    return agent


def post(path, params):
    """POST the search query to the API and return the parsed JSON reply."""
    boundary = "----" + uuid.uuid4().hex
    body = b""
    for name, value in (("query", QUERY), ("languages", ["en"])):
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="blob"\r\n'
            "Content-Type: application/json\r\n\r\n"
            f"{json.dumps(value)}\r\n"
        ).encode()
    body += f"--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        f"{API}/{path}?apiKey=SEDIA&text=***{params}",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": user_agent(),
        },
    )
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:
                return json.load(reply)
        except Exception as error:
            print(f"  attempt {attempt} failed: {error}")
            if attempt == ATTEMPTS:
                raise
            time.sleep(10 * attempt)


def fetch_all():
    """Download every page of results."""
    results = []
    page = 1
    while True:
        data = post("search", f"&pageSize={PAGE_SIZE}&pageNumber={page}")
        total = data["totalResults"]
        results += data["results"]
        print(f"page {page}: {len(results)} of {total}")
        if not data["results"] or len(results) >= total:
            break
        page += 1
        time.sleep(PAUSE_SECONDS)
    if not results:
        sys.exit("ERROR: the API returned zero results. Existing data left untouched.")
    if len(results) < total:
        sys.exit(f"ERROR: only got {len(results)} of {total} results. Existing data left untouched.")
    return results


def fetch_programme_names():
    """The API returns programmes as numbers; this gets the readable names."""
    time.sleep(PAUSE_SECONDS)
    data = post("facet", "")
    for facet in data["facets"]:
        if facet["name"] == "frameworkProgramme":
            return {v["rawValue"]: " ".join(v["value"].split()) for v in facet["values"]}
    sys.exit("ERROR: could not find programme names in the API reply.")


def first(metadata, field):
    values = metadata.get(field) or [""]
    return (values[0] or "").strip()


def find_budget(metadata, identifier):
    """Budget in euros, or None if the API does not give one."""
    budget = first(metadata, "budget")
    if not budget:
        # Grant topics keep budgets in a table covering every topic of the call.
        overview = first(metadata, "budgetOverview")
        if not overview:
            return None
        amounts = [
            float(amount)
            for actions in json.loads(overview).get("budgetTopicActionMap", {}).values()
            for action in actions
            if (action.get("action") or "").startswith(identifier + " ")
            for amount in (action.get("budgetYearMap") or {}).values()
            if amount
        ]
        if not amounts:
            return None
        budget = sum(amounts)
    try:
        return round(float(budget))
    except ValueError:
        return None


def build_calls(results, programme_names, today):
    """Turn raw API results into one clean record per call, keyed by link."""
    calls = {}
    for result in results:
        m = result["metadata"]
        url = result.get("url") or first(m, "url")
        kind = first(m, "type")
        if kind == "8" and first(m, "callccm2Id"):
            # The link the API gives for cascade calls opens an empty page.
            # The working link ends in the call's own number instead.
            url = url.rsplit("/", 1)[0] + "/" + first(m, "callccm2Id")
        deadlines = sorted({d[:10] for d in m.get("deadlineDate") or [] if d})

        # The API still lists many old calls as "open" years after they
        # closed. Skip anything whose last deadline has already passed.
        if deadlines and deadlines[-1] < today:
            continue

        if url in calls:  # same call listed twice: merge the deadlines
            calls[url]["deadlines"] = sorted(set(calls[url]["deadlines"]) | set(deadlines))
            continue

        identifier = first(m, "identifier")
        title = first(m, "title")
        if kind == "8":  # cascade calls: "title" is the parent topic's title
            title = first(m, "callTitle") or first(m, "caName") or title
        programme = first(m, "frameworkProgramme")
        status = first(m, "status")

        calls[url] = {
            "url": url,
            "identifier": identifier,
            "title": " ".join(title.split()),
            "type": TYPES.get(kind, kind),
            "programme": programme_names.get(programme, programme),
            "call": first(m, "callIdentifier"),
            "status": STATUSES.get(status, status),
            "opening_date": first(m, "startDate")[:10],
            "deadlines": deadlines,
            "deadline_model": first(m, "deadlineModel"),
            "budget": find_budget(m, identifier),
            "first_seen": "",
            "changed_on": "",
            "change": "",
        }

    for call in calls.values():
        upcoming = [d for d in call["deadlines"] if d >= today]
        call["next_deadline"] = upcoming[0] if upcoming else ""
    return calls


def track_changes(calls, previous, today):
    """Fill in first-seen dates and flag deadline or status changes."""
    if previous is None:
        return  # very first run: nothing to compare with, so nothing is "new"
    for url, call in calls.items():
        old = previous.get(url)
        if old is None:
            call["first_seen"] = today
            continue
        call["first_seen"] = old.get("first_seen", "")
        call["changed_on"] = old.get("changed_on", "")
        call["change"] = old.get("change", "")
        notes = []
        if old["deadlines"] != call["deadlines"]:
            before = ", ".join(old["deadlines"]) or "none"
            after = ", ".join(call["deadlines"]) or "none"
            notes.append(f"Deadline: {before} -> {after}")
        if old["status"] != call["status"]:
            notes.append(f"Status: {old['status']} -> {call['status']}")
        if notes:
            call["changed_on"] = today
            call["change"] = "; ".join(notes)


COLUMNS = [
    ("Identifier", "identifier"),
    ("Title", "title"),
    ("Type", "type"),
    ("Programme", "programme"),
    ("Parent call", "call"),
    ("Status", "status"),
    ("Opening date", "opening_date"),
    ("Next deadline", "next_deadline"),
    ("All deadlines", "deadlines"),
    ("Deadline model", "deadline_model"),
    ("Budget (EUR)", "budget"),
    ("First seen", "first_seen"),
    ("Changed on", "changed_on"),
    ("Change", "change"),
    ("Link", "url"),
]


def table_rows(calls):
    rows = [[title for title, _ in COLUMNS]]
    for call in calls:
        row = [call[key] for _, key in COLUMNS]
        rows.append([", ".join(v) if isinstance(v, list) else v for v in row])
    return rows


def write_files(calls, now):
    calls = sorted(calls.values(), key=lambda c: (c["next_deadline"] or "9999", c["identifier"]))
    rows = table_rows(calls)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    JSON_FILE.write_text(
        json.dumps({"generated_at": now, "calls": calls}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    # "utf-8-sig" makes Excel open accented characters correctly.
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Grants"
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    workbook.save(XLSX_FILE)


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    previous = None
    if JSON_FILE.exists():
        old_calls = json.loads(JSON_FILE.read_text(encoding="utf-8"))["calls"]
        previous = {c["url"]: c for c in old_calls}

    results = fetch_all()
    programme_names = fetch_programme_names()
    calls = build_calls(results, programme_names, today)
    if not calls:
        sys.exit("ERROR: no current calls after filtering. Existing data left untouched.")

    track_changes(calls, previous, today)
    write_files(calls, now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    new = sum(1 for c in calls.values() if c["first_seen"] == today)
    changed = sum(1 for c in calls.values() if c["changed_on"] == today)
    print(f"Done: {len(calls)} calls written ({new} new, {changed} changed today).")


if __name__ == "__main__":
    main()
