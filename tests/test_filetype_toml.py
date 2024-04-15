from box import Box
from textwrap import dedent
from bumpsemver.files.toml import ConfiguredTOMLFile
import pytest
from bumpsemver.cli import main
from bumpsemver import exceptions
from testfixtures import LogCapture
import os


def test_simplest_query_1():
    obj = Box.from_toml("a = 1")
    assert obj.a == 1


def test_simplest_query_2():
    obj = Box.from_toml(
        dedent(
            r"""
    [a]
    b = 2
    """
        )
    )
    assert obj.a.b == 2


def test_simplest_query_3():
    obj = Box.from_toml(
        dedent(
            r"""
    [a.b]
    c = 3
    """
        )
    )
    assert obj.a.b.c == 3


def test_simplest_query_4():
    obj = Box.from_toml(
        dedent(
            r"""
    c = 4
    [a.b]
    c = 3
    """
        )
    )
    assert obj.a.b.c == 3
    assert obj.c == 4


def test_simplest_query_4_dots():
    obj = Box.from_toml(
        dedent(
            r"""
    c = 4
    [a.b]
    c = 3
    """
        ),
        box_dots=True,
    )
    assert obj["a.b.c"] == 3
    assert obj["c"] == 4


def test_array_single_value():
    obj = Box.from_toml(
        dedent(
            r"""
    [[a]]
    value = 1
    [[a]]
    value = 2
    [[a]]
    value = 3
    """
        ),
        box_dots=True,
    )
    assert obj["a[1].value"] == 2


def test_repr():
    file = ConfiguredTOMLFile("fileN", None, None)
    assert repr(file) == "<bumpsemver.files.ConfiguredTOMLFile:fileN>"


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


def test_toml_file_with_suffix_complex(tmpdir, toml_keyword):
    tmpdir.chdir()
    tmpdir.join("file1").write('version = "5.10.2"')
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version: 5.10.2
        new_version: 5.10.8
        [bumpsemver:%s:file1]
        tomlpath: version
        """
            % toml_keyword
        ).strip()
    )
    main(["patch"])

    assert "5.10.8" in tmpdir.join("file1").read()


def test_toml_file_simple(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 85.0.1
        [bumpsemver:toml:playbook.yml]
        tomlpath = dummy[0].vars.project_version
        """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
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
    main(["minor"])
    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """[[dummy]]
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
    )
    assert tmpdir.join("playbook.yml").read() == expected


def test_toml_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 85.4.1
        [bumpsemver:toml(a):playbook.yml]
        tomlpath = version
        [bumpsemver:toml(b):playbook.yml]
        tomlpath = pos.version
        """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
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
    main(["minor"])
    assert "current_version = 85.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """version = "85.5.0"

[pos]
version = "85.5.0"

[neg]
version = "85.4.1"
"""
    )
    assert tmpdir.join("playbook.yml").read() == expected


def test_toml_file_key_does_not_exist(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 85.8.1
        [bumpsemver:toml:playbook.yml]
        tomlpath = version_foo_bar
        """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
        version = "85.8.1"
    """
        ).strip()
    )

    with pytest.raises(
        exceptions.VersionNotFoundError,
        match="Did not find '85.8.1' at tomlpath 'version_foo_bar' in file: 'playbook.yml'",
    ):
        main(["minor"])

    assert "current_version = 85.8.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert 'version = "85.8.1"' in tmpdir.join("playbook.yml").read()


def test_toml_file_key_exists_but_wrong_value(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
        [bumpsemver]
        current_version = 85.10.1
        [bumpsemver:toml:playbook.yml]
        tomlpath = version
        """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
        version = "^85.10.1"
    """
        ).strip()
    )

    with pytest.raises(
        exceptions.VersionNotFoundError,
        match="Did not find '85.10.1' at tomlpath 'version' in file: 'playbook.yml'",
    ):
        main(["minor"])

    assert "current_version = 85.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert 'version = "^85.10.1"' in tmpdir.join("playbook.yml").read()


def test_toml_file_info_logging(tmpdir):
    tmpdir.join("fileZ").write(
        dedent(
            """
        version = "0.4.0"
        """
        ).strip()
    )
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            r"""
        [bumpsemver]
        current_version = 0.4.0

        [bumpsemver:toml:fileZ]
        tomlpath = version
        """
        ).strip()
    )

    with LogCapture() as log_capture:
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

    main(["minor"])

    actual = tmpdir.join("pyproject.toml").read()

    with open(data_path + "/pyproject_after.toml", "rt") as fin:
        assert actual == fin.read()
