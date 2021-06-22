import logging

from bumpsemver.version_part import Version

from bumpsemver.exceptions import VersionNotFoundException
from bumpsemver.files import FileTypes
from bumpsemver.files.base import FileTypeBase

logger = logging.getLogger(__name__)


class ConfiguredGenericFile(FileTypeBase):

    def __init__(self, path, version_config):
        self.path = path
        self._version_config = version_config
        self.file_type = FileTypes.GENERIC
        super().__init__(path, version_config, FileTypes.GENERIC, logger)

    def should_contain_version(self, version: Version, context: dict) -> None:
        """
        Raise VersionNotFound if the version number isn't present in this file.

        Return normally if the version number is in fact present.
        """
        context["current_version"] = self._version_config.serialize(version, context)
        search_expression = self._version_config.search.format(**context)

        if self.contains(search_expression):
            return

        # the `search` pattern did not match, but the original supplied version number (representing the same version part values) might
        # match instead.

        # check whether `search` isn't customized, i.e. should match only very specific parts of the file
        search_pattern_is_default = self._version_config.search == "{current_version}"

        if search_pattern_is_default and self.contains(version.original):
            # original version is present and we're not looking for something more specific -> this is accepted as a match
            return

        # version not found
        raise VersionNotFoundException(f"Did not find '{search_expression}' in file: '{self.path}'")

    def contains(self, search: str) -> bool:
        if not search:
            return False

        with open(self.path, "rt", encoding="utf-8") as orig_fp:
            search_lines = search.splitlines()
            lookbehind = []

            for lineno, line in enumerate(orig_fp.readlines()):
                lookbehind.append(line.rstrip("\n"))

                if len(lookbehind) > len(search_lines):
                    lookbehind = lookbehind[1:]

                if search_lines[0] in lookbehind[0] and search_lines[-1] in lookbehind[-1] and search_lines[1:-1] == lookbehind[1:-1]:
                    logger.info(f"Found '{search}' in {self.path} at line {lineno - (len(lookbehind) - 1)}: {line.rstrip()}")
                    return True
        return False

    def replace(self, current_version: Version, new_version: Version, context: dict, dry_run: bool) -> None:

        with open(self.path, "rt", encoding="utf-8") as orig_fp:
            file_content_before = orig_fp.read()

        context["current_version"] = self._version_config.serialize(current_version, context)
        context["new_version"] = self._version_config.serialize(new_version, context)

        search_for = self._version_config.search.format(**context)
        replace_with = self._version_config.replace.format(**context)

        file_content_after = file_content_before.replace(search_for, replace_with)

        if file_content_before == file_content_after:
            file_content_after = file_content_before.replace(current_version.original, replace_with)

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredGenericFile:{self.path}>"
