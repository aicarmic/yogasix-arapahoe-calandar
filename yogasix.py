import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta, timezone

LOCATION_SLUG = "yogasix-arapahoe"
LOCATION_STR = "6340 S Parker Rd, Unit 2, Aurora, CO 80016"
PUBLISHED_ICS_URL = "https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics"
STATE_FILE = "known_events.json"

CLASS_EMOJIS = {
    "Y6 Sculpt": "💪",
    "Y6 Power": "⚡",
    "Y6 Slow Flow": "🌊",
    "Y6 Restore": "🪔",
    "Y6 Hot": "🔥",
    "Y6 Core": "🎯",
    "Y6 Mobility": "🤸‍♂️",
    "Y6 101": "🧘‍♂️",
    "Workshop": "🛠️"
}

def get_class_emoji(title):
    for key, emoji in CLASS_EMOJIS.items():
        if key.lower() in title.lower():
            return emoji
    return "🤸‍♂️"

def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[STATE] Loaded {len(data)} events from persistent cache: {STATE_FILE}")
                return data
        except Exception as e:
            print(f"[STATE] Error reading {STATE_FILE}: {e}")
    print("[STATE] No persistent state found. Running in baseline mode.")
    return {}

def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    print(f"[STATE] Wrote {len(state)} events to {STATE_FILE}")

def detect_changes(prev_state, new_events):
    changes = []
    updated_state = {}
    new_event_map = {e["uid"]: e for e in new_events}
    now_str = datetime.now().strftime("%Y%m%dT%H%M%S")

    is_cold_start = len(prev_state) == 0

    for uid, new_ev in new_event_map.items():
        summary = f"{new_ev['emoji']} {new_ev['title']} - {new_ev['instructor']}"
        dtstart = new_ev["start_str"]

        if not is_cold_start and uid in prev_state:
            prev = prev_state[uid]
            prev_summary = prev.get("summary", "")
            last_alerted = prev.get("last_alerted_summary", prev_summary)

            if prev_summary != summary and last_alerted != summary:
                changes.append({
                    "uid": uid,
                    "type": "MODIFIED",
                    "time": new_ev["start_dt"].strftime("%a %m/%d @ %I:%M%p"),
                    "old": prev_summary,
                    "new": summary
                })
                last_alerted = summary
        else:
            last_alerted = summary

        updated_state[uid] = {
            "summary": summary,
            "dtstart": dtstart,
            "last_alerted_summary": last_alerted
        }

    # Check cancellations
    if not is_cold_start:
        for uid, prev in prev_state.items():
            if prev.get("dtstart", "") > now_str and uid not in new_event_map:
                if not prev.get("alerted_canceled", False):
                    try:
                        dt = datetime.strptime(prev["dtstart"], "%Y%m%dT%H%M%S")
                        time_display = dt.strftime("%a %m/%d @ %I:%M%p")
                    except Exception:
                        time_display = prev.get("dtstart", "")

                    changes.append({
                        "uid": uid,
                        "type": "CANCELED",
                        "time": time_display,
                        "old": prev.get("summary", ""),
                        "new": "Class Removed / Canceled"
                    })
                    prev["alerted_canceled"] = True

    return changes, updated_state

def export_changes_markdown(changes, output_path="changes.md"):
    if not changes:
        return

    lines = [
        "### 🚨 Schedule Modifications Detected\n",
        "The following existing classes were updated or canceled:\n"
    ]
    for c in changes:
        if c["type"] == "MODIFIED":
            lines.append(f"- **MODIFIED:** `{c['time']}` (UID: `{c['uid']}`)")
            lines.append(f"  - **Previous:** {c['old']}")
            lines.append(f"  - **Updated:**  {c['new']}\n")
        elif c["type"] == "CANCELED":
            lines.append(f"- **CANCELED:** `{c['time']}` (UID: `{c['uid']}`)")
            lines.append(f"  - **Was:** {c['old']}\n")

    lines.append(f"\n[View Live Calendar Feed]({PUBLISHED_ICS_URL})")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote change details to {output_path}")

def fetch_schedule_api():
    today = datetime.now()
    
    # Define overlapping windows:
    # Window 1: Past history (-28 days to today)
    # Window 2: Current & Future (today to +21 days)
    windows = [
        (today - timedelta(days=28), today + timedelta(days=1)),
        (today, today + timedelta(days=21))
    ]

    unique_events = {}
    errors = []

    for start_dt, end_dt in windows:
        s_str = start_dt.strftime("%Y-%m-%d")
        e_str = end_dt.strftime("%Y-%m-%d")
        url = f"https://members.yogasix.com/api/v2/locations/{LOCATION_SLUG}/schedule_entries?start_date={s_str}&end_date={e_str}"
        print(f"Fetching window: {s_str} to {e_str}")

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        })

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
                entries = data.get("schedule_entries", [])
                print(f" -> Received {len(entries)} entries from API")
                
                for entry in entries:
                    entry_id = entry.get("id")
                    if not entry_id or entry_id in unique_events:
                        continue

                    title = entry.get("title", "").strip()
                    inst_dict = entry.get("instructor") or {}
                    instructor = inst_dict.get("name", "").strip()
                    start_raw = entry.get("starts_at")
                    end_raw = entry.get("ends_at")
                    description_raw = entry.get("description") or ""

                    if not title or not instructor or not start_raw or not end_raw:
                        continue

                    if instructor.lower() == "staff":
                        continue

                    clean_desc = description_raw.strip().replace("\r\n", "\\n").replace("\n", "\\n")
                    desc_field = f"Instructor: {instructor}\\nStudio: YogaSix Arapahoe"
                    if clean_desc:
                        desc_field += f"\\n\\n{clean_desc}"

                    emoji = get_class_emoji(title)
                    s_parsed = datetime.fromisoformat(start_raw)
                    e_parsed = datetime.fromisoformat(end_raw)

                    unique_events[entry_id] = {
                        "uid": entry_id,
                        "title": title,
                        "emoji": emoji,
                        "instructor": instructor,
                        "start_dt": s_parsed,
                        "start_str": s_parsed.strftime("%Y%m%dT%H%M%S"),
                        "end_str": e_parsed.strftime("%Y%m%dT%H%M%S"),
                        "desc": desc_field
                    }
        except Exception as e:
            err_msg = f"Failed window {s_str} -> {e_str}: {str(e)}"
            print(f"Error: {err_msg}")
            errors.append(err_msg)

    events = sorted(unique_events.values(), key=lambda x: x["start_dt"])
    return events, errors

def build_ics(events, output_path="public/schedule.ics"):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//YogaSix Arapahoe Native Sync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:YogaSix Arapahoe Schedule",
        "X-WR-TIMEZONE:America/Denver",
        "BEGIN:VTIMEZONE",
        "TZID:America/Denver",
        "X-LIC-LOCATION:America/Denver",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:-0700",
        "TZOFFSETTO:-0600",
        "TZNAME:MDT",
        "DTSTART:19700308T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:-0600",
        "TZOFFSETTO:-0700",
        "TZNAME:MST",
        "DTSTART:19701101T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "END:STANDARD",
        "END:VTIMEZONE"
    ]

    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for ev in events:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}@yogasix.local",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID=America/Denver:{ev['start_str']}",
            f"DTEND;TZID=America/Denver:{ev['end_str']}",
            f"SUMMARY:{ev['emoji']} {ev['title']} - {ev['instructor']}",
            f"DESCRIPTION:{ev['desc']}",
            f"LOCATION:{LOCATION_STR}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

def write_sync_log(events, errors, changes, log_path="public/sync_status.json"):
    now = datetime.now(timezone.utc)
    now_local = datetime.now()
    past_count = sum(1 for e in events if e["start_dt"].replace(tzinfo=None) < now_local)
    
    log_data = {
        "last_sync_utc": now.isoformat(),
        "status": "success" if not errors else "partial_failure",
        "total_classes": len(events),
        "historical_classes_retained": past_count,
        "upcoming_classes_published": len(events) - past_count,
        "changes_detected": len(changes),
        "recent_changes": changes,
        "errors": errors
    }
    
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

if __name__ == "__main__":
    os.makedirs("public", exist_ok=True)

    if os.path.exists("changes.md"):
        os.remove("changes.md")

    prev_state = load_previous_state()
    events, errors = fetch_schedule_api()

    if not events and errors:
        write_sync_log(events, errors, [])
        print("CRITICAL: Failed to retrieve schedule entries.")
        sys.exit(1)

    changes, new_state = detect_changes(prev_state, events)
    if changes:
        print(f"\n[CHANGE DETECTION] Found {len(changes)} new modification(s):")
        for c in changes:
            print(f" -> {c['type']}: {c['time']} | {c['old']} => {c['new']}")
        export_changes_markdown(changes)
    else:
        print("\n[CHANGE DETECTION] No new modifications detected.")

    save_current_state(new_state)
    build_ics(events, output_path="public/schedule.ics")
    write_sync_log(events, errors, changes)

    # Print verification breakdown
    now_local = datetime.now()
    upcoming = [e for e in events if e["start_dt"].replace(tzinfo=None) >= now_local]
    print(f"\nTotal verified events: {len(events)} ({len(upcoming)} upcoming)")
    print("Generated public/schedule.ics successfully.")
