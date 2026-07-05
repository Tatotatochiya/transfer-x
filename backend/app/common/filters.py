from datetime import date, datetime, time, timedelta


def apply_date_range(query, column, date_from: date | None, date_to: date | None):
    """Filter `query` to rows where `column` falls within [date_from, date_to],
    inclusive of the whole of date_to. `column` is a DateTime column."""
    if date_from is not None:
        query = query.where(column >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.where(column < datetime.combine(date_to + timedelta(days=1), time.min))
    return query
