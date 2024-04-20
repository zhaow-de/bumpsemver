from datetime import datetime
from textwrap import dedent
from unittest import mock

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main
from bumpsemver.exceptions import VersionNotFoundError
from bumpsemver.files.text import ConfiguredPlainTextFile
from bumpsemver.version_part import VersionConfig


def test_should_contain_version(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file1").write("Version: 75.0.1")
    vc = VersionConfig("Version: {current_version}", "Version: {new_version}")
    unknown_version = vc.parse("1.2.3")
    file = ConfiguredPlainTextFile("file1", vc)
    # Define a context
    context = {}

    with pytest.raises(VersionNotFoundError) as exc:
        file.should_contain_version(unknown_version, context)

    assert "VersionNotFoundError" == exc.typename
    assert "Did not find 'Version: 1.2.3' in plaintext file: 'file1'" in str(exc.value)

    known_version = vc.parse("75.0.1")
    try:
        file.should_contain_version(known_version, context)
    except VersionNotFoundError:
        pytest.fail("should_contain_version() raised VersionNotFoundException unexpectedly!")


def test_repr():
    file = ConfiguredPlainTextFile("file2", VersionConfig())
    assert repr(file) == "<bumpsemver.files.ConfiguredPlainTextFile:file2>"


def test_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.4.1
            [bumpsemver:plaintext:package.txt]
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'package.txt'"),
        order_matters=False,
    )
    assert "current_version = 99.4.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


def test_second_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.4.1
            [bumpsemver:plaintext:package1.txt]
            [bumpsemver:plaintext:package2.txt]
            """
        ).strip()
    )
    tmpdir.join("package1.txt").write("99.4.1")

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'package2.txt'"),
        order_matters=False,
    )
    assert "current_version = 99.4.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


def test_multi_file_configuration(tmpdir):
    tmpdir.join("FULL_VERSION.txt").write("1.0.3")
    tmpdir.join("MAJOR_VERSION.txt").write("1.0.3")

    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 1.0.3

            [bumpsemver:file:FULL_VERSION.txt]

            [bumpsemver:file:MAJOR_VERSION.txt]
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["major", "--verbose"])
    assert "2.0.0" in tmpdir.join("FULL_VERSION.txt").read()
    assert "2.0.0" in tmpdir.join("MAJOR_VERSION.txt").read()
    assert "current_version = 2.0.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(["patch"])
    assert "2.0.1" in tmpdir.join("FULL_VERSION.txt").read()
    assert "2.0.1" in tmpdir.join("MAJOR_VERSION.txt").read()
    assert "current_version = 2.0.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_search_replace_to_avoid_updating_unconcerned_lines(tmpdir):
    tmpdir.chdir()

    tmpdir.join("requirements.txt").write("Django>=1.5.6,<1.6\nMyProject==1.5.6")

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 1.5.6

            [bumpsemver:file:requirements.txt]
            search = MyProject=={current_version}
            replace = MyProject=={new_version}
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        (
            "bumpsemver.cli",
            "INFO",
            "[bumpsemver]\ncurrent_version = 1.5.6\n\n[bumpsemver:file:requirements.txt]\n"
            "search = MyProject=={current_version}\nreplace = MyProject=={new_version}",
        ),
        ("bumpsemver.cli", "WARNING", "File type 'file' is deprecated, please use 'plaintext' instead."),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '1.5.6' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=5, patch=6"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'minor'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=1, minor=6, patch=0"),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '1.6.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=1, minor=6, patch=0"),
        ("bumpsemver.cli", "INFO", "New version will be '1.6.0'"),
        ("bumpsemver.cli", "INFO", "Asserting files requirements.txt contain the version string..."),
        (
            "bumpsemver.files.text",
            "INFO",
            "Found 'MyProject==1.5.6' in requirements.txt at line 1: MyProject==1.5.6",
        ),
        ("bumpsemver.files.text", "INFO", "Changing plaintext file requirements.txt:"),
        (
            "bumpsemver.files.text",
            "INFO",
            (
                "--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1,2 +1,2 @@\n"
                " Django>=1.5.6,<1.6\n-MyProject==1.5.6\n+MyProject==1.6.0"
            ),
        ),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.cli",
            "INFO",
            "[bumpsemver]\ncurrent_version = 1.6.0\n\n[bumpsemver:file:requirements.txt]\n"
            "search = MyProject=={current_version}\nreplace = MyProject=={new_version}\n\n",
        ),
    )

    assert "MyProject==1.6.0" in tmpdir.join("requirements.txt").read()
    assert "Django>=1.5.6" in tmpdir.join("requirements.txt").read()
    assert "current_version = 1.6.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_search_replace_expanding_changelog(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGELOG.md").write(
        dedent(
            """
            My awesome software project Changelog
            =====================================

            Unreleased
            ----------

            * Some nice feature
            * Some other nice feature

            Version v8.1.1 (2014-05-28)
            ---------------------------

            * Another old nice feature

            """
        ).strip()
    )

    config_content = dedent(
        """
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
        """
    ).strip()

    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with mock.patch("bumpsemver.cli.logger"), pytest.raises(SystemExit) as exc:
        main(["minor", "--verbose"])

    predate = dedent(
        """
        Unreleased
        ----------
        Version v8.2.0 (20
        """
    ).strip()

    postdate = dedent(
        """
        )
        ---------------------------

        * Some nice feature
        * Some other nice feature
        """
    ).strip()

    assert predate in tmpdir.join("CHANGELOG.md").read()
    assert postdate in tmpdir.join("CHANGELOG.md").read()
    assert exc.value.code == 0


def test_non_matching_search_does_not_modify_file(tmpdir):
    tmpdir.chdir()

    changelog_content = dedent(
        """
        # Unreleased

        * bullet point A

        # Release v'older' (2019-09-17)

        * bullet point B
        """
    ).strip()

    config_content = dedent(
        """
        [bumpsemver]
        current_version = 1.0.3

        [bumpsemver:file:CHANGELOG.md]
        search = Not-yet-released
        replace = Release v{new_version} ({now:%Y-%m-%d})
        """
    ).strip()

    tmpdir.join("CHANGELOG.md").write(changelog_content)
    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "Did not find 'Not-yet-released' in plaintext file: 'CHANGELOG.md'"),
    )

    assert changelog_content == tmpdir.join("CHANGELOG.md").read()
    assert config_content in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 4


def test_search_replace_cli(tmpdir):
    tmpdir.join("file89").write("My birthday: 3.5.98\nCurrent version: 3.5.98")
    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--current-version",
                "3.5.98",
                "--search",
                "Current version: {current_version}",
                "--replace",
                "Current version: {new_version}",
                "minor",
                "file89",
            ]
        )

    assert "My birthday: 3.5.98\nCurrent version: 3.6.0" == tmpdir.join("file89").read()
    assert exc.value.code == 0


def test_deprecation_warning_files_in_global_configuration(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileX").write("3.2.1")
    tmpdir.join("fileY").write("3.2.1")
    tmpdir.join("fileZ").write("3.2.1")

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 3.2.1
            files = fileX fileY fileZ
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        ("bumpsemver.cli", "WARNING", "'files =' configuration will be deprecated, please use [bumpsemver:file:...]"),
        order_matters=False,
    )

    assert "current_version = 3.2.2" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_multi_line_search_is_found(tmpdir):
    tmpdir.chdir()

    tmpdir.join("the_alphabet.txt").write(
        dedent(
            """
            A
            B
            C
            """
        )
    )

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
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
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["major"])

    assert (
        dedent(
            """
      A
      B
      C
      10.0.0
    """
        )
        == tmpdir.join("the_alphabet.txt").read()
    )
    assert "current_version = 10.0.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_configparser_empty_lines_in_values(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGES.rst").write(
        dedent(
            """
    My changelog
    ============

    current
    -------

    """
        )
    )

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
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
      """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert (
        dedent(
            """
      My changelog
      ============
      current
      -------


      0.4.2
      -------

    """
        )
        == tmpdir.join("CHANGES.rst").read()
    )
    assert "current_version = 0.4.2" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_regression_dont_touch_capitalization_of_keys_in_config(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 0.1.0

        [other]
        DJANGO_SETTINGS = Value
        """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert (
        dedent(
            """
        [bumpsemver]
        current_version = 0.1.1

        [other]
        DJANGO_SETTINGS = Value
        """
        ).strip()
        == tmpdir.join(".bumpsemver.cfg").read().strip()
    )
    assert exc.value.code == 0


def test_regression_new_version_cli_in_files(tmpdir):
    tmpdir.chdir()
    tmpdir.join("myp___init__.py").write("__version__ = '0.7.2'")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 0.7.2
        message = v{new_version}
        tag_name = {new_version}
        tag = true
        commit = true
        [bumpsemver:file:myp___init__.py]
        """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main("patch --allow-dirty --verbose --new-version 0.9.3".split(" "))

    assert "__version__ = '0.9.3'" == tmpdir.join("myp___init__.py").read()
    assert "current_version = 0.9.3" in tmpdir.join(".bumpsemver.cfg").read()

    assert exc.value.code == 0


def test_correct_interpolation_for_setup_cfg_files(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file.py").write("XX-XX-XXXX v. X.X.X")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.7.2
            search = XX-XX-XXXX v. X.X.X
            replace = {now:%m-%d-%Y} v. {new_version}
            [bumpsemver:file:file.py]
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["major"])

    assert datetime.now().strftime("%m-%d-%Y") + " v. 1.0.0" == tmpdir.join("file.py").read()
    assert "current_version = 1.0.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        "file",
        "file(suffix)",
        "file (suffix with space)",
        "file (suffix lacking closing paren",
        "plaintext",
        "plaintext(suffix)",
        "plaintext (suffix with space)",
        "plaintext (suffix lacking closing paren",
    ]
)
def file_keyword(request):
    """Return multiple possible styles for the bumpsemver:file keyword."""
    return request.param


def test_type_keyword_with_suffix_is_accepted(tmpdir, file_keyword):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.10.2
            new_version = 0.10.3
            [bumpsemver:%s:file2]
            """
            % file_keyword
        ).strip()
    )

    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "0.10.3" == tmpdir.join("file2").read()
    assert "current_version = 0.10.3" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_config_file_is_updated(tmpdir):
    tmpdir.join("file3").write("0.0.13")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.0.13
            new_version = 0.0.14
            [bumpsemver:file:file3]
            """
        ).strip()
    )

    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    assert (
        """[bumpsemver]
current_version = 0.0.14

[bumpsemver:file:file3]
"""
        == tmpdir.join(".bumpsemver.cfg").read()
    )
    assert exc.value.code == 0


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_retain_newline(tmpdir, newline):
    tmpdir.join("file.py").write_binary(
        dedent(
            """
        0.7.2
        Some Content
        """
        )
        .strip()
        .encode(encoding="UTF-8")
        .replace(b"\n", newline)
    )
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write_binary(
        dedent(
            """
        [bumpsemver]
        current_version = 0.7.2
        search = {current_version}
        replace = {new_version}
        [bumpsemver:file:file.py]
        """
        )
        .strip()
        .encode(encoding="UTF-8")
        .replace(b"\n", newline)
    )

    with pytest.raises(SystemExit) as exc:
        main(["major"])

    assert newline in tmpdir.join("file.py").read_binary()
    new_config = tmpdir.join(".bumpsemver.cfg").read_binary()
    assert newline in new_config

    # Ensure there is only a single newline (not two) at the end of the file and that it is of the right type
    assert new_config.endswith(b"[bumpsemver:file:file.py]" + newline)
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        {
            "cfg": """
                [bumpsemver]
                current_version = 0.13
                new_version = 0.14
                [bumpsemver:plaintext:file103.txt]
                """,
            "version": "0.13",
        },
        {
            "cfg": """
                [bumpsemver]
                current_version = 0.13.pre-SNAPSHOT
                new_version = 0.14.pre-SNAPSHOT
                [bumpsemver:plaintext:file103.txt]
                """,
            "version": "0.13.pre-SNAPSHOT",
        },
    ]
)
def wrong_version_pattern(request):
    return request.param


def test_wrong_version_pattern_in_cfg(tmpdir, wrong_version_pattern):
    cfg = dedent(wrong_version_pattern["cfg"]).strip()
    tmpdir.join("file103.txt").write(wrong_version_pattern["version"])
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.chdir()
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "The specific version could not be parsed with semver scheme. Please double check the config file",
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


def test_update_mixed_newlines(tmpdir):
    tmpdir.chdir()
    # the file operation helper by pytest is too intelligent to swallow these inconsistencies.
    # here we use lower level functions
    with open(tmpdir.join("file104"), "wt", newline="") as f_out:
        f_out.write("Header\r\nCurrent version: 100.5.98\nFooter\r")

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(
            [
                "--current-version",
                "100.5.98",
                "--search",
                "Current version: {current_version}",
                "--replace",
                "Current version: {new_version}",
                "minor",
                "file104",
            ]
        )

    assert "Current version: 100.6.0" in tmpdir.join("file104").read()
    log_capture.check_present(
        ("bumpsemver.cli", "WARNING", "File file104 has mixed newline characters: ('\\r', '\\n', '\\r\\n')"),
        order_matters=False,
    )
    assert exc.value.code == 3
