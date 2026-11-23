DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50

def positive_int(value, default):
    """Retrieve a positive integer from the query parameters."""

    if value is None:
        return default

    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None