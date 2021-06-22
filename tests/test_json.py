# pylint: skip-file

# noinspection PyPackageRequirements
import pytest
# noinspection PyPackageRequirements
from testfixtures import LogCapture

import json
from textwrap import dedent

from bumpsemver import exceptions
from bumpsemver.cli import main


@pytest.fixture(params=[
    "json",
    "json(suffix)",
    "json (suffix with space)",
    "json (suffix lacking closing paren",
])
def json_keyword(request):
    """Return multiple possible styles for the bumpsemver:json keyword."""
    return request.param


def test_json_file_simple(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.0.1
        [bumpsemver:json:package.json]
        jsonpath = version
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "75.0.1"
        }
    """)
    main(["minor"])
    assert "current_version = 75.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["version"] == "75.1.0"


def test_json_file_exact_path(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.2.1
        [bumpsemver:json:package.json]
        jsonpath = version
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "75.2.1",
          "dependencies": {
            "@babel/code-frame": {
              "version": "75.2.1",
              "requires": {
                "version": "^75.2.1"
              }
            }
          }
        }
    """)
    main(["minor"])
    assert "current_version = 75.3.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == "75.3.0"
    assert data['dependencies']['@babel/code-frame']['version'] == "75.2.1"
    assert data['dependencies']['@babel/code-frame']['requires']['version'] == "^75.2.1"


def test_json_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.4.1
        [bumpsemver:json(a):package.json]
        jsonpath = version
        [bumpsemver:json(b):package.json]
        jsonpath = dependencies."@babel/code-frame".version
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "75.4.1",
          "dependencies": {
            "@babel/code-frame": {
              "version": "75.4.1",
              "requires": {
                "version": "75.4.1"
              }
            }
          }
        }
    """)
    main(["minor"])
    assert "current_version = 75.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == "75.5.0"
    assert data['dependencies']['@babel/code-frame']['version'] == "75.5.0"
    assert data['dependencies']['@babel/code-frame']['requires']['version'] == "75.4.1"


def test_json_file_with_suffix_complex(tmpdir, json_keyword):
    tmpdir.join("file2").write('{"version": "5.10.2"}')
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 5.10.2
        new_version: 5.10.8
        [bumpsemver:%s:file2]
        jsonpath: version
        """ % json_keyword).strip())
    tmpdir.chdir()
    main(["patch"])

    assert "5.10.8" in tmpdir.join("file2").read()


def test_json_file_incl_array(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.6.1
        [bumpsemver:json:package.json]
        jsonpath = dependencies[1].*.version
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "75.6.1",
          "dependencies": [
            {
              "@babel/code-frame": {
                "version": "75.6.1"
              }
            },
            {
              "@babel/highlight": {
                "version": "75.6.1"
              }
            }
          ]
        }
    """)
    main(["minor"])
    assert "current_version = 75.7.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == "75.6.1"
    assert data['dependencies'][0]['@babel/code-frame']['version'] == "75.6.1"
    assert data['dependencies'][1]['@babel/highlight']['version'] == "75.7.0"


def test_json_file_key_does_not_exist(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.8.1
        [bumpsemver:json:package.json]
        jsonpath = version_foo_bar
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "75.8.1"
        }
    """)

    with pytest.raises(exceptions.VersionNotFoundException,
                       match="Did not find '75.8.1' at jsonpath 'version_foo_bar' in file: 'package.json'"):
        main(["minor"])

    assert "current_version = 75.8.1" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == "75.8.1"


def test_json_file_key_exists_but_wrong_value(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 75.10.1
        [bumpsemver:json:package.json]
        jsonpath = version
        """).strip())
    tmpdir.join("package.json").write("""
        {
          "version": "^75.10.1"
        }
    """)

    with pytest.raises(exceptions.VersionNotFoundException, match="Did not find '75.10.1' at jsonpath 'version' in file: 'package.json'"):
        main(["minor"])

    assert "current_version = 75.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == "^75.10.1"


def test_json_file_info_logging(tmpdir):
    tmpdir.join("fileJ").write(dedent("""
        {
          "version": "0.4.0"
        }
        """).strip())
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpsemver]
        current_version = 0.4.0

        [bumpsemver:json:fileJ]
        jsonpath = version
        """).strip())

    with LogCapture() as log_capture:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:json:fileJ]\njsonpath = version"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=4, patch=1"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=4, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.4.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileJ contain the version string..."),
        ("bumpsemver.files.json", "INFO", "Changing json file fileJ:"),
        ("bumpsemver.files.json", "INFO",
         "--- a/fileJ\n+++ b/fileJ\n@@ -1,3 +1,3 @@\n {\n-  \"version\": \"0.4.0\"\n+  \"version\": \"0.4.1\"\n }"),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO", "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:json:fileJ]\njsonpath = version\n\n")
    )
