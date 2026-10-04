import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

BASELINE_FILE = "baseline_schedule.json"
CURRENT_ICS = "public/schedule.ics"
CHANGES_FILE = "changes.md"
PUBLISHED_ICS_URL = "https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics"
DENVER_TZ = ZoneInfo("America/Denver")

def parse_ics(file_path):
    if not os.path.exists(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    events = {}
    for block in content.split("BEGIN:VEVENT")[1:]:
        uid = None
        summary = None
        dtstart = None

        for line in block.splitlines():
            line = line.strip()
            if line.startswith("UID:"):
                uid = line.split(":", 1)[1].strip()
            elif line.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif "DTSTART" in line:
                dtstart = line.split(":")[-1].strip()

        if uid and summary and dtstart:
            events[uid] = {
                "summary": summary,
                "dtstart": dtstart
            }
    return events

def run():
    if os.path.exists(CHANGES_FILE):
        os.remove(CHANGES_FILE)

    current_events = parse_ics(CURRENT_ICS)
    if not current_events:
        print("[CHANGE_CHECK] Target calendar missing or empty. Skipping.")
        return

    baseline_state = {}
    if os.path.exists(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, "r", encoding="utf-8") as f:
                baseline_state = json.load(f)
        except Exception as e:
            print(f"[CHANGE_CHECK] Warning: Error reading baseline: {e}")

    now_denver_str = datetime.now(DENVER_TZ).strftime("%Y%m%dT%H%M%S")
    is_initial_seed = len(baseline_state) == 0

    changes = []
    updated_state = {}

    # Check for modifications & record current events
    for uid, curr in current_events.items():
        summary = curr["summary"]
        dtstart = curr["dtstart"]

        if not is_initial_seed and uid in baseline_state:
            prev = baseline_state[uid]
            prev_summary = prev.get("summary", "")
            last_alerted = prev.get("last_alerted", prev_summary)

            # Only flag if summary changed AND it wasn't already alerted
            # and the class is occurring in the future
            if dtstart >= now_denver_str and prev_summary != summary and last_alerted != summary:
                try:
                    dt = datetime.strptime(dtstart, "%Y%m%dT%H%M%S")
                    time_display = dt.strftime("%a %m/%d @ %I:%M%p")
                except Exception:
                    time_display = dtstart

                changes.append({
                    "type": "MODIFIED",
                    "time": time_display,
                    "uid": uid,
                    "old": prev_summary,
                    "new": summary
                })
                last_alerted = summary
        else:
            last_alerted = summary

        updated_state[uid] = {
            "summary": summary,
            "dtstart": dtstart,
            "last_alerted": last_alerted
        }

    # Check for cancellations (future classes in baseline that disappeared)
    if not is_initial_seed:
        for uid, prev in baseline_state.items():
            dtstart = prev.get("dtstart", "")
            if dtstart >= now_denver_str and uid not in current_events:
                if not prev.get("alerted_canceled", False):
                    try:
                        dt = datetime.strptime(dtstart, "%Y%m%dT%H%M%S")
                        time_display = dt.strftime("%a %m/%d @ %I:%M%p")
                    except Exception:
                        time_display = dtstart

                    changes.append({
                        "type": "CANCELED",
                        "time": time_display,
                        "uid": uid,
                        "old": prev.get("summary", ""),
                        "new": "Class Removed / Canceled"
                    })
                    prev["alerted_canceled"] = True

    # Output alert file if changes exist
    if changes:
        print(f"[CHANGE_CHECK] Found {len(changes)} schedule change(s). Writing {CHANGES_FILE}.")
        lines = [
            "### 🚨 Schedule Modifications Detected\n",
            "The following classes have an updated instructor or format:\n"
        ]
        for c in changes:
            if c["type"] == "MODIFIED":
                lines.append(f"- **MODIFIED:** `{c['time']}`")
                lines.append(f"  - **Previous:** {c['old']}")
                lines.append(f"  - **Updated:**  {c['new']}\n")
            elif c["type"] == "CANCELED":
                lines.append(f"- **CANCELED:** `{c['time']}`")
                lines.append(f"  - **Was:** {c['old']}\n")

        lines.append(f"\n[View Live Calendar Feed]({PUBLISHED_ICS_URL})")
        with open(CHANGES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    else:
        print("[CHANGE_CHECK] No unalerted schedule changes detected.")

    # Save updated baseline for the next run
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_state, f, indent=2, sort_keys=True)
    print(f"[CHANGE_CHECK] Synchronized {len(updated_state)} classes to {BASELINE_FILE}.")

if __name__ == "__main__":
    run()
