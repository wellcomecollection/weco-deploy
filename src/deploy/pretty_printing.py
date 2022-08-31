import datetime


def pprint_date(date_obj, *, now=datetime.datetime.now()):
    assert date_obj <= now

    difference = now - date_obj

    is_today = date_obj.date() == now.date()
    is_yesterday = date_obj.date() == (now - datetime.timedelta(days=1)).date()

    if difference.total_seconds() <= 120:
        return "just now"
    elif is_today and difference.total_seconds() <= 60 * 60:
        return date_obj.strftime("today @ %H:%M") + " (%d min ago)" % (
            difference.total_seconds() // 60
        )
    elif is_today:
        return date_obj.strftime("today @ %H:%M")
    elif is_yesterday and difference.total_seconds() <= 60 * 60:
        return date_obj.strftime("yesterday @ %H:%M") + " (%d min ago)" % (
            difference.total_seconds() // 60
        )
    elif is_yesterday:
        return date_obj.strftime("yesterday @ %H:%M")
    else:
        result = date_obj.strftime("%a %d %B %Y @ %H:%M")

        # Trim the trailing zero from the day of the month, but not from the
        # timestamp.  Add an extra space to the month names and timestamps
        # all line up.
        if result[4] == "0":
            return result.replace(" 0", "  ", 1)
        else:
            return result


def pprint_duration(seconds):
    """
    Pretty-prints a duration.

    Examples:
        1m
        2m 3s

    Not meant for durations more than an hour.

    """
    if seconds < 60:
        return f"{seconds}s"
    else:
        minutes = seconds // 60
        seconds %= 60

        if seconds == 0:
            return f"{minutes}m"
        else:
            return f"{minutes}m {seconds}s"
