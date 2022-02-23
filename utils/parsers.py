def field_to_string(string):
    return " ".join(string.split("_")).capitalize()


def parse_details(data):
    if not data:
        raise ValueError("data must not be null, empty, etc.")

    if isinstance(data, dict):
        items = list(data.items())
        max_key_len = len(max(map(str, data.keys()), key=len)) + 1
        max_val_len = len(max(map(str, data.values()), key=len)) + 1
        if len(items) > 1:
            return (
                "├ "
                + "\n├ ".join(
                    [
                        f"`{field_to_string(k):<{max_key_len}}: {v:<{max_val_len}}`"
                        for k, v in items[:-1]
                    ]
                )
                + f"\n└ `{field_to_string(items[-1][0]):<{max_key_len}}: {items[-1][1]:<{max_key_len}}`"
            )
        return f"└ {field_to_string(items[-1][0])}: {items[-1][1]}"
    elif isinstance(data, list):
        items = data
        if len(items) > 1:
            return (
                "├ "
                + "\n├ ".join([value for value in items[:-1]])
                + f"\n└ {items[-1]}"
            )
        return f"└ {items[-1]}"


def parse_list_details(data, item_emoji="➡️"):
    if not data:
        return ""
    if isinstance(data, dict):
        return "\n".join(
            [
                f"\n{item_emoji} {title}\n{parse_details(stats)}"
                for title, stats in data.items()
            ]
        )
    elif isinstance(data, list):
        return f"{data[0]}\n{parse_details(data[1:])}"


def parse_global(stats, items, title, emoji, footer=""):
    return f"""
*{title}*
{parse_details(stats)}
{parse_list_details(items, item_emoji=emoji)}
{footer}
"""
