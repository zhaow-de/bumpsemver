"""
Commonly used utilities
"""


def key_value_string(obj: dict) -> str:
    """
    Dump a dict object into a string representation of key-value pairs
    """
    return ", ".join(f"{k}={v}" for k, v in sorted(obj.items()))
