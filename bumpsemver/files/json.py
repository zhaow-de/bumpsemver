import collections
import io
import json
import logging
from json import JSONDecodeError

from jsonpath_ng import parse

from bumpsemver.version_part import Version
from bumpsemver.exceptions import VersionNotFoundException
from bumpsemver.files import FileTypes
from bumpsemver.files.base import FileTypeBase

logger = logging.getLogger(__name__)


def _get_json_value(obj, path):
    json_path_expr = parse(path)
    match = json_path_expr.find(obj)
    return match[0].value


def _set_json_value(obj, path, value):
    json_path_expr = parse(path)
    json_path_expr.find(obj)
    json_path_expr.update(obj, value)


class ConfiguredJSONFile(FileTypeBase):
    def __init__(self, path, jsonpath, version_config):
        super().__init__(path, version_config, FileTypes.JSON, logger)
        self.json_path = jsonpath

    def should_contain_version(self, version: Version, context: dict) -> None:
        current_version = self._version_config.serialize(version, context)
        context["current_version"] = current_version

        if self.contains(current_version):
            return

        # version not found
        raise VersionNotFoundException(f"Did not find '{current_version}' at jsonpath '{self.json_path}' in file: '{self.path}'")

    def contains(self, search: str) -> bool:
        try:
            with io.open(self.path, "rt", encoding="utf-8") as orig_fp:
                data = json.load(orig_fp)
            return _get_json_value(data, self.json_path) == search
        except LookupError as err:
            logger.error(f"invalid path expression: {str(err)}", exc_info=err)
            return False
        except JSONDecodeError as err:
            raise err

    def replace(self, current_version: Version, new_version: Version, context: dict, dry_run: bool) -> None:
        with io.open(self.path, "rt", encoding="utf-8") as orig_fp:
            file_content_before = orig_fp.read()
            # the object_pairs_hook allows us to load the json in a way that key order is preserved and will keep the file diff
            # to a minimum
            #
            # noinspection PyTypeChecker
            data = json.loads(file_content_before, object_pairs_hook=collections.OrderedDict)

        current_version = self._version_config.serialize(current_version, context)
        context["current_version"] = current_version
        new_version = self._version_config.serialize(new_version, context)
        context["new_version"] = new_version

        if _get_json_value(data, self.json_path) == current_version:
            _set_json_value(data, self.json_path, new_version)
        # ensure_ascii: we're writing utf-8 files, so we don't need ascii support
        # allow_nan: JSON does not have an understanding of infinity or nan, so it’s forbidden
        # indent: indent of 2 spaces is common practise
        # separators: the default separators leave a trailing space after every comma. when using indentation, this results in awkward
        #             line-endings with a leading space
        file_content_after = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, separators=(",", ": ")) + "\n"

        self.update_file(file_content_before, file_content_after, dry_run)

    def __repr__(self):
        return f"<bumpsemver.files.ConfiguredJSONFile:{self.path}>"
