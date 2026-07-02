def get_int_or_none(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def avg(values):
    numeric_values = []
    for value in values:
        if value in ("", None):
            continue
        try:
            numeric_values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numeric_values:
        return ""
    return round(sum(numeric_values) / len(numeric_values), 1)


def median(values):
    numeric_values = []
    for value in values:
        if value in ("", None):
            continue
        try:
            numeric_values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numeric_values:
        return ""
    numeric_values.sort()
    mid = len(numeric_values) // 2
    if len(numeric_values) % 2 == 1:
        return round(numeric_values[mid], 1)
    return round((numeric_values[mid - 1] + numeric_values[mid]) / 2, 1)


def min_value(values):
    if not values:
        return ""
    return round(min(values), 1)


def max_value(values):
    if not values:
        return ""
    return round(max(values), 1)


def variance(values):
    if not values:
        return ""
    mean = sum(values) / len(values)
    return round(sum((v - mean) ** 2 for v in values) / len(values), 1)


def std(values):
    if not values:
        return ""
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return round(var ** 0.5, 1)


def gap(my_values, opp_values, func):
    my_value = func(my_values)
    opp_value = func(opp_values)
    if my_value == "" or opp_value == "":
        return ""
    return format_signed(round(my_value - opp_value, 1))


def gap_value(my_values, opp_values, func):
    my_value = func(my_values)
    opp_value = func(opp_values)
    if my_value == "" or opp_value == "":
        return ""
    try:
        return round(float(my_value) - float(opp_value), 1)
    except (TypeError, ValueError):
        return ""


def format_signed(value):
    if value == 0:
        return "0"
    sign = "+" if value > 0 else "-"
    return f"{sign}{abs(value)}"
