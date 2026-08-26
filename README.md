# YogaSix Arapahoe - Dynamic Calendar Sync 🤸‍♂️
Y6 doesn't provide a webcal feed for their schedules. I prefer to have this info on my Google Calendar. This is an automated pipeline that scrapes the upcoming two-week class schedule from YogaSix Arapahoe, generates a standards-compliant iCalendar (`.ics`) feed, and publishes it via GitHub Pages as an auto-updating `webcal://` subscription.

## Features
- **Automated Sync**: Runs twice daily (04:00 & 16:00 MDT) via GitHub Actions.
- **Two-Week Window**: Captures current and next week's schedule tabs.
- **Emoji-Prefixed**: Formats event summaries with `🤸‍♂️` for scannability.
- **Transparent Availability**: Marks all events as `TRANSP:TRANSPARENT` (Free) so they do not block your calendar or conflict with scheduling tools.
- **Stateless WebCal**: A single published endpoint that multiple users can subscribe to independently.

---

## 📅 Calendar Subscription
Subscribe directly in your calendar client of choice using the following URL:
webcal://aicarmic.github.io/yogasix-arapahoe-calendar/schedule.ics
