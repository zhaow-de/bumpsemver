import io
from abc import ABCMeta, abstractmethod
from difflib import unified_diff

from bumpsemver.version_part import Version


class FileTypeBase:
    __metaclass__ = ABCMeta

    def __init__(self, path, version_config, file_type, logger):
        self.path = path
        self._version_config = version_config
        self.file_type = file_type
        self.logger = logger

    @abstractmethod
    def should_contain_version(self, version: Version, context: dict) -> None:
        """
        Raise VersionNotFound if the parsed version isn't present in this file.
        Otherwise, return if the version number is present.
        """

    @abstractmethod
    def contains(self, search: str) -> bool:
        """
        Return True if the version string is present, otherwise, False
        """

    @abstractmethod
    def replace(self, current_version: Version, new_version: Version, context: dict, dry_run: bool) -> None:
        """
        Update the version if it is not a dry run
        """

    def update_file(self, file_content_before: str, file_content_after: str, dry_run: bool) -> None:
        """
        Write changes to the file if it is not a dry run
        """
        with open(self.path, "rt", encoding="utf-8") as orig_fp:
            _dummy = orig_fp.read()
            file_new_lines = orig_fp.newlines

        if file_content_before != file_content_after:
            # reassemble the file to retain the original os-specific newline separator
            self.logger.info(f"{'Would change' if dry_run else 'Changing'} {self.file_type} file {self.path}:")
            self.logger.info("\n".join(list(unified_diff(
                file_content_before.splitlines(),
                file_content_after.splitlines(),
                lineterm="",
                fromfile=f"a/{self.path}",
                tofile=f"b/{self.path}"
            ))))
        else:
            self.logger.info(f"{'Would not change' if dry_run else 'Not changing'} {self.file_type} file {self.path}")

        if not dry_run:
            with io.open(self.path, "wt", encoding="utf-8", newline=file_new_lines) as orig_fp:
                orig_fp.write(file_content_after)

    def __str__(self):
        return self.path

    @abstractmethod
    def __repr__(self):
        pass
