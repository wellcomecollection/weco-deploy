import datetime


def pprint_nested_tree(tree, indent=0):
    lines = []

    if indent == 0:
        lines.append(".")

    if isinstance(tree, str):
        return tree

    # This is a bit of a hard-coded fudge for a common case that causes it
    # to be printed in a slightly more useful way.
    if tree.keys() == {"latest", "prod", "stage"}:
        entries = [
            ("latest", tree["latest"]),
            ("stage", tree["stage"]),
            ("prod", tree["prod"])
        ]
    else:
        entries = sorted(tree.items())

    for i, (key, nested_tree) in enumerate(entries, start=1):
        if i == len(entries):
            lines.append("└── " + key)

            if isinstance(nested_tree, str):
                lines[-1] = lines[-1].ljust(40) + nested_tree
            else:
                lines.extend([
                    "    " + line
                    for line in pprint_nested_tree(nested_tree, indent=indent + 1)
                ])
        else:
            lines.append("├── " + key)
            if isinstance(nested_tree, str):
                lines[-1] = lines[-1].ljust(40) + nested_tree
            else:
                lines.extend([
                    "│   " + line
                    for line in pprint_nested_tree(nested_tree, indent=indent + 1)
                ])

    return lines


def build_tree_from_paths(paths):
    tree = {}

    for path, value in paths.items():
        curr_tree = tree
        path_components = path.strip("/").split("/")
        for component in path_components:
            try:
                curr_tree = curr_tree[component]
            except KeyError:
                if component == path_components[-1]:
                    curr_tree[component] = value
                else:
                    curr_tree[component] = {}
                curr_tree = curr_tree[component]

    return tree


def pprint_path_keyval_dict(paths):
    tree = build_tree_from_paths(paths)
    return pprint_nested_tree(tree)


def pprint_date(date_obj, *, now=datetime.datetime.now()):
    assert date_obj <= now

    difference = (now - date_obj)

    is_today = date_obj.date() == now.date()
    is_yesterday = date_obj.date() == (now - datetime.timedelta(days=1)).date()

    if difference.total_seconds() <= 120:
        return "just now"
    elif is_today and difference.total_seconds() <= 60 * 60:
        return date_obj.strftime("today @ %H:%M") + " (%d min ago)" % (difference.total_seconds() // 60)
    elif is_today:
        return date_obj.strftime("today @ %H:%M")
    elif is_yesterday and difference.total_seconds() <= 60 * 60:
        return date_obj.strftime("yesterday @ %H:%M") + " (%d min ago)" % (difference.total_seconds() // 60)
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
