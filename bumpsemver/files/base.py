import io
from abc import ABCMeta, abstractmethod
from difflib import unified_diff


class FileTypeBase(object):
    __metaclass__ = ABCMeta

    def __init__(self, path, version_config, file_type, logger):
        self.path = path
        self._version_config = version_config
        self.file_type = file_type
        self.logger = logger

    @abstractmethod
    def should_contain_version(self, version, context) -> None:
        """
        Raise VersionNotFound if the version number isn't present in this file.

        Return normally if the version number is in fact present.
        """
        pass

    def contains(self, search) -> bool:
        pass

    def replace(self, current_version, new_version, context, dry_run) -> None:
        pass

    def update_file(self, file_content_before: str, file_content_after: str, dry_run: bool) -> None:
        with open(self.path, "rt", encoding="utf-8") as f:
            _dummy = f.read()
            file_new_lines = f.newlines

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
            with io.open(self.path, "wt", encoding="utf-8", newline=file_new_lines) as f:
                f.write(file_content_after)

    def __str__(self):
        return self.path

    @abstractmethod
    def __repr__(self):
        pass
