import argparse
import io
import logging
import os
import re
from configparser import NoOptionError, RawConfigParser
from typing import Dict, List, Tuple, Type

from bumpsemver.exceptions import FileTypeMismatchError, InvalidConfigSectionError
from bumpsemver.files.base import FileTypeBase
from bumpsemver.files.json import ConfiguredJSONFile
from bumpsemver.files.text import ConfiguredPlainTextFile
from bumpsemver.files.toml import ConfiguredTOMLFile
from bumpsemver.files.yaml import ConfiguredYAMLFile
from bumpsemver.version_part import VersionConfig

logger = logging.getLogger(__name__)

# detect either:
# bumpsemver:toml:value
# bumpsemver:toml(suffix):value
# bumpsemver:toml ( suffix with spaces):value
RE_CONFIG_SECTION = re.compile(
    r"^bumpsemver:((?P<file_type>.+?)(\s*\(\s*(?P<file_suffix>[^):]+)\)?)?):(?P<value>.+)",
)


class SectionConfig:
    def __init__(self, handler: Type[FileTypeBase], xpath_supported: bool, props: Dict[str, str]):
        self.handler = handler
        self.xpath_supported = xpath_supported
        self.props = props


file_types_config = {
    "plaintext": SectionConfig(
        ConfiguredPlainTextFile,
        False,
        {"search": "{current_version}", "replace": "{new_version}"},
    ),
    "file": SectionConfig(
        ConfiguredPlainTextFile,
        False,
        {"search": "{current_version}", "replace": "{new_version}"},
    ),
    "json": SectionConfig(ConfiguredJSONFile, True, {"jsonpath": "version"}),
    "yaml": SectionConfig(ConfiguredYAMLFile, True, {"yamlpath": "version"}),
    "toml": SectionConfig(ConfiguredTOMLFile, True, {"tomlpath": "version"}),
}


def _determine_config_file(explicit_config):
    if explicit_config:
        return explicit_config
    return ".bumpsemver.cfg"


def _config_file_exists(config_file: str, explicit_config: bool) -> bool:
    config_file_exists = os.path.exists(config_file)
    if not config_file_exists:
        message = f"Could not read config file at {config_file}"
        if explicit_config:
            raise argparse.ArgumentTypeError(message)
        logger.info(message)
        return False
    return True


def _check_section_config(section: str, acceptable_keys: List[str], actual_config: List[str]):
    unknown_keys = [item for item in actual_config if item not in acceptable_keys]
    if unknown_keys:
        raise InvalidConfigSectionError(f"Invalid config file. Unknown keys {unknown_keys} in section '{section}'")


def _parse_sections(config: RawConfigParser, defaults, sections) -> Tuple[List[FileTypeBase], List[str]]:
    files: List[FileTypeBase] = []
    ignored_for_discovery: List[str] = []

    for section_name in sections:
        if section_name == "bumpsemver:discovery":
            discovery_props = dict(config.items(section_name))
            _check_section_config(section_name, ["ignore"], [*config[section_name]])
            if "ignore" not in discovery_props:
                discovery_props["ignore"] = ""
            ignored_for_discovery = [
                item for item in (line.strip() for line in discovery_props["ignore"].split("\n")) if item
            ]
            continue

        parsed_section_header = RE_CONFIG_SECTION.match(section_name)

        if not parsed_section_header:
            continue

        section_type = parsed_section_header.groupdict()
        file_type = section_type.get("file_type")
        filename = section_type.get("value")
        section_props = dict(config.items(section_name))

        if not [x for x in file_types_config.keys() if x == file_type]:
            raise InvalidConfigSectionError(
                f"Invalid config file. Unknown file type '{file_type}' in section '{section_name}'"
            )

        type_info = file_types_config.get(file_type)

        _check_section_config(section_name, list(type_info.props.keys()), [*section_props])
        if file_type == "file" or file_type == "plaintext":
            _, ext = os.path.splitext(filename)
            ext = ext.lstrip(".").lower()
            if ext in ["json", "toml", "yaml", "yml"]:
                raise FileTypeMismatchError(file_type, ext if ext != "yml" else "yaml", filename)

        if file_type == "file":
            logger.warning("File type 'file' is deprecated, please use 'plaintext' instead.")

        for k, v in type_info.props.items():
            if k not in section_props:
                section_props[k] = defaults.get(k, v)

        if type_info.xpath_supported:
            path_key = next(iter(type_info.props.keys()))
            path = section_props.pop(path_key, None)
            files.append(type_info.handler(filename, VersionConfig(**section_props), file_type, path))
        else:
            files.append(type_info.handler(filename, VersionConfig(**section_props)))

    return files, ignored_for_discovery


def _load_configuration(config_file, explicit_config, defaults):
    # noinspection PyTypeChecker
    config = RawConfigParser("")
    # don't transform keys to lowercase (which would be the default)
    config.optionxform = lambda option: option
    config.add_section("bumpsemver")

    if not _config_file_exists(config_file, explicit_config):
        return config, False, None, [], []

    logger.info(f"Reading config file {config_file}:")

    with open(config_file, "rt", encoding="utf-8") as config_fp:
        config_content = config_fp.read()
        config_newlines = config_fp.newlines

    logger.info(config_content)
    config.read_string(config_content)
    log_config = io.StringIO()
    config.write(log_config)

    if config.has_option("bumpsemver", "files"):
        logger.warning("'files =' configuration will be deprecated, please use [bumpsemver:file:...]")

    defaults.update(dict(config.items("bumpsemver")))

    for bool_value_name in ("commit", "tag", "dry_run"):
        try:
            defaults[bool_value_name] = config.getboolean("bumpsemver", bool_value_name)
        except NoOptionError:
            pass  # no default value then

    files, ignored_for_discovery = _parse_sections(config, defaults, config.sections())

    return config, True, config_newlines, files, ignored_for_discovery


def _update_config_file(config, config_file, config_newlines, config_file_exists, new_version, dry_run):
    config.set("bumpsemver", "current_version", new_version)
    config.remove_option("bumpsemver", "new_version")
    new_config = io.StringIO()
    try:
        write_to_config_file = (not dry_run) and config_file_exists

        logger.info(f"{'Would write' if not write_to_config_file else 'Writing'} to config file {config_file}:")

        config.write(new_config)
        logger.info(new_config.getvalue())

        if write_to_config_file:
            with open(config_file, "wt", encoding="utf-8", newline=config_newlines) as config_fp:
                config_fp.write(new_config.getvalue().strip() + "\n")

    except UnicodeEncodeError:
        logger.warning(
            "Unable to write UTF-8 to config file, because of an old configparser version. "
            "Update with `pip install --upgrade configparser`."
        )
