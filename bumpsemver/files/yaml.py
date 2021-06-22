import logging
from types import SimpleNamespace

from ruamel.yaml.compat import StringIO
from yamlpath import Processor, YAMLPath
from yamlpath.common import Parsers
from yamlpath.exceptions import YAMLPathException
from yamlpath.wrappers import ConsolePrinter

from bumpsemver.exceptions import BumpVersionException, VersionNotFoundException
from bumpsemver.files import FileTypes
from bumpsemver.files.base import FileTypeBase
from bumpsemver.version_part import Version

logger = logging.getLogger(__name__)


class InvalidYAMLException(BumpVersionException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ConfiguredYAMLFile(FileTypeBase):
    def __init__(self, path, yamlpath, version_config):
        super().__init__(path, version_config, FileTypes.YAML, logger)
        self.yaml = Parsers.get_yaml_editor()
        self.yaml_path = yamlpath
        self.yaml_logging_args = SimpleNamespace(quiet=True, verbose=False, debug=False)
        self.yaml_log = ConsolePrinter(self.yaml_logging_args)

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version, context)
        context["current_version"] = current_version

        if self.contains(current_version):
            return

        # version not found
        raise VersionNotFoundException(f"Did not find '{current_version}' at yamlpath '{self.yaml_path}' in file: '{self.path}'")

    def contains(self, search: str) -> bool:
        try:
            processor = self.__get_processor()
            yaml_path = YAMLPath(self.yaml_path)
            nodes_found = list(processor.get_nodes(yaml_path, mustexist=True))
            matched = True
            for node in nodes_found:
                if node.node != search:
                    matched = False
            return matched
        except YAMLPathException as ex:
            logger.error(f"invalid path expression: {str(ex)}", exc_info=ex)
            return False

    def __dump(self, data) -> str:
        stream = StringIO()
        self.yaml.dump(data, stream)
        return stream.getvalue()

    def __get_processor(self):
        (yaml_data, doc_loaded) = Parsers.get_yaml_data(self.yaml, self.yaml_log, self.path)
        if not doc_loaded:
            raise InvalidYAMLException(f"Failed in reading YAML file '{self.path}'")
        processor = Processor(self.yaml_log, yaml_data)
        return processor

    def replace(self, current_version: Version, new_version: Version, context: dict, dry_run: bool) -> None:
        processor = self.__get_processor()
        file_content_before = self.__dump(processor.data)

        current_version = self._version_config.serialize(current_version, context)
        context["current_version"] = current_version
        new_version = self._version_config.serialize(new_version, context)
        context["new_version"] = new_version

        yaml_path = YAMLPath(self.yaml_path)
        for node in processor.get_nodes(yaml_path, mustexist=True):
            if node.node == current_version:
                processor.set_value(node.path, new_version)

        file_content_after = self.__dump(processor.data)

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.ConfiguredYAMLFile:{self.path}>"
