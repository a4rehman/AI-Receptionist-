from datetime import datetime, timedelta, timezone, date
from typing import Optional
import re
import pytz


DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_relative_date(text: str, tz: str = "UTC") -> Optional[date]:
    text_lower = text.lower().strip()
    today = date.today()

    if "today" in text_lower:
        return today
    if "tomorrow" in text_lower:
        return today + timedelta(days=1)
    if "day after tomorrow" in text_lower:
        return today + timedelta(days=2)

    for day_name, day_num in DAY_MAP.items():
        if day_name in text_lower:
            days_ahead = (day_num - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if "next" in text_lower:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    date_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text_lower)
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def parse_time_of_day(text: str) -> Optional[str]:
    text_lower = text.lower().strip()

    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    if "morning" in text_lower:
        return "09:00"
    if "afternoon" in text_lower:
        return "14:00"
    if "evening" in text_lower:
        return "18:00"
    if "noon" in text_lower:
        return "12:00"

    return None


def convert_to_utc(dt: datetime, from_tz: str) -> datetime:
    if dt.tzinfo is None:
        tz_obj = pytz.timezone(from_tz)
        dt = tz_obj.localize(dt)
    return dt.astimezone(pytz.UTC)


def convert_from_utc(dt: datetime, to_tz: str) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    tz_obj = pytz.timezone(to_tz)
    return dt.astimezone(tz_obj)


def format_datetime(dt: datetime, tz: str = "UTC", fmt: str = "%A, %B %d at %I:%M %p") -> str:
    local_dt = convert_from_utc(dt, tz) if dt.tzinfo else dt
    return local_dt.strftime(fmt)


def get_day_of_week(d: date) -> int:
    return d.weekday()


def is_within_business_hours(dt: datetime, open_time: str, close_time: str) -> bool:
    time_str = dt.strftime("%H:%M")
    return open_time <= time_str < close_time


def add_minutes(time_str: str, minutes: int) -> str:
    h, m = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def time_to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
