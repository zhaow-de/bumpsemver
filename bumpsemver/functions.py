import re


class NumericFunction:
    """
    This is a class that provides a numeric function for version parts.
    It simply starts with the provided first_value (0 by default) and increases it following the sequence of integer numbers.

    This function also supports alphanumeric parts, altering just the numeric part (e.g. 'r3' --> 'r4'). Only the first numeric group
    found in the part is considered (e.g. 'r3-001' --> 'r4-001').
    """

    FIRST_NUMERIC = re.compile(r"([^\d]*)(\d+)(.*)")

    def __init__(self, first_value=None):

        if first_value is not None:
            try:
                _, _, _ = self.FIRST_NUMERIC.search(first_value).groups()
            except AttributeError:
                # pylint: disable=raise-missing-from
                raise ValueError(f"The given first value {first_value} does not contain any digit")
        else:
            first_value = 0

        self.first_value = str(first_value)

    def bump(self, value):
        part_prefix, part_numeric, part_suffix = self.FIRST_NUMERIC.search(value).groups()
        bumped_numeric = int(part_numeric) + 1

        return "".join([part_prefix, str(bumped_numeric), part_suffix])
