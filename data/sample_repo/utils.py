def add_item(item, bucket=[]):  # mutable default argument
    bucket.append(item)
    return bucket


def categorize(score):
    result = "unknown"
    if score > 90:
        if score > 95:
            result = "A+"
        else:
            result = "A"
    elif score > 80:
        result = "B"
    elif score > 70:
        result = "C"
    elif score > 60:
        result = "D"
    else:
        if score < 0:
            result = "invalid"
        else:
            result = "F"
    unused_local = 42
    return result
