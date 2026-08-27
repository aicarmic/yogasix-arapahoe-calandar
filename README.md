# YogaSix Arapahoe - Dynamic Calendar Sync 🤸‍♂️
If you prefer to have the Y6 class schedule on your personal calendar (Google/Apple Calendar, Outlook, etc) look no further.

Since Y6 doesn't provide a calendar feed for their class schedule, this automatically fetches the upcoming two-week class schedule from YogaSix Arapahoe twice daily, and then maintains a published `.ics` calendar feed as a `webcal://` subscription!

<img width="1141" height="829" alt="Google Calendar 2026-08-26 10 38 04" src="https://github.com/user-attachments/assets/f9b69c01-865d-4051-9745-2716b97eef6a" />

## Features
- **Automated Sync**: Runs twice daily (04:00 & 16:00 MDT).
- **Two-Week Window**: Captures current and next week's schedule tabs, maintains a 30-day lookback.
- **Emoji-Prefixed**: Formats event summaries with emojis for easy scannability.
- **Transparent Availability**: Keeps all events as `TRANSP:TRANSPARENT` (Free) so they do not block your calendar or conflict with scheduling tools.
- **Stateless WebCal**: A single published endpoint that multiple users can subscribe to independently.

---

## 📅 INSTRUCTIONS: Add Y6 Class Schedule to your Calendar
Subscribe directly in your calendar client of choice using the following URL:
https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics 

### Google Calendar
1. Open Google Calendar in your browser.
2. On the left sidebar, find Other calendars and click the `+` icon.
3. Select `From URL`.
4. Paste the calendar URL: [https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics](https://aicarmic.github.io/yogasix-arapahoe-calandar/schedule.ics)
5. Click Add calendar.
