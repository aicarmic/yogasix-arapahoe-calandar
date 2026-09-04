import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta, timezone

LOCATION_SLUG = "yogasix-arapahoe"
LOCATION_STR = "6340 S Parker Rd, Unit 2, Aurora, CO 80016"
PUBLISHED_ICS_URL = "https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics"

# Updated Class Type Emojis
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

def parse_existing_ics(ics_url):
    """Downloads and parses the current live feed to build a baseline state."""
    req = urllib.request.Request(ics_url, headers={"User-Agent": "Mozilla/5.0"})
    existing = {}
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Notice: Could not fetch previous ICS ({e}). Skipping baseline diff.")
        return existing

    events = content.split("BEGIN:VEVENT")
    for ev in events[1:]:
        uid_match = None
        summary_match = None
        dtstart_match = None

        for line in ev.splitlines():
            line = line.strip()
            if line.startswith("UID:"):
                uid_match = line.replace("UID:", "").replace("@yogasix.local", "").strip()
            elif line.startswith("SUMMARY:"):
                summary_match = line.replace("SUMMARY:", "").strip()
            elif "DTSTART" in line:
                dtstart_match = line.split(":")[-1].strip()

        if uid_match and summary_match and dtstart_match:
            existing[uid_match] = {
                "summary": summary_match,
                "dtstart": dtstart_match
            }
    print(f"Loaded {len(existing)} existing events from published ICS for change tracking.")
    return existing

def detect_changes(existing_events, new_events):
    """Identifies modified instructors/titles or cancellations on existing events."""
    changes = []
    new_event_map = {e["uid"]: e for e in new_events}
    now_str = datetime.now().strftime("%Y%m%dT%H%M%S")

    # 1. Detect modifications to existing events
    for uid, new_ev in new_event_map.items():
        if uid in existing_events:
            prev = existing_events[uid]
            new_summary = f"{new_ev['emoji']} {new_ev['title']} - {new_ev['instructor']}"
            
            if prev["summary"] != new_summary:
                changes.append({
                    "type": "MODIFIED",
                    "time": new_ev["start_dt"].strftime("%a %m/%d @ %I:%M%p"),
                    "old": prev["summary"],
                    "new": new_summary
                })

    # 2. Detect cancellations (future events missing from fresh API pull)
    for uid, prev in existing_events.items():
        if prev["dtstart"] > now_str and uid not in new_event_map:
            try:
                dt = datetime.strptime(prev["dtstart"], "%Y%m%dT%H%M%S")
                time_display = dt.strftime("%a %m/%d @ %I:%M%p")
            except Exception:
                time_display = prev["dtstart"]

            changes.append({
                "type": "CANCELED",
                "time": time_display,
                "old": prev["summary"],
                "new": "Class Removed / Canceled"
            })

    return changes

def export_changes_markdown(changes, output_path="changes.md"):
    if not changes:
        return

    lines = [
        "### 🚨 Schedule Modifications Detected\n",
        "The following existing classes were updated or canceled:\n"
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
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote change details to {output_path}")

def fetch_schedule_api():
    today = datetime.now()
    # 42-day window: 4 weeks historical (-28 days) to 2 weeks future (+14 days)
    start_anchor = today - timedelta(days=28)
    end_anchor = today + timedelta(days=14)

    unique_events = {}
    current_start = start_anchor
    errors = []

    while current_start < end_anchor:
        current_end = min(current_start + timedelta(days=7), end_anchor)
        s_str = current_start.strftime("%Y-%m-%d")
        e_str = current_end.strftime("%Y-%m-%d")
        
        url = f"https://members.yogasix.com/api/v2/locations/{LOCATION_SLUG}/schedule_entries?start_date={s_str}&end_date={e_str}"
        print(f"Fetching chunk: {s_str} to {e_str}")

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        })

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                entries = data.get("schedule_entries", [])
                
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
                    s_dt = datetime.fromisoformat(start_raw)
                    e_dt = datetime.fromisoformat(end_raw)

                    unique_events[entry_id] = {
                        "uid": entry_id,
                        "title": title,
                        "emoji": emoji,
                        "instructor": instructor,
                        "start_dt": s_dt,
                        "start_str": s_dt.strftime("%Y%m%dT%H%M%S"),
                        "end_str": e_dt.strftime("%Y%m%dT%H%M%S"),
                        "desc": desc_field
                    }
        except Exception as e:
            err_msg = f"Failed chunk {s_str} -> {e_str}: {str(e)}"
            print(f"Error: {err_msg}")
            errors.append(err_msg)

        current_start = current_end

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
    print(f"Wrote status summary to {log_path}")

if __name__ == "__main__":
    os.makedirs("public", exist_ok=True)

    # 1. Clean previous run's change artifact
    if os.path.exists("changes.md"):
        os.remove("changes.md")

    # 2. Ingest baseline from published feed
    existing_events = parse_existing_ics(PUBLISHED_ICS_URL)

    # 3. Pull fresh schedule data
    events, errors = fetch_schedule_api()

    # 4. Critical failure exit
    if not events and errors:
        write_sync_log(events, errors, [])
        print("CRITICAL: Failed to retrieve schedule entries.")
        sys.exit(1)

    # 5. Detect and log modifications/cancellations
    changes = detect_changes(existing_events, events)
    if changes:
        print(f"\n[CHANGE DETECTION] Found {len(changes)} event modification(s):")
        for c in changes:
            print(f" -> {c['type']}: {c['time']} | {c['old']} => {c['new']}")
        export_changes_markdown(changes)
    else:
        print("\n[CHANGE DETECTION] No modifications to existing classes detected.")

    print("\n" + "=" * 80)
    print(f"{'DATE / TIME':<22} | {'INSTRUCTOR':<18} | {'CLASS TYPE'}")
    print("=" * 80)
    for ev in events:
        dt_str = ev['start_dt'].strftime('%a %m/%d %I:%M%p')
        print(f"{dt_str:<22} | {ev['instructor']:<18} | {ev['emoji']} {ev['title']}")
    print("=" * 80)
    print(f"Total verified events: {len(events)}\n")

    build_ics(events, output_path="public/schedule.ics")
    write_sync_log(events, errors, changes)
    print("Generated public/schedule.ics successfully.")
