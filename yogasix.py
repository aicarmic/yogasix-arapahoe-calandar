import os
import re
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

URL = "https://www.yogasix.com/location/arapahoe"
LOCATION = "6340 S Parker Rd, Unit 2, Aurora, CO 80016"

def parse_time(time_str, date_str):
    match = re.match(r"(\d+:\d+[ap]m)-(\d+:\d+[ap]m)", time_str.strip(), re.IGNORECASE)
    if not match:
        return None, None
    start_t, end_t = match.groups()
    current_year = datetime.now().year

    date_match = re.search(r"(\d{1,2})/(\d{1,2})", date_str)
    if date_match:
        month, day = map(int, date_match.groups())
    else:
        now = datetime.now()
        month, day = now.month, now.day

    start_dt = datetime.strptime(f"{current_year}-{month:02d}-{day:02d} {start_t.upper()}", "%Y-%m-%d %I:%M%p")
    end_dt = datetime.strptime(f"{current_year}-{month:02d}-{day:02d} {end_t.upper()}", "%Y-%m-%d %I:%M%p")
    return start_dt, end_dt

def fetch_schedule():
    events = []
    seen_keys = set()

    with sync_playwright() as p:
        print(f"Navigating to {URL}...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        for week in range(2):
            print(f"Scraping Week {week + 1}...")
            if week > 0:
                next_btn = page.query_selector("button:has-text('Next Week'), .next-week, [aria-label='Next Week']")
                if next_btn and next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(2500)

            day_tabs = page.query_selector_all("button:has-text('/'), [class*='day-tab'], [class*='schedule__day']")
            
            if day_tabs:
                for tab in day_tabs:
                    tab_text = tab.inner_text().strip()
                    tab.click()
                    page.wait_for_timeout(400)

                    cards = page.query_selector_all(".c-schedule__item, .schedule-item, div[class*='schedule']")
                    for card in cards:
                        if not card.is_visible():
                            continue
                        text = card.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        
                        title = next((l for l in lines if any(k in l for k in ["Y6", "Flow", "Sculpt", "Restore", "Mobility", "101", "Workshop"])), None)
                        time_range = next((l for l in lines if re.search(r"\d+:\d+[ap]m-\d+:\d+[ap]m", l, re.I)), None)
                        instructor = next((l for l in lines if re.search(r"^[A-Z][a-z]+ [A-Z]\.?$", l)), "Staff")

                        if title and time_range:
                            start_dt, end_dt = parse_time(time_range, tab_text)
                            if start_dt and end_dt:
                                key = (title, start_dt.isoformat())
                                if key not in seen_keys:
                                    seen_keys.add(key)
                                    events.append({
                                        "title": title,
                                        "instructor": instructor,
                                        "start": start_dt,
                                        "end": end_dt,
                                        "desc": f"Instructor: {instructor}\\nStudio: YogaSix Arapahoe"
                                    })
        browser.close()

    print(f"Total unique classes captured: {len(events)}")
    return events

def build_ics(events, output_path="public/schedule.ics"):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//YogaSix Arapahoe Sync//EN",
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
        start_str = ev["start"].strftime("%Y%m%dT%H%M%S")
        end_str = ev["end"].strftime("%Y%m%dT%H%M%S")
        clean_title = re.sub(r'[^a-zA-Z0-9]', '', ev['title'])
        uid = f"y6-{start_str}-{clean_title}@yogasix.local"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID=America/Denver:{start_str}",
            f"DTEND;TZID=America/Denver:{end_str}",
            f"SUMMARY:🤸‍♂️ {ev['title']} - {ev['instructor']}",
            f"DESCRIPTION:{ev['desc']}",
            f"LOCATION:{LOCATION}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    os.makedirs("public", exist_ok=True)
    events = fetch_schedule()
    if events:
        build_ics(events, output_path="public/schedule.ics")