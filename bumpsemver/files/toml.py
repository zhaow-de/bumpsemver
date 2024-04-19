import logging
from datetime import datetime
from typing import Dict, Union

from tomlkit.exceptions import EmptyKeyError, KeyAlreadyPresent, NonExistentKey, ParseError, UnexpectedCharError

from bumpsemver.exceptions import (
    InvalidFileError,
    MultiValuesMismatchError,
    PathNotFoundError,
    SingleValueMismatchError,
)
from bumpsemver.files.base import FileTypeBase
from bumpsemver.files.tomlpath import TomlPath
from bumpsemver.version_part import Version, VersionConfig

logger = logging.getLogger(__name__)


class ConfiguredTOMLFile(FileTypeBase):
    def __init__(self, filename: str, version_config: VersionConfig, file_type="toml", tomlpath: str = None):
        super().__init__(filename, version_config, file_type, tomlpath, logger)

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version)
        context["current_version"] = current_version

        try:
            self.contains(current_version)
        except KeyError:
            pass

    def contains(self, search: str) -> bool:
        if not TomlPath.is_valid(self.xpath):
            raise PathNotFoundError(self.xpath, "toml", self.filename) from None

        try:
            with open(self.filename, "rt") as fin:
                content = fin.read()
                value = TomlPath.query(content, self.xpath)
                if value is None or value == []:
                    raise NonExistentKey(self.xpath)
                if isinstance(value, list):
                    for item in value:
                        if item != search:
                            raise MultiValuesMismatchError(self.xpath, "toml", self.filename, value, search)
                elif value != search:
                    raise SingleValueMismatchError(self.xpath, "toml", self.filename, value, search)
                return True
        except (EmptyKeyError, KeyAlreadyPresent, ParseError, UnexpectedCharError) as exc:
            raise InvalidFileError(self.filename, "toml") from exc
        except (IndexError, NonExistentKey) as exc:
            raise PathNotFoundError(self.xpath, "toml", self.filename) from exc

    def replace(
        self, current_version: Version, new_version: Version, context: Dict[str, Union[str, datetime]], dry_run: bool
    ) -> None:
        current_version_str = self._version_config.serialize(current_version)
        context["current_version"] = current_version_str
        new_version_str = self._version_config.serialize(new_version)
        context["new_version"] = new_version_str

        with open(self.filename, "rt") as fin:
            content = fin.read()
            value = TomlPath.update(content, self.xpath, new_version_str)
            self.update_file(content, value, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredTOMLFile:{self.filename}>"
