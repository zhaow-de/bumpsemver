def key_value_string(d):
    return ", ".join(f"{k}={v}" for k, v in sorted(d.items()))
