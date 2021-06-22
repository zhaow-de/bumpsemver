# pylint: skip-file

import argparse
import logging
import os
import subprocess
import warnings
from configparser import RawConfigParser
from datetime import datetime
from functools import partial
from shlex import split as shlex_split
from textwrap import dedent
from unittest import mock

# noinspection PyPackageRequirements
import pytest
# noinspection PyPackageRequirements
from testfixtures import LogCapture

import bumpsemver
from bumpsemver import exceptions
from bumpsemver.cli import DESCRIPTION, main, split_args_in_optional_and_positional

check_output = partial(subprocess.check_output, env=os.environ.copy())

COMMIT = r"""
[bumpsemver]
commit = True
""".strip()

COMMIT_NOT_TAG = r"""
[bumpsemver]
commit = True
tag = False
""".strip()


@pytest.fixture(params=[
    "file",
    "file(suffix)",
    "file (suffix with space)",
    "file (suffix lacking closing paren",
])
def file_keyword(request):
    """Return multiple possible styles for the bumpsemver:file keyword."""
    return request.param


RawConfigParser(empty_lines_in_values=False)


def _mock_calls_to_string(called_mock):
    return [f"{name}|{args[0] if len(args) > 0 else args}|{repr(kwargs) if len(kwargs) > 0 else ''}"
            for name, args, kwargs in called_mock.mock_calls]


EXPECTED_OPTIONS = r"""
[-h]
[--config-file FILE]
[--verbose]
[--allow-dirty]
[--search SEARCH]
[--replace REPLACE]
[--current-version VERSION]
[--dry-run]
--new-version VERSION
[--commit | --no-commit]
[--tag | --no-tag]
[--sign-tags | --no-sign-tags]
[--tag-name TAG_NAME]
[--tag-message TAG_MESSAGE]
[--message COMMIT_MSG]
part
[file ...]
""".strip().splitlines()

EXPECTED_USAGE = (r"""

%s

positional arguments:
  part                  Part of the version to be bumped.
  file                  Files to change (default: [])

optional arguments:
  -h, --help            show this help message and exit
  --config-file FILE    Config file to read most of the variables from
                        (default: .bumpsemver.cfg)
  --verbose             Print verbose logging to stderr (default: 0)
  --allow-dirty         Don't abort if working directory is dirty (default:
                        False)
  --search SEARCH       Template for complete string to search (default:
                        {current_version})
  --replace REPLACE     Template for complete string to replace (default:
                        {new_version})
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
                        r{new_version})
  --tag-message TAG_MESSAGE
                        Tag message (default: [OPS] bumped version:
                        {current_version} → {new_version})
  --message COMMIT_MSG  Commit message (default: [OPS] bumped version:
                        {current_version} → {new_version})
""" % DESCRIPTION).lstrip()


def test_usage_string(tmpdir, capsys):
    tmpdir.chdir()

    with pytest.raises(SystemExit):
        main(["--help"])

    out, err = capsys.readouterr()
    assert err == ""

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, f"Usage string is missing {option_line}"

    assert EXPECTED_USAGE in out


def test_missing_explicit_config_file(tmpdir):
    tmpdir.chdir()
    with pytest.raises(argparse.ArgumentTypeError):
        main(["--config-file", "missing.cfg"])


def test_simple_replacement(tmpdir):
    tmpdir.join("VERSION").write("1.2.0")
    tmpdir.chdir()
    main(shlex_split("patch --current-version 1.2.0 --new-version 1.2.1 VERSION"))
    assert "1.2.1" == tmpdir.join("VERSION").read()


def test_simple_replacement_in_utf8_file(tmpdir):
    tmpdir.join("VERSION").write("Kröt1.3.0".encode(), "wb")
    tmpdir.chdir()
    tmpdir.join("VERSION").read("rb")
    main(shlex_split("patch --verbose --current-version 1.3.0 --new-version 1.3.1 VERSION"))
    out = tmpdir.join("VERSION").read("rb")
    assert "'Kr\\xc3\\xb6t1.3.1'" in repr(out)


def test_bump_version(tmpdir):
    tmpdir.join("file5").write("1.0.0")
    tmpdir.chdir()
    main(["patch", "--current-version", "1.0.0", "file5"])

    assert "1.0.1" == tmpdir.join("file5").read()


def test_bump_major(tmpdir):
    tmpdir.join("fileMAJORBUMP").write("4.2.8")
    tmpdir.chdir()
    main(["--current-version", "4.2.8", "major", "fileMAJORBUMP"])

    assert "5.0.0" == tmpdir.join("fileMAJORBUMP").read()


def test_non_existing_file(tmpdir):
    tmpdir.chdir()
    with pytest.raises(IOError):
        main(shlex_split("patch --current-version 1.2.0 --new-version 1.2.1 does_not_exist.txt"))


def test_non_existing_second_file(tmpdir):
    tmpdir.chdir()
    tmpdir.join("my_source_code.txt").write("1.2.3")
    with pytest.raises(IOError):
        main(shlex_split("patch --current-version 1.2.3 my_source_code.txt does_not_exist2.txt"))

    # first file is unchanged because second didn't exist
    assert "1.2.3" == tmpdir.join("my_source_code.txt").read()


def test_non_vcs_operations_if_vcs_is_not_installed(tmpdir, monkeypatch):
    monkeypatch.setenv("PATH", "")

    tmpdir.chdir()
    tmpdir.join("VERSION").write("31.0.3")

    main(["major", "--current-version", "31.0.3", "VERSION"])

    assert "32.0.0" == tmpdir.join("VERSION").read()


def test_log_no_config_file_info_message(tmpdir):
    tmpdir.chdir()

    tmpdir.join("a_file.txt").write("1.0.0")

    with LogCapture(level=logging.INFO) as log_capture:
        main(["--verbose", "--verbose", "--current-version", "1.0.0", "patch", 'a_file.txt'])

    log_capture.check_present(
        ("bumpsemver.cli", "INFO", "Could not read config file at .bumpsemver.cfg"),
        ("bumpsemver.version_part", "INFO", "Parsing version '1.0.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=0, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=1, minor=0, patch=1"),
        ("bumpsemver.version_part", "INFO", "Parsing version '1.0.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=0, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '1.0.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files a_file.txt contain the version string..."),
        ("bumpsemver.files.generic", "INFO", "Found '1.0.0' in a_file.txt at line 0: 1.0.0"),
        ("bumpsemver.files.generic", "INFO", "Changing generic file a_file.txt:"),
        ("bumpsemver.files.generic", "INFO", "--- a/a_file.txt\n+++ b/a_file.txt\n@@ -1 +1 @@\n-1.0.0\n+1.0.1"),
        ("bumpsemver.cli", "INFO", "Would write to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 1.0.1\n\n"),
        order_matters=True
    )


def test_log_parse_doesnt_parse_current_version(tmpdir):
    tmpdir.chdir()

    with LogCapture() as log_capture:
        main(["--verbose", "--current-version", '12', "--new-version", "13", "patch"])

    log_capture.check_present(
        ("bumpsemver.cli", "INFO", "Could not read config file at .bumpsemver.cfg"),
        ("bumpsemver.version_part", "INFO", "Parsing version '12' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", 'WARNING',
         "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' does not parse current version '12'"),
        ("bumpsemver.version_part", "INFO", "Parsing version '13' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", 'WARNING',
         "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' does not parse current version '13'"),
        ("bumpsemver.cli", "INFO", "New version will be '13'"),
        ("bumpsemver.cli", "INFO", "Asserting files  contain the version string..."),
        ("bumpsemver.cli", "INFO", "Would write to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 13\n\n"),
    )


def test_complex_info_logging(tmpdir):
    tmpdir.join("fileE").write("0.4.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpsemver]
        current_version = 0.4.0
        
        [bumpsemver:file:fileE]
        """).strip())

    with LogCapture() as log_capture:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:file:fileE]"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=4, patch=1"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.4.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileE contain the version string..."),
        ("bumpsemver.files.generic", "INFO", "Found '0.4.0' in fileE at line 0: 0.4.0"),
        ("bumpsemver.files.generic", "INFO", "Changing generic file fileE:"),
        ("bumpsemver.files.generic", "INFO", "--- a/fileE\n+++ b/fileE\n@@ -1 +1 @@\n-0.4.0\n+0.4.1"),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:file:fileE]\n\n")
    )


def test_multi_file_configuration(tmpdir):
    tmpdir.join("FULL_VERSION.txt").write("1.0.3")
    tmpdir.join("MAJOR_VERSION.txt").write("1.0.3")

    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 1.0.3

        [bumpsemver:file:FULL_VERSION.txt]

        [bumpsemver:file:MAJOR_VERSION.txt]
        """).strip())

    main(["major", "--verbose"])
    assert "2.0.0" in tmpdir.join("FULL_VERSION.txt").read()
    assert "2.0.0" in tmpdir.join("MAJOR_VERSION.txt").read()

    main(["patch"])
    assert "2.0.1" in tmpdir.join("FULL_VERSION.txt").read()
    assert "2.0.1" in tmpdir.join("MAJOR_VERSION.txt").read()


def test_search_replace_to_avoid_updating_unconcerned_lines(tmpdir):
    tmpdir.chdir()

    tmpdir.join("requirements.txt").write("Django>=1.5.6,<1.6\nMyProject==1.5.6")

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
      [bumpsemver]
      current_version = 1.5.6

      [bumpsemver:file:requirements.txt]
      search = MyProject=={current_version}
      replace = MyProject=={new_version}
      """).strip())

    with LogCapture() as log_capture:
        main(["minor", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 1.5.6\n\n[bumpsemver:file:requirements.txt]\n"
         "search = MyProject=={current_version}\nreplace = MyProject=={new_version}"),
        ("bumpsemver.version_part", "INFO", "Parsing version '1.5.6' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=5, patch=6"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'minor'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=1, minor=6, patch=0"),
        ("bumpsemver.version_part", "INFO", "Parsing version '1.6.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=6, patch=0"),
        ("bumpsemver.cli", "INFO", "New version will be '1.6.0'"),
        ("bumpsemver.cli", "INFO", "Asserting files requirements.txt contain the version string..."),
        ("bumpsemver.files.generic", "INFO", "Found 'MyProject==1.5.6' in requirements.txt at line 1: MyProject==1.5.6"),
        ("bumpsemver.files.generic", "INFO", "Changing generic file requirements.txt:"),
        ("bumpsemver.files.generic", "INFO",
         "--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1,2 +1,2 @@\n Django>=1.5.6,<1.6\n-MyProject==1.5.6\n+MyProject==1.6.0"),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 1.6.0\n\n[bumpsemver:file:requirements.txt]\n"
         "search = MyProject=={current_version}\nreplace = MyProject=={new_version}\n\n")
    )

    assert "MyProject==1.6.0" in tmpdir.join("requirements.txt").read()
    assert "Django>=1.5.6" in tmpdir.join("requirements.txt").read()


def test_search_replace_expanding_changelog(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGELOG.md").write(dedent("""
        My awesome software project Changelog
        =====================================
        
        Unreleased
        ----------
        
        * Some nice feature
        * Some other nice feature
        
        Version v8.1.1 (2014-05-28)
        ---------------------------
        
        * Another old nice feature
        
        """).strip())

    config_content = dedent("""
        [bumpsemver]
        current_version = 8.1.1

        [bumpsemver:file:CHANGELOG.md]
        search =
          Unreleased
          ----------
        replace =
          Unreleased
          ----------
          Version v{new_version} ({now:%Y-%m-%d})
          ---------------------------
        """).strip()

    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with mock.patch("bumpsemver.cli.logger"):
        main(["minor", "--verbose"])

    predate = dedent("""
        Unreleased
        ----------
        Version v8.2.0 (20
        """).strip()

    postdate = dedent("""
        )
        ---------------------------

        * Some nice feature
        * Some other nice feature
        """).strip()

    assert predate in tmpdir.join("CHANGELOG.md").read()
    assert postdate in tmpdir.join("CHANGELOG.md").read()


def test_non_matching_search_does_not_modify_file(tmpdir):
    tmpdir.chdir()

    changelog_content = dedent("""
        # Unreleased
        
        * bullet point A
        
        # Release v'older' (2019-09-17)
        
        * bullet point B
        """).strip()

    config_content = dedent("""
        [bumpsemver]
        current_version = 1.0.3
        
        [bumpsemver:file:CHANGELOG.md]
        search = Not-yet-released
        replace = Release v{new_version} ({now:%Y-%m-%d})
        """).strip()

    tmpdir.join("CHANGELOG.md").write(changelog_content)
    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with pytest.raises(exceptions.VersionNotFoundException, match="Did not find 'Not-yet-released' in file: 'CHANGELOG.md'"):
        main(["patch", "--verbose"])

    assert changelog_content == tmpdir.join("CHANGELOG.md").read()
    assert config_content in tmpdir.join(".bumpsemver.cfg").read()


def test_search_replace_cli(tmpdir):
    tmpdir.join("file89").write("My birthday: 3.5.98\nCurrent version: 3.5.98")
    tmpdir.chdir()
    main([
        "--current-version", '3.5.98',
        "--search", "Current version: {current_version}",
        "--replace", "Current version: {new_version}",
        "minor",
        "file89",
    ])

    assert "My birthday: 3.5.98\nCurrent version: 3.6.0" == tmpdir.join("file89").read()


def test_deprecation_warning_files_in_global_configuration(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileX").write("3.2.1")
    tmpdir.join("fileY").write("3.2.1")
    tmpdir.join("fileZ").write("3.2.1")

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 3.2.1
        files = fileX fileY fileZ
        """).strip())

    warning_registry = getattr(bumpsemver, "__warningregistry__", None)
    if warning_registry:
        warning_registry.clear()
    warnings.resetwarnings()
    warnings.simplefilter("always")
    with warnings.catch_warnings(record=True) as received_warnings:
        main(["patch"])

    w = received_warnings.pop()
    assert issubclass(w.category, PendingDeprecationWarning)
    assert "'files =' configuration will be deprecated, please use" in str(w.message)


def test_deprecation_warning_multiple_files_cli(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileA").write("1.2.3")
    tmpdir.join("fileB").write("1.2.3")
    tmpdir.join("fileC").write("1.2.3")

    warning_registry = getattr(bumpsemver, "__warningregistry__", None)
    if warning_registry:
        warning_registry.clear()
    warnings.resetwarnings()
    warnings.simplefilter("always")
    with warnings.catch_warnings(record=True) as received_warnings:
        main(["--current-version", "1.2.3", "patch", "fileA", "fileB", "fileC"])

    w = received_warnings.pop()
    assert issubclass(w.category, PendingDeprecationWarning)
    assert "Giving multiple files on the command line will be deprecated" in str(w.message)


def test_multi_line_search_is_found(tmpdir):
    tmpdir.chdir()

    tmpdir.join("the_alphabet.txt").write(dedent("""
        A
        B
        C
        """))

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 9.8.7
        
        [bumpsemver:file:the_alphabet.txt]
        search =
          A
          B
          C
        replace =
          A
          B
          C
          {new_version}
        """).strip())

    main(['major'])

    assert dedent("""
      A
      B
      C
      10.0.0
    """) == tmpdir.join("the_alphabet.txt").read()


def test_configparser_empty_lines_in_values(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGES.rst").write(dedent("""
    My changelog
    ============

    current
    -------

    """))

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpsemver]
    current_version = 0.4.1

    [bumpsemver:file:CHANGES.rst]
    search =
      current
      -------
    replace = current
      -------


      {new_version}
      -------
      """).strip())

    main(["patch"])
    assert dedent("""
      My changelog
      ============
      current
      -------


      0.4.2
      -------

    """) == tmpdir.join("CHANGES.rst").read()


def test_regression_dont_touch_capitalization_of_keys_in_config(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 0.1.0
    
        [other]
        DJANGO_SETTINGS = Value
        """).strip())

    main(["patch"])

    assert dedent("""
        [bumpsemver]
        current_version = 0.1.1
    
        [other]
        DJANGO_SETTINGS = Value
        """).strip() == tmpdir.join(".bumpsemver.cfg").read().strip()


def test_regression_new_version_cli_in_files(tmpdir):
    tmpdir.chdir()
    tmpdir.join("myp___init__.py").write("__version__ = '0.7.2'")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 0.7.2
        message = v{new_version}
        tag_name = {new_version}
        tag = true
        commit = true
        [bumpsemver:file:myp___init__.py]
        """).strip())

    main("patch --allow-dirty --verbose --new-version 0.9.3".split(" "))

    assert "__version__ = '0.9.3'" == tmpdir.join("myp___init__.py").read()
    assert "current_version = 0.9.3" in tmpdir.join(".bumpsemver.cfg").read()


def test_correct_interpolation_for_setup_cfg_files(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file.py").write("XX-XX-XXXX v. X.X.X")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 0.7.2
        search = XX-XX-XXXX v. X.X.X
        replace = {now:%m-%d-%Y} v. {new_version}
        [bumpsemver:file:file.py]
        """).strip())

    main(["major"])

    assert datetime.now().strftime("%m-%d-%Y") + " v. 1.0.0" == tmpdir.join("file.py").read()
    assert "current_version = 1.0.0" in tmpdir.join(".bumpsemver.cfg").read()


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

        assert positional == ['major', 'setup.py']
        assert optional == ["--dry-run"]

    def test_2optional_1positional(self):
        params = ["--dry-run", "--message", '"Commit"', "major"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == ['major']
        assert optional == ["--dry-run", "--message", '"Commit"']

    def test_2optional_mixed_2positional(self):
        params = ["--allow-dirty", "--message", '"Commit"', "minor", "setup.py"]
        positional, optional = split_args_in_optional_and_positional(params)

        assert positional == ["minor", "setup.py"]
        assert optional == ["--allow-dirty", "--message", '"Commit"']


def test_defaults_in_usage_with_config(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("my_defaults.cfg").write(dedent("""
        [bumpsemver]
        current_version: 18
        new_version: 19
        [bumpsemver:file:file1]
        [bumpsemver:file:file2]
        [bumpsemver:file:file3]
        """).strip())
    with pytest.raises(SystemExit):
        main(["--config-file", "my_defaults.cfg", "--help"])

    out, err = capsys.readouterr()

    assert "Version that needs to be updated (default: 18)" in out
    assert "New version that should be in the files (default: 19)" in out
    assert "[--current-version VERSION]" in out
    assert "[--new-version VERSION]" in out
    assert "[file ...]" in out


def test_config_file(tmpdir):
    tmpdir.join("file1").write("0.9.34")
    tmpdir.join("my_bump_config.cfg").write(dedent("""
        [bumpsemver]
        current_version: 0.9.34
        new_version: 0.9.35
        [bumpsemver:file:file1]
        """).strip())

    tmpdir.chdir()
    main(shlex_split("patch --config-file my_bump_config.cfg"))

    assert "0.9.35" == tmpdir.join("file1").read()


def test_default_config_files(tmpdir):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 0.10.2
        new_version: 0.10.3
        [bumpsemver:file:file2]
        """).strip())

    tmpdir.chdir()
    main(["patch"])

    assert "0.10.3" == tmpdir.join("file2").read()


def test_file_keyword_with_suffix_is_accepted(tmpdir, file_keyword):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 0.10.2
        new_version: 0.10.3
        [bumpsemver:%s:file2]
        """ % file_keyword).strip())

    tmpdir.chdir()
    main(["patch"])

    assert "0.10.3" == tmpdir.join("file2").read()


def test_config_file_is_updated(tmpdir):
    tmpdir.join("file3").write("0.0.13")
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 0.0.13
        new_version: 0.0.14
        [bumpsemver:file:file3]
        """).strip())

    tmpdir.chdir()
    main(["patch", "--verbose"])

    assert """[bumpsemver]
current_version = 0.0.14

[bumpsemver:file:file3]
""" == tmpdir.join(".bumpsemver.cfg").read()


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_retain_newline(tmpdir, newline):
    tmpdir.join("file.py").write_binary(dedent("""
        0.7.2
        Some Content
        """).strip().encode(encoding='UTF-8').replace(b"\n", newline))
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write_binary(dedent("""
        [bumpsemver]
        current_version = 0.7.2
        search = {current_version}
        replace = {new_version}
        [bumpsemver:file:file.py]
        """).strip().encode(encoding='UTF-8').replace(b"\n", newline))

    main(["major"])

    assert newline in tmpdir.join("file.py").read_binary()
    new_config = tmpdir.join(".bumpsemver.cfg").read_binary()
    assert newline in new_config

    # Ensure there is only a single newline (not two) at the end of the file and that it is of the right type
    assert new_config.endswith(b"[bumpsemver:file:file.py]" + newline)
