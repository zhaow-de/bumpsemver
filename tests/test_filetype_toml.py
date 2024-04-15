import os
from textwrap import dedent

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main
from bumpsemver.files.toml import ConfiguredTOMLFile
from bumpsemver.version_part import VersionConfig


def test_toml_file_simple_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.0.1
            [bumpsemver:toml:test119.toml]
            """
        ).strip()
    )
    tmpdir.join("test119.toml").write(
        dedent(
            """
            version = "85.0.1"
            [[dummy]]
            version = "85.0.1"
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """
        version = "85.1.0"
        [[dummy]]
        version = "85.0.1"
        """
    ).strip()
    assert tmpdir.join("test119.toml").read() == expected
    assert exc.value.code == 0


def test_toml_file_simple_non_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.0.1
            [bumpsemver:toml:test118.toml]
            tomlpath = dummy[0].vars.project_version
            """
        ).strip()
    )
    tmpdir.join("test118.toml").write(
        dedent(
            """
            [[dummy]]
            name = "create CodeBuild project 1"
            [dummy.vars]
            project_version = "85.0.1"
            software_component = "devops"
            [[dummy]]
            name = "create CodeBuild project 2"
            [dummy.vars]
            project_version = "85.0.1"
            software_component = "airflow"
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """
        [[dummy]]
        name = "create CodeBuild project 1"
        [dummy.vars]
        project_version = "85.1.0"
        software_component = "devops"
        [[dummy]]
        name = "create CodeBuild project 2"
        [dummy.vars]
        project_version = "85.0.1"
        software_component = "airflow"
        """
    ).strip()
    assert tmpdir.join("test118.toml").read() == expected
    assert exc.value.code == 0


def test_toml_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.4.1
            [bumpsemver:toml(a):test118.toml]
            tomlpath = version
            [bumpsemver:toml(b):test118.toml]
            tomlpath = pos.version
            """
        ).strip()
    )
    tmpdir.join("test118.toml").write(
        dedent(
            """
            version = "85.4.1"
            [pos]
            version = "85.4.1"
            [neg]
            version = "85.4.1"
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """
        version = "85.5.0"
        [pos]
        version = "85.5.0"
        [neg]
        version = "85.4.1"
        """
    ).strip()
    assert tmpdir.join("test118.toml").read() == expected
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        "toml",
        "toml(suffix)",
        "toml (suffix with space)",
        "toml (suffix lacking closing paren",
    ]
)
def toml_keyword(request):
    """Return multiple possible styles for the bumpsemver:toml keyword."""
    return request.param


def test_type_keyword_with_suffix_is_accepted(tmpdir, toml_keyword):
    tmpdir.chdir()
    tmpdir.join("file1").write('version = "5.10.2"')
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 5.10.2
            new_version = 5.10.8
            [bumpsemver:%s:file1]
            tomlpath = version
            """
            % toml_keyword
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    cfg_expected = dedent(
        """[bumpsemver]
current_version = 5.10.8

[bumpsemver:%s:file1]
tomlpath = version
"""
        % toml_keyword
    )

    assert "5.10.8" in tmpdir.join("file1").read()
    assert tmpdir.join(".bumpsemver.cfg").read() == cfg_expected
    assert exc.value.code == 0


def test_toml_file_info_logging(tmpdir):
    tmpdir.join("fileZ").write('version = "0.4.0"')
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.4.0

            [bumpsemver:toml:fileZ]
            tomlpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        (
            "bumpsemver.cli",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:toml:fileZ]\ntomlpath = version",
        ),
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
        ("bumpsemver.cli", "INFO", "Asserting files fileZ contain the version string..."),
        ("bumpsemver.files.toml", "INFO", "Changing toml file fileZ:"),
        (
            "bumpsemver.files.toml",
            "INFO",
            '--- a/fileZ\n+++ b/fileZ\n@@ -1 +1 @@\n-version = "0.4.0"\n+version = "0.4.1"',
        ),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.cli",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:toml:fileZ]\ntomlpath = version\n\n",
        ),
    )
    assert "current_version = 0.4.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_repr():
    file = ConfiguredTOMLFile("fileN", VersionConfig(), None, None)
    assert repr(file) == "<bumpsemver.files.ConfiguredTOMLFile:fileN>"


def test_toml_file_real_pyproject_toml(tmpdir):
    data_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/fixtures")

    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 2.0.2
            commit = True
            tag = False
            tag_name = v{new_version}

            [bumpsemver:toml:pyproject.toml]
            tomlpath = tool.poetry.version
            """
        ).strip()
    )
    with open(data_path + "/pyproject_before.toml", "rt") as fin:
        tmpdir.join("pyproject.toml").write(fin.read())

    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    actual = tmpdir.join("pyproject.toml").read()

    with open(data_path + "/pyproject_after.toml", "rt") as fin:
        assert actual == fin.read()
    assert "current_version = 2.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.8.1
            [bumpsemver:toml:sample.toml]
            tomlpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample.toml'"),
        order_matters=False,
    )
    assert "current_version = 99.8.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


def test_second_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.8.1
            [bumpsemver:toml:sample1.toml]
            tomlpath = version
            [bumpsemver:toml:sample2.toml]
            tomlpath = version
            """
        ).strip()
    )
    tmpdir.join("sample1.toml").write('version = "99.8.1"')

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample2.toml'"),
        order_matters=False,
    )
    assert "current_version = 99.8.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


@pytest.fixture(
    params=[
        "version: 3.13.1",
        '{"version": "3.13.2"}',
        'version = "3.13.1"\nversion = "4"',
        '[section]\nversion1 = "3.13.1"\n[section]\nversion2 = "4"',
        "version",
        "=",
        '= "3.13.1"',
    ]
)
def toml_invalid_files(request):
    return request.param


def test_invalid_file(tmpdir, toml_invalid_files):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 3.13.1
        [bumpsemver:toml:file107.toml]
        tomlpath = version
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file107.toml").write(toml_invalid_files)
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "File file107.toml cannot be parsed as a valid toml file",
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        "release",
        "section[2].version",
        "section.release",
    ]
)
def toml_valid_locators(request):
    """Return multiple possible styles for the bumpsemver:toml keyword."""
    return request.param


def test_locator_finds_nothing(tmpdir, toml_valid_locators):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 8.13.1
        [bumpsemver:toml:file112.toml]
        tomlpath = %s
        """
        % toml_valid_locators
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file112.toml").write(
        'version = "6.13.1"\n[[section]]\nversion = "6.13.1"\n[[section]]\nversion = "6.13.2"'
    )
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector '%s' does not lead to a valid property in toml file file112.toml" % toml_valid_locators,
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        "]",
        "\"}](!'",
        "version[a]",
    ]
)
def toml_invalid_locators(request):
    """Return multiple possible styles for the bumpsemver:toml keyword."""
    return request.param


def test_invalid_locator(tmpdir, toml_invalid_locators):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 9.13.1
        [bumpsemver:toml:file113.toml]
        tomlpath = %s
        """
        % toml_invalid_locators
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file113.toml").write('version = "6.13.1"')
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector '%s' does not lead to a valid property in toml file file113.toml" % toml_invalid_locators,
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


def test_key_exists_but_wrong_value(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 86.10.1
            [bumpsemver:toml:pyproject.toml]
            tomlpath = tool.poetry.version
            """
        ).strip()
    )
    tmpdir.join("pyproject.toml").write('[tool.poetry]\nversion = "^86.10.1"')

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            f"Selector 'tool.poetry.version' finds value '^86.10.1' "
            f"mismatches with the expectation '86.10.1' in toml file pyproject.toml",
        ),
        order_matters=False,
    )

    assert "current_version = 86.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert 'version = "^86.10.1"' in tmpdir.join("pyproject.toml").read()
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        # partial match (the last element mismatches)
        {
            "file": """
                [[release]]
                version = "86.11.1"
                [[release]]
                version = "86.11.1"
                [[release]]
                [release.child]
                version = "86.11.1"
                """,
            "expected": """
                [[release]]
                version = "86.12.0"
                [[release]]
                version = "86.12.0"
                [[release]]
                [release.child]
                version = "86.11.1"
                """,
            "version_before": "86.11.1",
            "version_after": "86.12.0",
        },
        # partial match (the first element mismatches)
        {
            "file": """
                [[release]]
                [release.child]
                version = "87.11.1"
                [[release]]
                version = "87.11.1"
                [[release]]
                version = "87.11.1"
                """,
            "expected": """
                [[release]]
                [release.child]
                version = "87.11.1"
                [[release]]
                version = "87.12.0"
                [[release]]
                version = "87.12.0"
                """,
            "version_before": "87.11.1",
            "version_after": "87.12.0",
        },
        # partial match (a middle element mismatches)
        {
            "file": """
                [[release]]
                version = "88.11.1"
                [[release]]
                [release.child]
                version = "88.11.1"
                [[release]]
                version = "88.11.1"
                """,
            "expected": """
                [[release]]
                version = "88.12.0"
                [[release]]
                [release.child]
                version = "88.11.1"
                [[release]]
                version = "88.12.0"
                """,
            "version_before": "88.11.1",
            "version_after": "88.12.0",
        },
        # full match
        {
            "file": """
                [[release]]
                version = "89.11.1"
                [[release]]
                version = "89.11.1"
                [[release]]
                version = "89.11.1"
                """,
            "expected": """
                [[release]]
                version = "89.12.0"
                [[release]]
                version = "89.12.0"
                [[release]]
                version = "89.12.0"
                """,
            "version_before": "89.11.1",
            "version_after": "89.12.0",
        },
    ]
)
def array_positive(request):
    return request.param


def test_multiple_values_positive(tmpdir, array_positive):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = %s
            [bumpsemver:toml:test.toml]
            tomlpath = release.version
            """
            % array_positive["version_before"]
        ).strip()
    )
    tmpdir.join("test.toml").write(dedent(array_positive["file"]).strip())
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    expected = dedent(array_positive["expected"]).strip()
    assert f"current_version = {array_positive['version_after']}" in tmpdir.join(".bumpsemver.cfg").read()
    assert tmpdir.join("test.toml").read() == expected
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        # partial match (the last element mismatches)
        {
            "file": """
                [[release]]
                version = "90.11.1"
                [[release]]
                version = "90.11.1"
                [[release]]
                version = "90.11.0"
                """,
            "version": "90.11.1",
            "error": f"Selector 'release.version' finds list of values ['90.11.1', '90.11.1', '90.11.0'] "
            f"with one more more elements mismatch with the expectation '90.11.1' in toml file test90.toml",
        },
        # partial match (the first element mismatches)
        {
            "file": """
                [[release]]
                version = "91.11.0"
                [[release]]
                version = "91.11.1"
                [[release]]
                version = "91.11.1"
                """,
            "version": "91.11.1",
            "error": f"Selector 'release.version' finds list of values ['91.11.0', '91.11.1', '91.11.1'] "
            f"with one more more elements mismatch with the expectation '91.11.1' in toml file test90.toml",
        },
        # partial match (a middle element mismatches)
        {
            "file": """
                [[release]]
                version = "92.11.1"
                [[release]]
                version = "92.11.0"
                [[release]]
                version = "92.11.1"
                """,
            "version": "92.11.1",
            "error": f"Selector 'release.version' finds list of values ['92.11.1', '92.11.0', '92.11.1'] "
            f"with one more more elements mismatch with the expectation '92.11.1' in toml file test90.toml",
        },
        # full mismatch
        {
            "file": """
                [[release]]
                version = "93.11.2"
                [[release]]
                version = "93.11.3"
                [[release]]
                version = "93.11.4"
                """,
            "version": "93.11.1",
            "error": f"Selector 'release.version' finds list of values ['93.11.2', '93.11.3', '93.11.4'] "
            f"with one more more elements mismatch with the expectation '93.11.1' in toml file test90.toml",
        },
        # locator finds nothing
        {
            "file": """
                [[release]]
                version2 = "92.11.1"
                [[release]]
                version3 = "92.11.1"
                [[release]]
                version4 = "92.11.1"
                """,
            "version": "92.11.1",
            "error": "Selector 'release.version' does not lead to a valid property in toml file test90.toml",
        },
    ]
)
def array_negative(request):
    return request.param


def test_multiple_values_negative(tmpdir, array_negative):
    tmpdir.chdir()
    orig_cfg = dedent(
        """
        [bumpsemver]
        current_version = %s
        [bumpsemver:toml:test90.toml]
        tomlpath = release.version
        """
        % array_negative["version"]
    ).strip()
    orig_file = dedent(array_negative["file"]).strip()
    tmpdir.join(".bumpsemver.cfg").write(orig_cfg)
    tmpdir.join("test90.toml").write(orig_file)

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            array_negative["error"],
        ),
        order_matters=False,
    )
    assert tmpdir.join(".bumpsemver.cfg").read() == orig_cfg
    assert tmpdir.join("test90.toml").read() == orig_file
    assert exc.value.code == 4
