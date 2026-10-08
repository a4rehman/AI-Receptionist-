from datetime import date, datetime
import pytest
from receptionist.utils.datetime_utils import (
    parse_relative_date, parse_time_of_day, convert_to_utc, convert_from_utc,
    format_datetime, add_minutes, time_to_minutes, minutes_to_time,
)


class TestParseRelativeDate:
    def test_today(self):
        result = parse_relative_date("today")
        assert result == date.today()

    def test_tomorrow(self):
        result = parse_relative_date("tomorrow")
        assert result == date.today() + __import__("datetime").timedelta(days=1)

    def test_day_of_week(self):
        result = parse_relative_date("friday")
        assert result is not None
        assert result.weekday() == 4

    def test_next_monday(self):
        result = parse_relative_date("next monday")
        assert result is not None
        assert result.weekday() == 0

    def test_invalid(self):
        result = parse_relative_date("invalid text")
        assert result is None


class TestParseTimeOfDay:
    def test_morning(self):
        assert parse_time_of_day("morning") == "09:00"

    def test_afternoon(self):
        assert parse_time_of_day("afternoon") == "14:00"

    def test_specific_time(self):
        assert parse_time_of_day("3:30 pm") == "15:30"

    def test_noon(self):
        assert parse_time_of_day("noon") == "12:00"

    def test_time_not_confused_by_appointment_id_digits(self):
        msg = "reschedule appointment apt_8b29c39833a0 to 2026-10-12 at 11:00 am"
        assert parse_time_of_day(msg) == "11:00"

    def test_date_digits_not_parsed_as_time(self):
        assert parse_time_of_day("2026-10-12 at 14:00") == "14:00"

    def test_hour_with_am_pm_no_colon(self):
        assert parse_time_of_day("tomorrow at 8 am") == "08:00"

    def test_bare_number_only_when_whole_text(self):
        assert parse_time_of_day("8") == "08:00"
        assert parse_time_of_day("order 8 widgets") is None


class TestTimeConversion:
    def test_add_minutes(self):
        assert add_minutes("09:00", 30) == "09:30"
        assert add_minutes("09:45", 30) == "10:15"

    def test_time_to_minutes(self):
        assert time_to_minutes("09:30") == 570
        assert time_to_minutes("14:00") == 840

    def test_minutes_to_time(self):
        assert minutes_to_time(570) == "09:30"
        assert minutes_to_time(840) == "14:00"
