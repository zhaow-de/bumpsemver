import logging
from datetime import datetime
from typing import Dict, Union

from bumpsemver.exceptions import VersionNotFoundError
from bumpsemver.files.base import FileTypeBase
from bumpsemver.version_part import Version, VersionConfig

logger = logging.getLogger(__name__)


class ConfiguredPlainTextFile(FileTypeBase):

    def __init__(self, filename, version_config: VersionConfig):
        super().__init__(filename, version_config, "plaintext", None, logger)

    def should_contain_version(self, version: Version, context: dict) -> None:
        """
        Raise VersionNotFound if the version number isn't present in this file.

        Return normally if the version number is in fact present.
        """
        context["current_version"] = self._version_config.serialize(version)
        search_expression = self._version_config.search.format(**context)

        if self.contains(search_expression):
            return

        # the `search` pattern did not match,
        # but the original supplied version number (representing the same version part values) might match instead.

        # check whether `search` isn't customized, i.e., should match only very specific parts of the file
        search_pattern_is_default = self._version_config.search == "{current_version}"

        if search_pattern_is_default and self.contains(version.original):
            # the original version is present, and we're not looking for something more specific
            # -> this is accepted as a match
            return

        raise VersionNotFoundError(search_expression, self.filename)

    def contains(self, search: str) -> bool:
        if not search:
            return False

        with open(self.filename, "rt", encoding="utf-8") as orig_fp:
            search_lines = search.splitlines()
            lookbehind = []

            for lineno, line in enumerate(orig_fp.readlines()):
                lookbehind.append(line.rstrip("\n"))

                if len(lookbehind) > len(search_lines):
                    lookbehind = lookbehind[1:]

                if (
                    search_lines[0] in lookbehind[0]
                    and search_lines[-1] in lookbehind[-1]
                    and search_lines[1:-1] == lookbehind[1:-1]
                ):
                    logger.info(
                        f"Found '{search}' in {self.filename} at line {lineno - (len(lookbehind) - 1)}: {line.rstrip()}"
                    )
                    return True
        return False

    def replace(
        self, current_version: Version, new_version: Version, context: Dict[str, Union[str, datetime]], dry_run: bool
    ) -> None:

        with open(self.filename, "rt", encoding="utf-8") as orig_fp:
            file_content_before = orig_fp.read()

        context["current_version"] = self._version_config.serialize(current_version)
        context["new_version"] = self._version_config.serialize(new_version)

        search_for = self._version_config.search.format(**context)
        replace_with = self._version_config.replace.format(**context)

        file_content_after = file_content_before.replace(search_for, replace_with)

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredPlainTextFile:{self.filename}>"
