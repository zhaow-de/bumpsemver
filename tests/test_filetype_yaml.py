import os
from textwrap import dedent

import pytest
from ruamel.yaml import YAML
from testfixtures import LogCapture

from bumpsemver.cli import main
from bumpsemver.files.yaml import ConfiguredYAMLFile
from bumpsemver.version_part import VersionConfig


def test_yaml_file_simple_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.0.1
            [bumpsemver:yaml:playbook.yml]
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write("version: '85.0.1'")
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data["version"] == "85.1.0"
    assert exc.value.code == 0


def test_yaml_file_simple_non_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.0.1
            [bumpsemver:yaml:playbook.yml]
            yamlpath = *.vars.project_version
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
            ---
            - name: 'create CodeBuild projects'
              vars:
                project_version: '85.0.1'
                software_component: 'devops'
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]["vars"]["project_version"] == "85.1.0"
    assert exc.value.code == 0


def test_yaml_file_simple_with_comments(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.0.1
            [bumpsemver:yaml:playbook.yml]
            yamlpath = *.vars.project_version
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
            # Some comments here
            ---
            # Here
            - name: 'create CodeBuild projects'
              # Here
              vars:
                project_version: '85.0.1'  # and here
                software_component: 'devops'
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    expected = dedent(
        """---
# Here
  - name: 'create CodeBuild projects'
  # Here
    vars:
      project_version: 85.1.0  # and here
      software_component: 'devops'
    """
    )

    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]["vars"]["project_version"] == "85.1.0"
    assert tmpdir.join("playbook.yml").read() == expected
    assert exc.value.code == 0


def test_yaml_file_exact_path(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.2.1
            [bumpsemver:yaml:playbook.yml]
            yamlpath = *.vars.project_version
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
            - level: '[]-prop'
              vars:
                project_version: 85.2.1
              child_prop1:
                level: '[]-prop-prop'
                vars:
                  project_version: 85.2.1
              child_prop2:
                - level: '[]-prop-[]-prop'
                  vars:
                    project_version: 85.2.1
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.3.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]["vars"]["project_version"] == "85.3.0"
    assert data[0]["child_prop1"]["vars"]["project_version"] == "85.2.1"
    assert data[0]["child_prop2"][0]["vars"]["project_version"] == "85.2.1"
    assert exc.value.code == 0


def test_yaml_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 85.4.1
            [bumpsemver:yaml(a):playbook.yml]
            yamlpath = version
            [bumpsemver:yaml(b):playbook.yml]
            yamlpath = pos.version
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write(
        dedent(
            """
            version: 85.4.1
            pos:
              version: 85.4.1
            neg:
              version: 85.4.1
            """
        ).strip()
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 85.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data["version"] == "85.5.0"
    assert data["pos"]["version"] == "85.5.0"
    assert data["neg"]["version"] == "85.4.1"
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        "yaml",
        "yaml(suffix)",
        "yaml (suffix with space)",
        "yaml (suffix lacking closing paren",
    ]
)
def yaml_keyword(request):
    """Return multiple possible styles for the bumpsemver:yaml keyword."""
    return request.param


def test_type_keyword_with_suffix_is_accepted(tmpdir, yaml_keyword):
    tmpdir.join("file2").write("version: 5.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 5.10.2
            new_version = 5.10.8
            [bumpsemver:%s:file2]
            yamlpath = version
            """
            % yaml_keyword
        ).strip()
    )
    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    cfg_expected = dedent(
        """[bumpsemver]
current_version = 5.10.8

[bumpsemver:%s:file2]
yamlpath = version
"""
        % yaml_keyword
    )

    assert "5.10.8" in tmpdir.join("file2").read()
    assert tmpdir.join(".bumpsemver.cfg").read() == cfg_expected
    assert exc.value.code == 0


def test_yaml_file_info_logging(tmpdir):
    tmpdir.join("fileY").write(
        dedent(
            """
            ---
            version: 0.4.0
            """
        ).strip()
    )
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.4.0

            [bumpsemver:yaml:fileY]
            yamlpath = version
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
            "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:yaml:fileY]\nyamlpath = version",
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
        ("bumpsemver.cli", "INFO", "Asserting files fileY contain the version string..."),
        ("bumpsemver.files.yaml", "INFO", "Changing yaml file fileY:"),
        (
            "bumpsemver.files.yaml",
            "INFO",
            "--- a/fileY\n+++ b/fileY\n@@ -1,2 +1,2 @@\n ---\n-version: 0.4.0\n+version: 0.4.1",
        ),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.cli",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:yaml:fileY]\nyamlpath = version\n\n",
        ),
    )
    assert "current_version = 0.4.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_repr():
    file = ConfiguredYAMLFile("fileL", VersionConfig(), None, None)
    assert repr(file) == "<bumpsemver.files.ConfiguredYAMLFile:fileL>"


def test_yaml_file_multiple_values_one_pattern(tmpdir):
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

            [bumpsemver:yaml:attribute_sources.yml]
            yamlpath = sources.tables.meta.version
            """
        ).strip()
    )
    with open(data_path + "/attribute_sources_before.yml", "rt") as fin:
        tmpdir.join("attribute_sources.yml").write(fin.read())
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    actual = tmpdir.join("attribute_sources.yml").read()

    with open(data_path + "/attribute_sources_after.yml", "rt") as fin:
        assert actual == fin.read()
    assert "current_version = 2.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.5.1
            [bumpsemver:yaml:sample.yml]
            yamlpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample.yml'"),
        order_matters=False,
    )
    assert "current_version = 99.5.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


def test_second_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.7.1
            [bumpsemver:yaml:sample1.yml]
            yamlpath = version
            [bumpsemver:yaml:sample2.yml]
            yamlpath = version
            """
        ).strip()
    )
    tmpdir.join("sample1.yml").write("version: 99.7.1")

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample2.yml'"),
        order_matters=False,
    )
    assert "current_version = 99.7.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


def test_invalid_file(tmpdir):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 2.13.1
        [bumpsemver:yaml:file106.yml]
        yamlpath = version
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file106.yml").write('{"version" = "2.13.1"}')
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "File file106.yml cannot be parsed as a valid yaml file",
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


def test_locator_finds_nothing(tmpdir):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 6.13.1
        [bumpsemver:yaml:file110.yml]
        yamlpath = release
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file110.yml").write("version:\n  release: 6.13.1")
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector 'release' does not lead to a valid property in yaml file file110.yml",
        ),
        order_matters=False,
    )

    assert tmpdir.join(".bumpsemver.cfg").read() == cfg
    assert exc.value.code == 4


def test_invalid_locator(tmpdir):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 7.13.1
        [bumpsemver:yaml:file111.yml]
        yamlpath = "}](!'
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file111.yml").write("version:\n  release: 7.13.1")
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector '\"}](!'' does not lead to a valid property in yaml file file111.yml",
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
            current_version = 85.10.1
            [bumpsemver:yaml:playbook.yml]
            yamlpath = version
            """
        ).strip()
    )
    tmpdir.join("playbook.yml").write("version: ^85.10.1")

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            f"Selector 'version' finds value '^85.10.1' "
            f"mismatches with the expectation '85.10.1' in yaml file playbook.yml",
        ),
        order_matters=False,
    )

    assert "current_version = 85.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert "version: ^85.10.1" in tmpdir.join("playbook.yml").read()
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        # partial match (the last element mismatches)
        {
            "file": "---\n  - version: 85.11.1\n  - version: 85.11.1\n  - child:\n      version: 85.11.1\n",
            "expected": "---\n  - version: 85.12.0\n  - version: 85.12.0\n  - child:\n      version: 85.11.1\n",
            "version_before": "85.11.1",
            "version_after": "85.12.0",
        },
        # partial match (the first element mismatches)
        {
            "file": "---\n  - child:\n      version: 95.11.1\n  - version: 95.11.1\n  - version: 95.11.1\n",
            "expected": "---\n  - child:\n      version: 95.11.1\n  - version: 95.12.0\n  - version: 95.12.0\n",
            "version_before": "95.11.1",
            "version_after": "95.12.0",
        },
        # partial match (a middle element mismatches)
        {
            "file": "---\n  - version: 96.11.1\n  - child:\n      version: 96.11.1\n  - version: 96.11.1\n",
            "expected": "---\n  - version: 96.12.0\n  - child:\n      version: 96.11.1\n  - version: 96.12.0\n",
            "version_before": "96.11.1",
            "version_after": "96.12.0",
        },
        # full match
        {
            "file": "---\n  - version: 97.11.1\n  - version: 97.11.1\n  - version: 97.11.1\n",
            "expected": "---\n  - version: 97.12.0\n  - version: 97.12.0\n  - version: 97.12.0\n",
            "version_before": "97.11.1",
            "version_after": "97.12.0",
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
            [bumpsemver:yaml:test85.yml]
            yamlpath = *.version
            """
            % array_positive["version_before"]
        ).strip()
    )
    tmpdir.join("test85.yml").write(array_positive["file"])
    with pytest.raises(SystemExit) as exc:
        main(["minor"])
    expected = array_positive["expected"]
    assert f"current_version = {array_positive['version_after']}" in tmpdir.join(".bumpsemver.cfg").read()
    assert tmpdir.join("test85.yml").read() == expected
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        # partial match (the last element mismatches)
        {
            "file": "---\n  - version: 98.11.1\n  - version: 98.11.1\n  - version: 98.11.0\n",
            "version": "98.11.1",
            "error": f"Selector '*.version' finds list of values ['98.11.1', '98.11.1', '98.11.0'] "
            f"with one more more elements mismatch with the expectation '98.11.1' in yaml file test98.yml",
        },
        # partial match (the first element mismatches)
        {
            "file": "---\n  - version: 99.11.0\n  - version: 99.11.1\n  - version: 99.11.1\n",
            "version": "99.11.1",
            "error": f"Selector '*.version' finds list of values ['99.11.0', '99.11.1', '99.11.1'] "
            f"with one more more elements mismatch with the expectation '99.11.1' in yaml file test98.yml",
        },
        # partial match (a middle element mismatches)
        {
            "file": "---\n  - version: 100.11.1\n  - version: 100.11.0\n  - version: 100.11.1\n",
            "version": "100.11.1",
            "error": f"Selector '*.version' finds list of values ['100.11.1', '100.11.0', '100.11.1'] "
            f"with one more more elements mismatch with the expectation '100.11.1' in yaml file test98.yml",
        },
        # full mismatch
        {
            "file": "---\n  - version: 101.11.2\n  - version: 101.11.3\n  - version: 101.11.4\n",
            "version": "101.11.1",
            "error": f"Selector '*.version' finds list of values ['101.11.2', '101.11.3', '101.11.4'] "
            f"with one more more elements mismatch with the expectation '101.11.1' in yaml file test98.yml",
        },
        # locator finds nothing
        {
            "file": "---\n  - version2: 102.11.1\n  - version3: 102.11.1\n  - version4: 102.11.1\n",
            "version": "102.11.1",
            "error": "Selector '*.version' does not lead to a valid property in yaml file test98.yml",
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
        [bumpsemver:yaml:test98.yml]
        yamlpath = *.version
        """
        % array_negative["version"]
    ).strip()
    orig_file = dedent(array_negative["file"])

    tmpdir.join(".bumpsemver.cfg").write(orig_cfg)
    tmpdir.join("test98.yml").write(orig_file)

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
    assert tmpdir.join("test98.yml").read() == orig_file
