import io
import json
import logging
from datetime import datetime
from typing import Dict, Union

from jsonpath_ng import parse
from jsonpath_ng.lexer import JsonPathLexerError

from bumpsemver.exceptions import (
    InvalidFileError,
    MultiValuesMismatchError,
    PathNotFoundError,
    SingleValueMismatchError,
)
from bumpsemver.files.base import FileTypeBase
from bumpsemver.version_part import Version, VersionConfig

logger = logging.getLogger(__name__)


def _get_json_value(obj, path):
    json_path_expr = parse(path)
    return [item.value for item in json_path_expr.find(obj)]


def _set_json_value(obj, path, value):
    json_path_expr = parse(path)
    json_path_expr.update(obj, value)


class ConfiguredJSONFile(FileTypeBase):
    def __init__(self, filename: str, version_config: VersionConfig, file_type="json", jsonpath: str = None):
        super().__init__(filename, version_config, file_type, jsonpath, logger)

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version)
        context["current_version"] = current_version

        if self.contains(current_version):
            return

    def contains(self, search: str) -> bool:
        try:
            with io.open(self.filename, "rt", encoding="utf-8") as orig_fp:
                data = json.load(orig_fp)
            nodes = _get_json_value(data, self.xpath)
            if (len(nodes) == 1 and nodes[0] != search) or len(nodes) == 0:
                raise SingleValueMismatchError(self.xpath, "json", self.filename, nodes[0], search)
            else:
                for node in nodes:
                    if node != search:
                        raise MultiValuesMismatchError(self.xpath, "json", self.filename, nodes, search)
            return True
        except (JsonPathLexerError, LookupError) as exc:
            raise PathNotFoundError(self.xpath, "json", self.filename) from exc
        except json.JSONDecodeError as exc:
            raise InvalidFileError(self.filename, "json") from exc

    def replace(
        self, current_version: Version, new_version: Version, context: Dict[str, Union[str, datetime]], dry_run: bool
    ) -> None:
        with io.open(self.filename, "rt", encoding="utf-8") as orig_fp:
            file_content_before = orig_fp.read()
            # the object_pairs_hook allows us to load the json in a way that key order
            # is preserved and will keep the file diff to a minimum
            #
            data = json.loads(file_content_before)

        current_version_str = self._version_config.serialize(current_version)
        context["current_version"] = current_version_str
        new_version_str = self._version_config.serialize(new_version)
        context["new_version"] = new_version_str

        _set_json_value(data, self.xpath, new_version_str)
        # ensure_ascii: we're writing utf-8 files, so we don't need ascii support
        # allow_nan: JSON does not have an understanding of infinity or nan, so it is forbidden
        # indent: indent of 2 spaces is common practise
        # separators: the default separators leave a trailing space after every comma. when using indentation,
        #             this results in awkward line-endings with a leading space
        file_content_after = (
            json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, separators=(",", ": ")) + "\n"
        )

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredJSONFile:{self.filename}>"
