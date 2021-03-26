import collections
import io
import json
import logging
import os
from difflib import unified_diff
from json import JSONDecodeError

from jsonpath_ng import parse

from bumpsemver.exceptions import VersionNotFoundException

logger = logging.getLogger(__name__)


def key_value_string(d):
    return ", ".join("{}={}".format(k, v) for k, v in sorted(d.items()))


class ConfiguredFile:

    def __init__(self, path, version_config):
        self.path = path
        self._version_config = version_config

    def should_contain_version(self, version, context):
        """
        Raise VersionNotFound if the version number isn't present in this file.

        Return normally if the version number is in fact present.
        """
        context["current_version"] = self._version_config.serialize(version,
                                                                    context)
        search_expression = self._version_config.search.format(**context)

        if self.contains(search_expression):
            return

        # the `search` pattern did not match, but the original supplied
        # version number (representing the same version part values) might
        # match instead.

        # check whether `search` isn't customized, i.e. should match only
        # very specific parts of the file
        search_pattern_is_default =\
            self._version_config.search == "{current_version}"

        if search_pattern_is_default and self.contains(version.original):
            # original version is present and we're not looking for something
            # more specific -> this is accepted as a match
            return

        # version not found
        raise VersionNotFoundException(
            "Did not find '{}' in file: '{}'".format(
                search_expression, self.path
            )
        )

    def contains(self, search):
        if not search:
            return False

        with open(self.path, "rt", encoding="utf-8") as f:
            search_lines = search.splitlines()
            lookbehind = []

            for lineno, line in enumerate(f.readlines()):
                lookbehind.append(line.rstrip("\n"))

                if len(lookbehind) > len(search_lines):
                    lookbehind = lookbehind[1:]

                if (
                        search_lines[0] in lookbehind[0]
                        and search_lines[-1] in lookbehind[-1]
                        and search_lines[1:-1] == lookbehind[1:-1]
                ):
                    logger.info(
                        "Found '%s' in %s at line %s: %s",
                        search,
                        self.path,
                        lineno - (len(lookbehind) - 1),
                        line.rstrip(),
                    )
                    return True
        return False

    def replace(self, current_version, new_version, context, dry_run):

        with open(self.path, "rt", encoding="utf-8") as f:
            file_content_before = f.read()
            file_new_lines = f.newlines

        context["current_version"] = self._version_config.serialize(
            current_version, context
        )
        context["new_version"] = self._version_config.serialize(new_version,
                                                                context)

        search_for = self._version_config.search.format(**context)
        replace_with = self._version_config.replace.format(**context)

        file_content_after = file_content_before.replace(search_for,
                                                         replace_with)

        if file_content_before == file_content_after:
            file_content_after = file_content_before.replace(
                current_version.original, replace_with
            )

        if file_content_before != file_content_after:
            logger.info("%s file %s:",
                        "Would change" if dry_run else "Changing", self.path)
            logger.info(
                "\n".join(
                    list(
                        unified_diff(
                            file_content_before.splitlines(),
                            file_content_after.splitlines(),
                            lineterm="",
                            fromfile="a/" + self.path,
                            tofile="b/" + self.path,
                        )
                    )
                )
            )
        else:
            logger.info("%s file %s",
                        "Would not change" if dry_run else "Not changing",
                        self.path)

        if not dry_run:
            with open(self.path, "wt", encoding="utf-8",
                      newline=file_new_lines) as f:
                f.write(file_content_after)

    def __str__(self):
        return self.path

    def __repr__(self):
        return "<bumpsemver.ConfiguredFile:{}>".format(self.path)


def _get_json_value(obj, path):
    json_path_expr = parse(path)
    match = json_path_expr.find(obj)
    return match[0].value


def _set_json_value(obj, path, value):
    json_path_expr = parse(path)
    json_path_expr.find(obj)
    json_path_expr.update(obj, value)


class ConfiguredJSONFile(ConfiguredFile):
    def __init__(self, path, version_key, version_config):
        super(ConfiguredJSONFile, self).__init__(path, version_config)
        self.json_path = version_key

    def contains(self, search):
        try:
            with io.open(self.path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
            return _get_json_value(data, self.json_path) == search
        except LookupError as exc:
            logger.error('invalid path expression: {}'.format(str(exc)),
                         exc_info=exc)
            return False
        except JSONDecodeError as e:
            raise e

    def replace(self, current_version, new_version, context, dry_run):
        with io.open(self.path, 'rt', encoding='utf-8') as f:
            file_content_before = f.read()
            # the object_pairs_hook allows us to load the json in a way that
            # key order is preserved and will keep the file diff to a minimum
            data = json.loads(file_content_before,
                              object_pairs_hook=collections.OrderedDict)

        context['current_version'] = self._version_config.serialize(
            current_version, context)
        context['new_version'] = self._version_config.serialize(
            new_version, context)

        search_for = self._version_config.search.format(**context)
        replace_with = self._version_config.replace.format(**context)

        if _get_json_value(data, self.json_path) == search_for:
            _set_json_value(data, self.json_path, replace_with)
        # ensure_ascii: we're writing utf-8 files, so we don't need ascii
        #               support
        # allow_nan: JSON does not have an understanding of infinity or nan,
        #            so it’s forbidden
        # indent: indent of 2 spaces is common practise
        # separators: the default separators leave a trailing space after every
        #             comma. when using indentation, this results in awkward
        #             line-endings with a leading space
        file_content_after = json.dumps(data, ensure_ascii=False,
                                        allow_nan=False, indent=2,
                                        separators=(',', ': ')) + '\n'

        if file_content_before != file_content_after:
            logger.info('{} file {}:'.format(
                'Would change' if dry_run else 'Changing',
                self.path,
            ))
            logger.info(os.linesep.join(list(unified_diff(
                file_content_before.splitlines(),
                file_content_after.splitlines(),
                lineterm='',
                fromfile='a/' + self.path,
                tofile='b/' + self.path
            ))))
        else:
            logger.info('{} file {}'.format(
                'Would not change' if dry_run else 'Not changing',
                self.path,
            ))

        if not dry_run:
            with io.open(self.path, 'wt', encoding='utf-8', newline='\n') as f:
                f.write(file_content_after)

    def __repr__(self):
        return '<bumpsemver.ConfiguredJSONFile:{}>'.format(self.path)
