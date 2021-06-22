# pylint: skip-file

# noinspection PyPackageRequirements
import pytest
# noinspection PyPackageRequirements
from testfixtures import LogCapture

from textwrap import dedent
from ruamel.yaml import YAML

from bumpsemver import exceptions
from bumpsemver.cli import main


@pytest.fixture(params=[
    "yaml",
    "yaml(suffix)",
    "yaml (suffix with space)",
    "yaml (suffix lacking closing paren",
])
def yaml_keyword(request):
    """Return multiple possible styles for the bumpsemver:yaml keyword."""
    return request.param


def test_yaml_file_simple(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.0.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = *.vars.project_version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        ---
        - name: 'create CodeBuild projects'
          vars:
            project_version: '85.0.1'
            software_component: 'devops'
    """).strip())
    main(["minor"])
    assert "current_version = 85.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]['vars']['project_version'] == "85.1.0"


def test_yaml_file_exact_path(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.2.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = *.vars.project_version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
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
            """).strip())
    main(["minor"])
    assert "current_version = 85.3.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]['vars']['project_version'] == "85.3.0"
    assert data[0]['child_prop1']['vars']['project_version'] == "85.2.1"
    assert data[0]['child_prop2'][0]['vars']['project_version'] == "85.2.1"


def test_yaml_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.4.1
        [bumpsemver:yaml(a):playbook.yml]
        yamlpath = version
        [bumpsemver:yaml(b):playbook.yml]
        yamlpath = pos.version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        version: 85.4.1
        pos:
          version: 85.4.1
        neg:
          version: 85.4.1
    """).strip())
    main(["minor"])
    assert "current_version = 85.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data['version'] == "85.5.0"
    assert data['pos']['version'] == "85.5.0"
    assert data['neg']['version'] == "85.4.1"


def test_yaml_file_with_suffix_complex(tmpdir, yaml_keyword):
    tmpdir.join("file2").write("version: 5.10.2")
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 5.10.2
        new_version: 5.10.8
        [bumpsemver:%s:file2]
        yamlpath: version
        """ % yaml_keyword).strip())
    tmpdir.chdir()
    main(["patch"])

    assert "5.10.8" in tmpdir.join("file2").read()


def test_yaml_file_key_does_not_exist(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.8.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = version_foo_bar
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        version: 85.8.1
    """).strip())

    with pytest.raises(exceptions.VersionNotFoundException,
                       match="Did not find '85.8.1' at yamlpath 'version_foo_bar' in file: 'playbook.yml'"):
        main(["minor"])

    assert "current_version = 85.8.1" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data['version'] == "85.8.1"


def test_yaml_file_key_exists_but_wrong_value(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.10.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        version: ^85.10.1
    """).strip())

    with pytest.raises(exceptions.VersionNotFoundException, match="Did not find '85.10.1' at yamlpath 'version' in file: 'playbook.yml'"):
        main(["minor"])

    assert "current_version = 85.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data['version'] == "^85.10.1"


def test_yaml_file_multiple_values_positive(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.11.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = *.version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        ---
        - name: 'node 1'
          version: 85.11.1
        - name: 'node 2'
          version: 85.11.1
        - name: 'node 3'
          child:
            version: 85.11.1
    """).strip())
    main(["minor"])
    assert "current_version = 85.12.0" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]['version'] == "85.12.0"
    assert data[1]['version'] == "85.12.0"
    assert data[2]['child']['version'] == "85.11.1"


def test_yaml_file_multiple_values_negative(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 85.12.1
        [bumpsemver:yaml:playbook.yml]
        yamlpath = *.version
        """).strip())
    tmpdir.join("playbook.yml").write(dedent("""
        - name: 'node 1'
          version: 85.12.1
        - name: 'node 2'
          version: 1.2.3
    """).strip())

    with pytest.raises(exceptions.VersionNotFoundException,
                       match=r"Did not find '85.12.1' at yamlpath '\*\.version' in file: 'playbook.yml'"):
        main(["minor"])

    assert "current_version = 85.12.1" in tmpdir.join(".bumpsemver.cfg").read()
    yaml = YAML()
    data = yaml.load(tmpdir.join("playbook.yml").read())
    assert data[0]['version'] == "85.12.1"
    assert data[1]['version'] == "1.2.3"


def test_yaml_file_info_logging(tmpdir):
    tmpdir.join("fileY").write(dedent("""
        ---
        version: 0.4.0
        """).strip())
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpsemver]
        current_version = 0.4.0

        [bumpsemver:yaml:fileY]
        yamlpath = version
        """).strip())

    with LogCapture() as log_capture:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:yaml:fileY]\nyamlpath = version"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=4, patch=1"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.4.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileY contain the version string..."),
        ("bumpsemver.files.yaml", "INFO", "Changing yaml file fileY:"),
        ("bumpsemver.files.yaml", "INFO",
         "--- a/fileY\n+++ b/fileY\n@@ -1,2 +1,2 @@\n ---\n-version: 0.4.0\n+version: 0.4.1"),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:yaml:fileY]\nyamlpath = version\n\n")
    )
