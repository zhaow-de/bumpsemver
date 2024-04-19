import argparse
import io
import logging
import os
import re
import sre_constants
import subprocess
import sys
from configparser import NoOptionError, RawConfigParser
from datetime import datetime
from typing import Dict, List, Tuple, Type

from bumpsemver import __title__, __version__
from bumpsemver.exceptions import (
    CannotParseVersionError,
    InvalidConfigSectionError,
    InvalidFileError,
    MixedNewLineError,
    MultiValuesMismatchError,
    PathNotFoundError,
    SingleValueMismatchError,
    VersionNotFoundError,
    WorkingDirectoryIsDirtyError,
)
from bumpsemver.files.base import FileTypeBase
from bumpsemver.files.json import ConfiguredJSONFile
from bumpsemver.files.text import ConfiguredPlainTextFile
from bumpsemver.files.toml import ConfiguredTOMLFile
from bumpsemver.files.yaml import ConfiguredYAMLFile
from bumpsemver.git import Git
from bumpsemver.utils import key_value_string
from bumpsemver.version_part import VersionConfig

python_version = sys.version.split("\n")[0].split(" ")[0]
DESCRIPTION = f"{__title__}: v{__version__} (using Python v{python_version})"

# detect either:
# bumpsemver:toml:value
# bumpsemver:toml(suffix):value
# bumpsemver:toml ( suffix with spaces):value
RE_CONFIG_SECTION = re.compile(
    r"^bumpsemver:((?P<file_type>.+?)(\s*\(\s*(?P<file_suffix>[^):]+)\)?)?):(?P<value>.+)",
)

logger = logging.getLogger(__name__)
time_context = {"now": datetime.now(), "utcnow": datetime.utcnow()}

OPTIONAL_ARGUMENTS_THAT_TAKE_VALUES = [
    "--config-file",
    "--current-version",
    "--message",
    "--new-version",
    "--search",
    "--replace",
    "--tag-name",
    "--tag-message",
]


class SectionConfig:
    def __init__(self, handler: Type[FileTypeBase], xpath_supported: bool, props: Dict[str, str]):
        self.handler = handler
        self.xpath_supported = xpath_supported
        self.props = props


def main(original_args=None) -> None:
    try:
        #
        # determine configuration based on command-line arguments and on-disk configuration files
        args, known_args, root_parser, positionals = _parse_arguments_phase_1(original_args)
        _setup_logging(known_args.verbose)
        vcs_info = _determine_vcs_usability()
        defaults = _determine_current_version(vcs_info)
        explicit_config = None
        if hasattr(known_args, "config_file"):
            explicit_config = known_args.config_file
        config_file = _determine_config_file(explicit_config)
        config, config_file_exists, config_newlines, files = _load_configuration(config_file, explicit_config, defaults)
        known_args, parser2, remaining_argv = _parse_arguments_phase_2(args, defaults, root_parser)
        version_config = _setup_version_config(known_args)
        current_version = version_config.parse(known_args.current_version)
        context = {**time_context, **vcs_info}
        #
        # calculate the desired new version
        new_version = _assemble_new_version(
            current_version, defaults, known_args.current_version, positionals, version_config
        )
        args, file_names = _parse_arguments_phase_3(remaining_argv, positionals, defaults, parser2)
        new_version = _parse_new_version(args, new_version, version_config)

        # replace the version in target files
        vcs = _determine_vcs_dirty(defaults)
        files.extend(
            ConfiguredPlainTextFile(file_name, version_config) for file_name in (file_names or positionals[1:])
        )
        _check_files_contain_version(files, current_version, context)
        _replace_version_in_files(files, current_version, new_version, args.dry_run, context)
        config.remove_option("bumpsemver", "new_version")

        # store the new version
        _update_config_file(config, config_file, config_newlines, config_file_exists, args.new_version, args.dry_run)

        # commit and tag
        if vcs:
            context = _commit_to_vcs(files, config_file, config_file_exists, vcs, args, current_version, new_version)
            _tag_in_vcs(vcs, context, args)

        sys.exit(0)
    except argparse.ArgumentTypeError as exc:
        logger.error(f"{''.join(exc.args)}")
        sys.exit(1)
    except FileNotFoundError as exc:
        logger.error(f"FileNotFound. {exc!s}")
        sys.exit(2)
    except MixedNewLineError as exc:
        logger.warning(f"{exc.message}")
        sys.exit(3)
    except (
        CannotParseVersionError,
        InvalidConfigSectionError,
        InvalidFileError,
        MultiValuesMismatchError,
        PathNotFoundError,
        SingleValueMismatchError,
        VersionNotFoundError,
    ) as exc:
        logger.error(f"{exc.message}")
        sys.exit(4)
    except WorkingDirectoryIsDirtyError as exc:
        logger.error(f"{exc.message}\n\nUse --allow-dirty to override this if you know what you're doing.")
        sys.exit(5)
    except subprocess.CalledProcessError:
        sys.exit(10)
    except Exception as exc:
        logger.error(f"Unexpected error occurred: {exc!s}")
        sys.exit(128)


def split_args_in_optional_and_positional(args):
    # manually parsing positional arguments because with argparse we cannot mix positional and optional arguments

    positions = []
    for i, arg in enumerate(args):

        previous = None

        if i > 0:
            previous = args[i - 1]

        if (not arg.startswith("-")) and (previous not in OPTIONAL_ARGUMENTS_THAT_TAKE_VALUES):
            positions.append(i)

    positionals = [arg for i, arg in enumerate(args) if i in positions]
    args = [arg for i, arg in enumerate(args) if i not in positions]

    return positionals, args


def _parse_arguments_phase_1(original_args):
    positionals, args = split_args_in_optional_and_positional(sys.argv[1:] if original_args is None else original_args)
    if len(positionals[1:]) > 2:
        logger.warning(
            "Giving multiple files on the command line will be deprecated, "
            "please use [bumpsemver:plaintext:...] in a config file."
        )
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument(
        "--config-file",
        metavar="FILE",
        default=argparse.SUPPRESS,
        required=False,
        help="Config file to read most of the variables from (default: .bumpsemver.cfg)",
    )
    root_parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Print verbose logging to stderr",
        required=False,
    )
    root_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        default=False,
        help="Don't abort if working directory is dirty",
        required=False,
    )
    known_args, _ = root_parser.parse_known_args(args)
    return args, known_args, root_parser, positionals


def _setup_logging(verbose: int) -> None:
    try:
        log_level = [logging.WARNING, logging.INFO, logging.DEBUG][verbose]
    except IndexError:
        log_level = logging.DEBUG
    logging.basicConfig(format="%(levelname)s:%(message)s")
    root_logger = logging.getLogger("")
    root_logger.setLevel(log_level)
    logger.debug(f"Starting {DESCRIPTION}")


def _determine_vcs_usability():
    vcs_info = {}
    if Git.is_usable():
        vcs_info.update(Git.latest_tag_info())
    return vcs_info


def _determine_current_version(vcs_info):
    defaults = {}
    if "current_version" in vcs_info:
        defaults["current_version"] = vcs_info["current_version"]
    return defaults


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


def _parse_sections(config: RawConfigParser, defaults, sections):
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

    files: List[FileTypeBase] = []

    for section_name in sections:
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
        if file_type == "file":
            logger.warning("Using 'file' section type is deprecated, please use 'plaintext' instead.")

        for k, v in type_info.props.items():
            if k not in section_props:
                section_props[k] = defaults.get(k, v)

        if type_info.xpath_supported:
            path_key = next(iter(type_info.props.keys()))
            path = section_props.pop(path_key, None)
            files.append(type_info.handler(filename, VersionConfig(**section_props), file_type, path))
        else:
            files.append(type_info.handler(filename, VersionConfig(**section_props)))

    return files


def _load_configuration(config_file, explicit_config, defaults):
    # noinspection PyTypeChecker
    config = RawConfigParser("")
    # don't transform keys to lowercase (which would be the default)
    config.optionxform = lambda option: option
    config.add_section("bumpsemver")

    if not _config_file_exists(config_file, explicit_config):
        return config, False, None, []

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

    files = _parse_sections(config, defaults, config.sections())

    return config, True, config_newlines, files


def _parse_arguments_phase_2(args, defaults, root_parser):
    parser2 = argparse.ArgumentParser(prog="bumpsemver", add_help=False, parents=[root_parser])
    parser2.set_defaults(**defaults)
    parser2.add_argument(
        "--current-version",
        metavar="VERSION",
        help="Version that needs to be updated",
        required=False,
    )
    parser2.add_argument(
        "--search",
        metavar="SEARCH",
        help="Template for complete string to search",
        default=defaults.get("search", "{current_version}"),
    )
    parser2.add_argument(
        "--replace",
        metavar="REPLACE",
        help="Template for complete string to replace",
        default=defaults.get("replace", "{new_version}"),
    )
    known_args, remaining_argv = parser2.parse_known_args(args)

    defaults.update(vars(known_args))

    return known_args, parser2, remaining_argv


def _setup_version_config(known_args):
    try:
        version_config = VersionConfig(search=known_args.search, replace=known_args.replace)
    except sre_constants.error:
        sys.exit(1)
    return version_config


def _assemble_new_version(current_version, defaults, arg_current_version, positionals, version_config):
    new_version = None
    if "new_version" not in defaults and arg_current_version:
        try:
            if current_version and positionals:
                logger.info(f"Attempting to increment part '{positionals[0]}'")
                new_version = current_version.bump(positionals[0], version_config.order())
                logger.info(f"Values are now: {key_value_string(new_version.values)}")
                defaults["new_version"] = version_config.serialize(new_version)
        except KeyError:
            logger.info("Opportunistic finding of new_version failed")
    return new_version


def _parse_arguments_phase_3(remaining_argv, positionals, defaults, parser2):
    parser3 = argparse.ArgumentParser(
        prog="bumpsemver",
        description=DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        conflict_handler="resolve",
        parents=[parser2],
    )
    parser3.set_defaults(**defaults)
    parser3.add_argument(
        "--current-version",
        metavar="VERSION",
        help="Version that needs to be updated",
        required="current_version" not in defaults,
    )
    parser3.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Don't write any files, just pretend.",
    )
    parser3.add_argument(
        "--new-version",
        metavar="VERSION",
        help="New version that should be in the files",
        required="new_version" not in defaults,
    )
    commit_group = parser3.add_mutually_exclusive_group()
    commit_group.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help="Commit to version control",
        default=defaults.get("commit", False),
    )
    commit_group.add_argument(
        "--no-commit",
        action="store_false",
        dest="commit",
        help="Do not commit to version control",
        default=argparse.SUPPRESS,
    )
    tag_group = parser3.add_mutually_exclusive_group()
    tag_group.add_argument(
        "--tag",
        action="store_true",
        dest="tag",
        default=defaults.get("tag", False),
        help="Create a tag in version control",
    )
    tag_group.add_argument(
        "--no-tag",
        action="store_false",
        dest="tag",
        help="Do not create a tag in version control",
        default=argparse.SUPPRESS,
    )
    sign_tags_group = parser3.add_mutually_exclusive_group()
    sign_tags_group.add_argument(
        "--sign-tags",
        action="store_true",
        dest="sign_tags",
        help="Sign tags if created",
        default=defaults.get("sign_tags", False),
    )
    sign_tags_group.add_argument(
        "--no-sign-tags",
        action="store_false",
        dest="sign_tags",
        help="Do not sign tags if created",
        default=argparse.SUPPRESS,
    )
    parser3.add_argument(
        "--tag-name",
        metavar="TAG_NAME",
        help="Tag name (only works with --tag)",
        default=defaults.get("tag_name", "r{new_version}"),
    )
    parser3.add_argument(
        "--tag-message",
        metavar="TAG_MESSAGE",
        dest="tag_message",
        help="Tag message",
        default=defaults.get("tag_message", "build(repo): bumped version {current_version} → {new_version}"),
    )
    parser3.add_argument(
        "--message",
        metavar="COMMIT_MSG",
        help="Commit message",
        default=defaults.get("message", "build(repo): bumped version {current_version} → {new_version}"),
    )
    file_names = []
    if "files" in defaults:
        assert defaults["files"] is not None
        file_names = defaults["files"].split(" ")
    parser3.add_argument("part", help="Part of the version to be bumped.")
    parser3.add_argument("files", metavar="file", nargs="*", help="Files to change", default=file_names)
    args = parser3.parse_args(remaining_argv + positionals)

    if args.dry_run:
        logger.info("Dry run active, won't touch any files.")

    return args, file_names


def _parse_new_version(args, new_version, version_config):
    if args.new_version:
        new_version = version_config.parse(args.new_version)
    logger.info(f"New version will be '{args.new_version}'")
    return new_version


def _determine_vcs_dirty(defaults):
    if not Git.is_usable():
        return None

    try:
        Git.assert_non_dirty()
    except WorkingDirectoryIsDirtyError:
        if defaults["allow_dirty"]:
            return None
        raise

    return Git


def _check_files_contain_version(files, current_version, context: Dict[str, Tuple[str, datetime]]):
    # make sure files exist and contain version string
    logger.info(f"Asserting files {', '.join([str(f) for f in files])} contain the version string...")
    for file_item in files:
        file_item.should_contain_version(current_version, context)


def _replace_version_in_files(files, current_version, new_version, dry_run, context: Dict[str, Tuple[str, datetime]]):
    # change version string in files
    for file_item in files:
        file_item.replace(current_version, new_version, context, dry_run)


def _update_config_file(config, config_file, config_newlines, config_file_exists, new_version, dry_run):
    config.set("bumpsemver", "current_version", new_version)
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


def _commit_to_vcs(files, config_file, config_file_exists, vcs, args, current_version, new_version):
    commit_files = [f.filename for f in files]
    if config_file_exists:
        commit_files.append(config_file)
    assert vcs.is_usable(), f"Did find '{vcs.__name__}' unusable, unable to commit."
    do_commit = args.commit and not args.dry_run
    logger.info(f"{'Would prepare' if not do_commit else 'Preparing'} {vcs.__name__} commit")
    for path in commit_files:
        logger.info(f"{'Would add' if not do_commit else 'Adding'} changes in file '{path}' to {vcs.__name__}")

        if do_commit:
            vcs.add_path(path)

    context = {
        "current_version": args.current_version,
        "new_version": args.new_version,
    }
    context.update(time_context)
    context.update({f"current_{part}": current_version[part].value for part in current_version})
    context.update({f"new_{part}": new_version[part].value for part in new_version})

    commit_message = args.message.format(**context)

    logger.info(
        f"{'Would commit' if not do_commit else 'Committing'} to {vcs.__name__} with message '{commit_message}'"
    )
    if do_commit:
        vcs.commit(message=commit_message, context=context)
    return context


def _tag_in_vcs(vcs, context, args):
    sign_tags = args.sign_tags
    tag_name = args.tag_name.format(**context)
    tag_message = args.tag_message.format(**context)
    do_tag = args.tag and not args.dry_run
    logger.info(
        f"{'Would tag' if not do_tag else 'Tagging'} `{tag_name}` "
        f"{f'with message `{tag_message}`' if tag_message else 'without message'} "
        f"in {vcs.__name__} and {'signing' if sign_tags else 'not signing'}"
    )
    if do_tag:
        vcs.tag(tag_name, sign_tags, tag_message)
