import logging
import os
import subprocess
from configparser import RawConfigParser
from functools import partial
from shlex import split as shlex_split
from textwrap import dedent

import pytest
from testfixtures import LogCapture

# noinspection PyProtectedMember
from bumpsemver.cli import (
    DESCRIPTION,
    _parse_arguments_phase_1,
    _setup_logging,
    main,
    split_args_in_optional_and_positional,
)

check_output = partial(subprocess.check_output, env=os.environ.copy())

COMMIT = """
[bumpsemver]
commit = True
[bumpsemver:file:VERSION]
""".strip()

COMMIT_NOT_TAG = """
[bumpsemver]
commit = True
tag = False
[bumpsemver:file:VERSION]
""".strip()

RawConfigParser(empty_lines_in_values=False)


def _mock_calls_to_string(called_mock):
    return [
        f"{name}|{args[0] if len(args) > 0 else args}|{repr(kwargs) if len(kwargs) > 0 else ''}"
        for name, args, kwargs in called_mock.mock_calls
    ]


EXPECTED_OPTIONS = """
[-h]
[--config-file FILE]
[--verbose]
[--allow-dirty]
[-v]
[--current-version VERSION]
[--dry-run]
--new-version VERSION
[--commit | --no-commit]
[--tag | --no-tag]
[--sign-tags | --no-sign-tags]
[--tag-name TAG_NAME]
[--tag-message TAG_MESSAGE]
[--message COMMIT_MSG]
{major,minor,patch}
""".strip().splitlines()

EXPECTED_USAGE = (
    """

%s

positional arguments:
  {major,minor,patch}   Part of the version to be bumped

options:
  -h, --help            show this help message and exit
  --config-file FILE    Config file to read most of the variables from
                        (default: .bumpsemver.cfg)
  --verbose             Print verbose logging, use it twice for debug level
                        (default: 0)
  --allow-dirty         Don't abort if working directory is dirty (default:
                        False)
  -v, --version         Print version and exit
  --current-version VERSION
                        Version that needs to be updated (default: None)
  --dry-run             Don't write any files, just pretend. (default: False)
  --new-version VERSION
                        New version that should be in the files (default:
                        None)
  --commit              Commit to version control (default: False)
  --no-commit           Do not commit to version control
  --tag                 Create a tag in version control (default: False)
  --no-tag              Do not create a tag in version control
  --sign-tags           Sign tags if created (default: False)
  --no-sign-tags        Do not sign tags if created
  --tag-name TAG_NAME   Tag name (only works with --tag) (default:
                        v{new_version})
  --tag-message TAG_MESSAGE
                        Tag message (default: build(repo): bumped version
                        {current_version} → {new_version})
  --message COMMIT_MSG  Commit message (default: build(repo): bumped version
                        {current_version} → {new_version})
"""
    % DESCRIPTION
).lstrip()


def test_verbosity():
    _args, known_args, _root_parser, _positionals = _parse_arguments_phase_1(["--help"])
    _setup_logging(known_args.verbose)
    assert logging.getLogger("").level == logging.WARNING

    _args, known_args, _root_parser, _positionals = _parse_arguments_phase_1(["--help", "--verbose"])
    _setup_logging(known_args.verbose)
    assert logging.getLogger("").level == logging.INFO

    _args, known_args, _root_parser, _positionals = _parse_arguments_phase_1(["--help", "--verbose", "--verbose"])
    _setup_logging(known_args.verbose)
    assert logging.getLogger("").level == logging.DEBUG

    _args, known_args, _root_parser, _positionals = _parse_arguments_phase_1(
        ["--help", "--verbose", "--verbose", "--verbose"]
    )
    _setup_logging(known_args.verbose)
    assert logging.getLogger("").level == logging.DEBUG


def test_usage_string(tmpdir, capsys):
    tmpdir.chdir()

    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0

    out, err = capsys.readouterr()
    assert err == ""

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, f"Usage string is missing {option_line}"

    assert EXPECTED_USAGE in out


def test_simple_replacement(tmpdir):
    tmpdir.join("VERSION").write("1.2.0")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:VERSION]
            """
        ).strip()
    )
    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(shlex_split("patch --current-version 1.2.0 --new-version 1.2.1"))
    assert "1.2.1" == tmpdir.join("VERSION").read()
    assert exc.value.code == 0


def test_simple_replacement_in_utf8_file(tmpdir):
    tmpdir.join("VERSION").write("Kröt1.3.0".encode(), "wb")
    tmpdir.chdir()
    tmpdir.join("VERSION").read("rb")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:VERSION]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(shlex_split("patch --verbose --current-version 1.3.0 --new-version 1.3.1"))
    out = tmpdir.join("VERSION").read("rb")
    assert "'Kr\\xc3\\xb6t1.3.1'" in repr(out)
    assert exc.value.code == 0


def test_bump_patch(tmpdir):
    tmpdir.join("filePATCHBUMP").write("1.0.0")
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:filePATCHBUMP]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "1.0.0"])

    assert "1.0.1" == tmpdir.join("filePATCHBUMP").read()
    assert exc.value.code == 0


def test_bump_minor(tmpdir):
    tmpdir.join("fileMINORBUMP").write("1.0.0")
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:fileMINORBUMP]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor", "--current-version", "1.0.0"])

    assert "1.1.0" == tmpdir.join("fileMINORBUMP").read()
    assert exc.value.code == 0


def test_bump_major(tmpdir):
    tmpdir.join("fileMAJORBUMP").write("4.2.8")
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:fileMAJORBUMP]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["--current-version", "4.2.8", "major"])

    assert "5.0.0" == tmpdir.join("fileMAJORBUMP").read()
    assert exc.value.code == 0


def test_bump_wrong_part(tmpdir):
    tmpdir.join("fileWRONGBUMP").write("4.5.8")
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:fileWRONGBUMP]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["--current-version", "4.5.8", "release", "-v"])

    assert "4.5.8" == tmpdir.join("fileWRONGBUMP").read()
    assert exc.value.code == 0


def test_non_vcs_operations_if_vcs_is_not_installed(tmpdir, monkeypatch):
    monkeypatch.setenv("PATH", "")

    tmpdir.chdir()
    tmpdir.join("VERSION").write("31.0.3")

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:file:VERSION]
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["major", "--current-version", "31.0.3"])

    assert "32.0.0" == tmpdir.join("VERSION").read()
    assert exc.value.code == 0


def test_log_parse_doesnt_parse_current_version(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            """
        ).strip()
    )
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["--verbose", "--current-version", "12", "--new-version", "13", "patch"])

    log_capture.check_present(
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '12' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        (
            "bumpsemver.version_part",
            "WARNING",
            (
                "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' "
                "does not parse current version '12'"
            ),
        ),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '13' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        (
            "bumpsemver.version_part",
            "WARNING",
            (
                "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' "
                "does not parse current version '13'"
            ),
        ),
        ("bumpsemver.cli", "INFO", "New version will be '13'"),
        ("bumpsemver.git", "WARNING", "'git ls-files' failed. Listing files without respecting '.gitignore'"),
        ("bumpsemver.cli", "INFO", "Asserting files  contain the version string..."),
        ("bumpsemver.config", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.config", "INFO", "[bumpsemver]\ncurrent_version = 13\n\n"),
    )
    assert exc.value.code == 0


def test_complex_info_logging(tmpdir):
    tmpdir.join("fileE").write("0.4.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.4.0

            [bumpsemver:file:fileE]
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.config", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.config", "INFO", "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:file:fileE]"),
        ("bumpsemver.config", "WARNING", "File type 'file' is deprecated, please use 'plaintext' instead."),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=4, patch=1"),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.4.1'"),
        ("bumpsemver.git", "WARNING", "'git ls-files' failed. Listing files without respecting '.gitignore'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileE contain the version string..."),
        ("bumpsemver.files.text", "INFO", "Found '0.4.0' in fileE at line 0: 0.4.0"),
        ("bumpsemver.files.text", "INFO", "Changing plaintext file fileE:"),
        ("bumpsemver.files.text", "INFO", "--- a/fileE\n+++ b/fileE\n@@ -1 +1 @@\n-0.4.0\n+0.4.1"),
        ("bumpsemver.config", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.config", "INFO", "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:file:fileE]\n\n"),
    )
    assert exc.value.code == 0


def test_complex_info_logging_plaintext(tmpdir):
    tmpdir.join("fileM").write("0.4.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.4.0
            [bumpsemver:plaintext:fileM]
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.config", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.config", "INFO", "[bumpsemver]\ncurrent_version = 0.4.0\n[bumpsemver:plaintext:fileM]"),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=4, patch=1"),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.4.1'"),
        ("bumpsemver.git", "WARNING", "'git ls-files' failed. Listing files without respecting '.gitignore'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileM contain the version string..."),
        ("bumpsemver.files.text", "INFO", "Found '0.4.0' in fileM at line 0: 0.4.0"),
        ("bumpsemver.files.text", "INFO", "Changing plaintext file fileM:"),
        ("bumpsemver.files.text", "INFO", "--- a/fileM\n+++ b/fileM\n@@ -1 +1 @@\n-0.4.0\n+0.4.1"),
        ("bumpsemver.config", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.config", "INFO", "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:plaintext:fileM]\n\n"),
    )
    assert exc.value.code == 0


def test_cli_does_not_support_file(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileA").write("1.2.3")

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["--current-version", "1.2.3", "patch", "fileA"])

    assert exc.value.code == 2


class TestSplitArgsInOptionalAndPositional:

    def test_all_optional(self):
        params = ["--allow-dirty", "--verbose", "--dry-run", "--tag-name", '"Tag"']
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == []
        assert optional == params

    def test_all_positional(self):
        params = ["minor", "setup.py"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == params
        assert optional == []

    def test_no_args(self):
        assert split_args_in_optional_and_positional([]) == ([], [])

    def test_1optional_2positional(self):
        params = ["--dry-run", "major", "setup.py"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == ["major", "setup.py"]
        assert optional == ["--dry-run"]

    def test_2optional_1positional(self):
        params = ["--dry-run", "--message", '"Commit"', "major"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == ["major"]
        assert optional == ["--dry-run", "--message", '"Commit"']

    def test_2optional_mixed_2positional(self):
        params = ["--allow-dirty", "--message", '"Commit"', "minor", "setup.py"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == ["minor", "setup.py"]
        assert optional == ["--allow-dirty", "--message", '"Commit"']


def test_defaults_in_usage_with_config(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("my_defaults.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 18
            new_version = 19
            [bumpsemver:plaintext:file1]
            [bumpsemver:plaintext:file2]
            [bumpsemver:plaintext:file3]
            """
        ).strip()
    )
    with pytest.raises(SystemExit):
        main(["--config-file", "my_defaults.cfg", "--help"])

    out, err = capsys.readouterr()

    assert "Version that needs to be updated (default: 18)" in out
    assert "New version that should be in the files (default: 19)" in out
    assert "[--current-version VERSION]" in out
    assert "[--new-version VERSION]" in out


def test_config_file_explicit(tmpdir):
    tmpdir.join("file1").write("0.9.34")
    tmpdir.join("my_bump_config.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.9.34
            new_version = 0.9.35
            [bumpsemver:plaintext:file1]
            """
        ).strip()
    )

    tmpdir.chdir()

    with pytest.raises(SystemExit) as exc:
        main(shlex_split("patch --config-file my_bump_config.cfg"))

    assert "0.9.35" == tmpdir.join("file1").read()
    assert exc.value.code == 0


def test_config_file_explicit_missing(tmpdir):
    tmpdir.chdir()
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["--config-file", "missing.cfg"])
    assert exc.value.code == 1
    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Could not read config file at missing.cfg",
        )
    )


def test_config_file_explicit_precedence(tmpdir):
    tmpdir.join("file1").write("0.10.34")
    tmpdir.join("my_bump_config.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.10.34
            new_version = 0.10.35
            [bumpsemver:plaintext:file1]
            """
        ).strip()
    )
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.10.34
            new_version = 0.10.35
            [bumpsemver:plaintext:file1]
            """
        ).strip()
    )

    tmpdir.chdir()

    with pytest.raises(SystemExit) as exc:
        main(shlex_split("patch --config-file my_bump_config.cfg"))

    assert "0.10.35" == tmpdir.join("file1").read()
    assert exc.value.code == 0
    assert (
        tmpdir.join(".bumpsemver.cfg").read()
        == dedent(
            """
        [bumpsemver]
        current_version = 0.10.34
        new_version = 0.10.35
        [bumpsemver:plaintext:file1]
        """
        ).strip()
    )
    assert (
        tmpdir.join("my_bump_config.cfg").read()
        == dedent(
            """
        [bumpsemver]
        current_version = 0.10.35

        [bumpsemver:plaintext:file1]
        """
        ).strip()
        + "\n"
    )


def test_config_file_default(tmpdir):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.10.2
            new_version = 0.10.3
            [bumpsemver:plaintext:file2]
            """
        ).strip()
    )

    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "0.10.3" == tmpdir.join("file2").read()
    assert exc.value.code == 0


def test_config_file_both_missing(tmpdir):
    tmpdir.chdir()

    tmpdir.join("a_file.txt").write("1.0.0")

    with LogCapture(level=logging.INFO) as log_capture, pytest.raises(SystemExit) as exc:
        main(["--verbose", "--verbose", "--current-version", "1.0.0", "patch"])

    log_capture.check_present(
        ("bumpsemver.config", "INFO", "Could not read config file at .bumpsemver.cfg"),
        ("bumpsemver.cli", "ERROR", "No valid config file is specified and the default .bumpsemver.cfg is not found"),
        order_matters=True,
    )
    assert exc.value.code == 1


def test_section_config_unknown_type(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file131").write("131.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 131.10.2
            new_version = 131.10.4
            [bumpsemver:foobar:file131]
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Invalid config file. Unknown file type 'foobar' in section 'bumpsemver:foobar:file131'",
        ),
        order_matters=True,
    )
    assert "131.10.2" == tmpdir.join("file131").read()
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        {
            "config": (
                """
                [bumpsemver]
                current_version = 131.10.2
                new_version = 131.10.4
                [bumpsemver:file:file132]
                jsonpath = "version"
                tomlpath = "version"
                """
            ),
            "error": "Invalid config file. Unknown keys ['jsonpath', 'tomlpath'] in section 'bumpsemver:file:file132'",
        },
        {
            "config": (
                """
                [bumpsemver]
                current_version = 131.10.2
                new_version = 131.10.4
                [bumpsemver:plaintext:file132]
                jsonpath = "version"
                """
            ),
            "error": "Invalid config file. Unknown keys ['jsonpath'] in section 'bumpsemver:plaintext:file132'",
        },
        {
            "config": (
                """
                [bumpsemver]
                current_version = 131.10.2
                new_version = 131.10.4
                [bumpsemver:json:file132]
                tomlpath = "version"
                """
            ),
            "error": "Invalid config file. Unknown keys ['tomlpath'] in section 'bumpsemver:json:file132'",
        },
        {
            "config": (
                """
                [bumpsemver]
                current_version = 131.10.2
                new_version = 131.10.4
                [bumpsemver:yaml:file132]
                tomlpath = "version"
                """
            ),
            "error": "Invalid config file. Unknown keys ['tomlpath'] in section 'bumpsemver:yaml:file132'",
        },
        {
            "config": (
                """
                [bumpsemver]
                current_version = 131.10.2
                new_version = 131.10.4
                [bumpsemver:toml:file132]
                jsonpath = "version"
                """
            ),
            "error": "Invalid config file. Unknown keys ['jsonpath'] in section 'bumpsemver:toml:file132'",
        },
    ]
)
def invalid_section_args(request):
    return request.param


def test_section_config_unknown_arguments(tmpdir, invalid_section_args):
    tmpdir.chdir()
    tmpdir.join("file132").write("131.10.2")
    print(invalid_section_args)
    tmpdir.join(".bumpsemver.cfg").write(dedent(invalid_section_args["config"]).strip())

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            invalid_section_args["error"],
        ),
        order_matters=True,
    )
    assert "131.10.2" == tmpdir.join("file132").read()
    assert exc.value.code == 4
