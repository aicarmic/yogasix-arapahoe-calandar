import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

LOCATION_SLUG = "yogasix-arapahoe"
LOCATION_STR = "6340 S Parker Rd, Unit 2, Aurora, CO 80016"

# Dynamic emoji mapping based on class nomenclature
CLASS_EMOJIS = {
    "Y6 Sculpt": "💪",
    "Y6 Power": "⚡",       # Captures both "Y6 Power" and "Y6 Power Flow"
    "Y6 Slow Flow": "🌊",
    "Y6 Restore": "🕯️",
    "Y6 Hot": "🔥",
    "Y6 Core": "🎯",
    "Y6 101": "🔰",
    "Workshop": "🛠️"
}

def get_class_emoji(title):
    for key, emoji in CLASS_EMOJIS.items():
        if key.lower() in title.lower():
            return emoji
    return "🤸‍♂️" # Default fallback for unrecognized formats

def fetch_schedule_api():
    # Expand window: -30 days (historical) to +14 days (future)
    today = datetime.now()
    start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    
    url = f"https://members.yogasix.com/api/v2/locations/{LOCATION_SLUG}/schedule_entries?start_date={start_date}&end_date={end_date}"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json"
    })
    
    print(f"Querying REST API (Window: {start_date} to {end_date}):\n{url}")
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"API Request failed: {e}")
        return []

    entries = data.get("schedule_entries", [])
    events = []

    for entry in entries:
        title = entry.get("title", "").strip()
        inst_dict = entry.get("instructor") or {}
        instructor = inst_dict.get("name", "").strip()
        start_raw = entry.get("starts_at")
        end_raw = entry.get("ends_at")
        entry_id = entry.get("id")
        description_raw = entry.get("description") or ""

        if not title or not instructor or not start_raw or not end_raw:
            continue

        # Preserve original logic: Drop Staff placeholders and Mobility
        if "mobility" in title.lower() or instructor.lower() == "staff":
            continue

        # Format Description for iCalendar format (requires literal \n strings)
        clean_desc = description_raw.strip().replace("\r\n", "\\n").replace("\n", "\\n")
        desc_field = f"Instructor: {instructor}\\nStudio: YogaSix Arapahoe"
        if clean_desc:
            desc_field += f"\\n\\n{clean_desc}"

        emoji = get_class_emoji(title)

        try:
            s_dt = datetime.fromisoformat(start_raw)
            e_dt = datetime.fromisoformat(end_raw)
            
            start_str = s_dt.strftime("%Y%m%dT%H%M%S")
            end_str = e_dt.strftime("%Y%m%dT%H%M%S")

            events.append({
                "uid": entry_id,
                "title": title,
                "emoji": emoji,
                "instructor": instructor,
                "start_dt": s_dt, 
                "start_str": start_str,
                "end_str": end_str,
                "desc": desc_field
            })
        except Exception as e:
            print(f"Skipping entry {entry_id} due to time parse error: {e}")
            continue

    events.sort(key=lambda x: x["start_dt"])
    return events

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

if __name__ == "__main__":
    os.makedirs("public", exist_ok=True)
    events = fetch_schedule_api()

    print("\n" + "=" * 80)
    print(f"{'DATE / TIME':<22} | {'INSTRUCTOR':<18} | {'CLASS TYPE'}")
    print("=" * 80)
    for ev in events:
        dt_str = ev['start_dt'].strftime('%a %m/%d %I:%M%p')
        print(f"{dt_str:<22} | {ev['instructor']:<18} | {ev['emoji']} {ev['title']}")
    print("=" * 80)
    print(f"Total API verified events: {len(events)}\n")

    if events:
        build_ics(events, output_path="public/schedule.ics")
        print("Generated public/schedule.ics successfully.")
