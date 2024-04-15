import logging
from datetime import datetime
from typing import Dict, Union

from bumpsemver.exceptions import VersionNotFoundError
from bumpsemver.files import FileTypes
from bumpsemver.files.base import FileTypeBase
from bumpsemver.files.tomlpath import TomlPath
from bumpsemver.version_part import Version

logger = logging.getLogger(__name__)


class ConfiguredTOMLFile(FileTypeBase):
    def __init__(self, path, tomlpath, version_config):
        super().__init__(path, version_config, FileTypes.TOML, logger)
        self.toml_path = tomlpath

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version)
        context["current_version"] = current_version

        try:
            if self.contains(current_version):
                return
        except KeyError:
            pass
        # version not found or mismatched
        raise VersionNotFoundError(
            f"Did not find '{current_version}' at tomlpath '{self.toml_path}' in file: '{self.path}'"
        ) from None

    def contains(self, search: str) -> bool:
        with open(self.path, "rt") as fin:
            content = fin.read()
            value = TomlPath.query(content, self.toml_path)
            return value == search

    def replace(
        self, current_version: Version, new_version: Version, context: Dict[str, Union[str, datetime]], dry_run: bool
    ) -> None:
        current_version_str = self._version_config.serialize(current_version)
        context["current_version"] = current_version_str
        new_version_str = self._version_config.serialize(new_version)
        context["new_version"] = new_version_str

        with open(self.path, "rt") as fin:
            content = fin.read()
            value = TomlPath.update(content, self.toml_path, new_version_str)
            self.update_file(content, value, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredTOMLFile:{self.path}>"
