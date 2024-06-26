import logging
import re
import string
from typing import Dict, List, Optional

from bumpsemver.exceptions import (
    CannotParseVersionError,
)
from bumpsemver.functions import NumericFunction
from bumpsemver.utils import key_value_string

logger = logging.getLogger(__name__)


class NumericVersionPartConfiguration:
    function_cls = NumericFunction

    def __init__(self, *args, **kwargs):
        self.function = self.function_cls(*args, **kwargs)

    @property
    def first_value(self):
        return str(self.function.first_value)

    def bump(self, value=None) -> str:
        return self.function.bump(value)


class VersionPart:
    """
    This class represents part of a version number. It contains a self.config
    object that rules how the part behaves when increased or reset.
    """

    def __init__(self, value: str, config=None):
        self._value = value

        if config is None:
            config = NumericVersionPartConfiguration()

        self.config = config

    @property
    def value(self):
        return self._value

    def copy(self):
        return VersionPart(self._value)

    def bump(self):
        return VersionPart(self.config.bump(self.value), self.config)

    def __format__(self, format_spec):
        return self.value

    def __repr__(self):
        return f"<bumpsemver.VersionPart:{self.config.__class__.__name__}:{self.value}>"

    def __eq__(self, other):
        return self.value == other.value

    def null(self):
        return VersionPart(self.config.first_value, self.config)


class Version:
    def __init__(self, values: Dict[str, VersionPart], original=None):
        self.values = dict(values)
        self.original = original

    def __getitem__(self, key):
        return self.values[key]

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return f"<bumpsemver.Version:{key_value_string(self.values)}>"

    def bump(self, part_name: str, order: List[str]):
        bumped = False

        new_values = {}

        for label in order:
            if label not in self.values:
                continue
            if label == part_name:
                new_values[label] = self.values[label].bump()
                bumped = True
            elif bumped:
                new_values[label] = self.values[label].null()
            else:
                new_values[label] = self.values[label].copy()

        new_version = Version(new_values)

        return new_version


def labels_for_format(serialize_format):
    return (label for _, label, _, _ in string.Formatter().parse(serialize_format) if label)


class VersionConfig:
    """
    Holds a complete representation of a version string.
    """

    def __init__(
        self,
        search: str = None,
        replace: str = None,
    ):
        self.parse_regex = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)", re.VERBOSE)
        self.serialize_format = "{major}.{minor}.{patch}"

        self.search = search
        self.replace = replace

    def order(self):
        # currently, order depends on the first given serialization format this seems like enough
        # because this should be the most complete format
        return labels_for_format(self.serialize_format)

    def parse(self, version_string: str = None) -> Optional[Version]:
        if not version_string:
            return None

        regexp_one_line = "".join([line.split("#")[0].strip() for line in self.parse_regex.pattern.splitlines()])

        logger.info(f"Parsing version '{version_string}' using regexp '{regexp_one_line}'")

        match = self.parse_regex.search(version_string)

        _parsed = {}
        if not match:
            logger.warning(
                f"Evaluating 'parse' option: '{self.parse_regex.pattern}' "
                f"does not parse current version '{version_string}'"
            )
            return None

        for key, value in match.groupdict().items():
            _parsed[key] = VersionPart(value, None)

        version = Version(_parsed, version_string)

        logger.info(f"Parsed the following values: {key_value_string(version.values)}")

        return version

    # noinspection PyMethodMayBeStatic
    def _serialize(self, version: Version, serialize_format: str) -> str:
        """
        Attempts to serialize a version with the given serialization format.
        """
        values: Dict[str, VersionPart] = {}
        for key in version:
            values[key] = version[key]

        # test whether all parts required in the format have values
        serialized = serialize_format.format(**values)

        return serialized

    def serialize(self, version: Version) -> str:
        try:
            serialized = self._serialize(version, self.serialize_format)
            logger.debug(f"Serialized to '{serialized}'")
            return serialized
        except TypeError as exc:
            raise CannotParseVersionError() from exc
