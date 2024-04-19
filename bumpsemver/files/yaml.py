import logging
import pathlib
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, Union

from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO
from ruamel.yaml.parser import ParserError
from yamlpath import Processor, YAMLPath
from yamlpath.common import Parsers
from yamlpath.exceptions import YAMLPathException
from yamlpath.wrappers import ConsolePrinter

from bumpsemver.exceptions import (
    BumpVersionError,
    InvalidFileError,
    MultiValuesMismatchError,
    PathNotFoundError,
    SingleValueMismatchError,
)
from bumpsemver.files.base import FileTypeBase
from bumpsemver.version_part import Version, VersionConfig

logger = logging.getLogger(__name__)


class InvalidYAMLError(BumpVersionError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ConfiguredYAMLFile(FileTypeBase):
    def __init__(self, filename: str, version_config: VersionConfig, file_type="yaml", yamlpath: str = None):
        super().__init__(filename, version_config, file_type, yamlpath, logger)
        self.yaml = Parsers.get_yaml_editor()
        self.yaml_logging_args = SimpleNamespace(quiet=True, verbose=False, debug=False)
        self.yaml_log = ConsolePrinter(self.yaml_logging_args)

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version)
        context["current_version"] = current_version

        self.contains(current_version)

    def contains(self, search: str) -> bool:
        # yamlpath is too resilient to swallow the exception when the json file is invalid.
        # instead of parsing the logs to find the error,
        # we simply accept the performance penalty,
        # and do an extra parsing round to check if the json file is valid
        try:
            yaml = YAML(typ="safe")
            yaml.load(pathlib.Path(self.filename))
        except ParserError as exc:
            raise InvalidFileError(self.filename, "yaml") from exc
        try:
            processor = self.__get_processor()
            yaml_path = YAMLPath(self.xpath)
            nodes = [node.node for node in list(processor.get_nodes(yaml_path, mustexist=True))]
            if len(nodes) == 1:
                if nodes[0] != search:
                    raise SingleValueMismatchError(self.xpath, "yaml", self.filename, nodes[0], search)
            else:
                for node in nodes:
                    if node != search:
                        raise MultiValuesMismatchError(self.xpath, "yaml", self.filename, nodes, search)
            return True
        except YAMLPathException as ex:
            raise PathNotFoundError(self.xpath, "yaml", self.filename) from ex

    def __dump(self, data) -> str:
        stream = StringIO()
        self.yaml.dump(data, stream)
        return stream.getvalue()

    def __get_processor(self):
        with open(self.filename, "rb") as fin:
            content = fin.read().decode("utf-8")
            (yaml_data, doc_loaded) = Parsers.get_yaml_data(self.yaml, self.yaml_log, content, literal=True)
            if not doc_loaded:
                raise InvalidYAMLError(f"Failed in reading YAML file '{self.filename}'")
            processor = Processor(self.yaml_log, yaml_data)
            return processor

    def replace(
        self, current_version: Version, new_version: Version, context: Dict[str, Union[str, datetime]], dry_run: bool
    ) -> None:
        processor = self.__get_processor()
        file_content_before = self.__dump(processor.data)

        current_version_str = self._version_config.serialize(current_version)
        context["current_version"] = current_version_str
        new_version_str = self._version_config.serialize(new_version)
        context["new_version"] = new_version_str

        yaml_path = YAMLPath(self.xpath)
        for node in processor.get_nodes(yaml_path, mustexist=True):
            if node.node == current_version_str:
                processor.set_value(node.path, new_version_str)

        file_content_after = self.__dump(processor.data)

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredYAMLFile:{self.filename}>"
