import dateparser
from datetime import datetime, timedelta

# TODO handle more complex phrases like "the first week of next month" and others


def get_week_range(date_obj):
    """Calculates the start (Monday) and end (Sunday) of the week for a given date."""
    start_of_week = date_obj - timedelta(days=date_obj.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')


def get_month_range(date_obj):
    """Calculates the start and end of the month for a given date."""
    # To get the first day, just replace the day with 1
    first_day = date_obj.replace(day=1)
    # To get the last day, go to the first day of the *next* month and subtract one day
    next_month = first_day.replace(day=28) + timedelta(days=4)  # safely go to next month
    last_day = next_month - timedelta(days=next_month.day)
    return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')


def temporal_word_parser(text: str) -> str | tuple[str, str] | None:
    """
    Parses a string with temporal words and returns a date or date range.
    """
    text = text.lower()

    # Handle ranges first
    if 'week' in text:
        # dateparser will return a date within the specified week
        ref_date = dateparser.parse(text)
        if ref_date:
            return get_week_range(ref_date)

    if 'month' in text:
        ref_date = dateparser.parse(text)
        if ref_date:
            return get_month_range(ref_date)

    if 'year' in text:
        ref_date = dateparser.parse(text)
        if ref_date:
            start_of_year = ref_date.replace(month=1, day=1)
            end_of_year = ref_date.replace(month=12, day=31)
            return start_of_year.strftime('%Y-%m-%d'), end_of_year.strftime('%Y-%m-%d')

    # Handle single dates
    parsed_date = dateparser.parse(text)
    if parsed_date:
        return parsed_date.strftime('%Y-%m-%d')
    return None