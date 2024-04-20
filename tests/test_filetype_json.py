import json
from textwrap import dedent

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main
from bumpsemver.files.json import ConfiguredJSONFile
from bumpsemver.version_part import VersionConfig


def test_json_file_simple_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.0.1
            [bumpsemver:json:package.json]
            """
        ).strip()
    )
    tmpdir.join("package.json").write('{"version": "75.0.1"}')
    with pytest.raises(SystemExit) as exc:
        main(["minor"])
    assert "current_version = 75.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["version"] == "75.1.0"
    assert exc.value.code == 0


def test_json_file_simple_non_default(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.0.1
            [bumpsemver:json:package.json]
            jsonpath = release
            """
        ).strip()
    )
    tmpdir.join("package.json").write('{"release": "75.0.1"}')
    with pytest.raises(SystemExit) as exc:
        main(["minor"])
    assert "current_version = 75.1.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["release"] == "75.1.0"
    assert exc.value.code == 0


def test_json_file_exact_path(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.2.1
            [bumpsemver:json:package.json]
            jsonpath = version
            """
        ).strip()
    )
    tmpdir.join("package.json").write(
        """
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
        """
    )
    with pytest.raises(SystemExit) as exc:
        (main(["minor"]))
    assert "current_version = 75.3.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["version"] == "75.3.0"
    assert data["dependencies"]["@babel/code-frame"]["version"] == "75.2.1"
    assert data["dependencies"]["@babel/code-frame"]["requires"]["version"] == "^75.2.1"
    assert exc.value.code == 0


def test_json_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.4.1
            [bumpsemver:json(a):package.json]
            jsonpath = version
            [bumpsemver:json(b):package.json]
            jsonpath = dependencies."@babel/code-frame".version
            """
        ).strip()
    )
    tmpdir.join("package.json").write(
        """
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
        """
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])
    assert "current_version = 75.5.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["version"] == "75.5.0"
    assert data["dependencies"]["@babel/code-frame"]["version"] == "75.5.0"
    assert data["dependencies"]["@babel/code-frame"]["requires"]["version"] == "75.4.1"
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        "json",
        "json(suffix)",
        "json (suffix with space)",
        "json (suffix lacking closing paren",
    ]
)
def json_keyword(request):
    """Return multiple possible styles for the bumpsemver:json keyword."""
    return request.param


def test_type_keyword_with_suffix_is_accepted(tmpdir, json_keyword):
    tmpdir.join("file2").write('{"version": "5.10.2"}')
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 5.10.2
            new_version = 5.10.8
            [bumpsemver:%s:file2]
            jsonpath: version
            """
            % json_keyword
        ).strip()
    )
    tmpdir.chdir()
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    cfg_expected = dedent(
        """[bumpsemver]
current_version = 5.10.8

[bumpsemver:%s:file2]
jsonpath = version
"""
        % json_keyword
    )

    assert "5.10.8" in tmpdir.join("file2").read()
    assert tmpdir.join(".bumpsemver.cfg").read() == cfg_expected
    assert exc.value.code == 0


def test_json_file_incl_array(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.6.1
            [bumpsemver:json:package.json]
            jsonpath = dependencies[1].*.version
            """
        ).strip()
    )
    tmpdir.join("package.json").write(
        """
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
        """
    )
    with pytest.raises(SystemExit) as exc:
        main(["minor"])

    assert "current_version = 75.7.0" in tmpdir.join(".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data["version"] == "75.6.1"
    assert data["dependencies"][0]["@babel/code-frame"]["version"] == "75.6.1"
    assert data["dependencies"][1]["@babel/highlight"]["version"] == "75.7.0"
    assert exc.value.code == 0


def test_json_file_info_logging(tmpdir):
    tmpdir.join("fileJ").write(
        dedent(
            """
        {
          "version": "0.4.0"
        }
        """
        ).strip()
    )
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.4.0

            [bumpsemver:json:fileJ]
            jsonpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.config", "INFO", "Reading config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.4.0\n\n[bumpsemver:json:fileJ]\njsonpath = version",
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
        ("bumpsemver.git", "WARNING", "'git ls-files' failed. Listing files without respecting '.gitignore'"),
        ("bumpsemver.cli", "INFO", "Asserting files fileJ contain the version string..."),
        ("bumpsemver.files.json", "INFO", "Changing json file fileJ:"),
        (
            "bumpsemver.files.json",
            "INFO",
            '--- a/fileJ\n+++ b/fileJ\n@@ -1,3 +1,3 @@\n {\n-  "version": "0.4.0"\n+  "version": "0.4.1"\n }',
        ),
        ("bumpsemver.config", "INFO", "Writing to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.4.1\n\n[bumpsemver:json:fileJ]\njsonpath = version\n\n",
        ),
    )
    assert "current_version = 0.4.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 0


def test_repr():
    file = ConfiguredJSONFile("fileK", VersionConfig(), None, None)
    assert repr(file) == "<bumpsemver.files.ConfiguredJSONFile:fileK>"


def test_file_not_found(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 99.5.1
            [bumpsemver:json:sample.json]
            jsonpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample.json'"),
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
            current_version = 99.6.1
            [bumpsemver:json:sample1.json]
            jsonpath = version
            [bumpsemver:json:sample2.json]
            jsonpath = version
            """
        ).strip()
    )
    tmpdir.join("sample1.json").write('{"version": "99.6.1"}')

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        ("bumpsemver.cli", "ERROR", "FileNotFound. [Errno 2] No such file or directory: 'sample2.json'"),
        order_matters=False,
    )
    assert "current_version = 99.6.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert exc.value.code == 2


@pytest.fixture(
    params=[
        """
        [bumpsemver]
        current_version = 0.13
        new_version = 0.14
        [bumpsemver:json:file103.json]
        jsonpath = version
        """,
        """
        [bumpsemver]
        current_version = 0.13.pre-SNAPSHOT
        new_version = 0.14.pre-SNAPSHOT
        [bumpsemver:json:file103.json]
        jsonpath = version
        """,
    ]
)
def wrong_version_pattern_in_cfg(request):
    return request.param


def test_wrong_version_pattern_in_cfg(tmpdir, wrong_version_pattern_in_cfg):
    cfg = dedent(wrong_version_pattern_in_cfg).strip()
    tmpdir.join("file103.json").write('{"version": "0.13"}')
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.chdir()
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

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


def test_invalid_file(tmpdir):
    tmpdir.chdir()
    cfg = dedent(
        """
        [bumpsemver]
        current_version = 1.13.1
        [bumpsemver:json:file105.json]
        jsonpath = version
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file105.json").write("version = 1.13.1")
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "File file105.json cannot be parsed as a valid json file",
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
        current_version = 4.13.1
        [bumpsemver:json:file108.json]
        jsonpath = release
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file108.json").write('{"version": {"release": "4.13.1"}}')
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector 'release' does not lead to a valid property in json file file108.json",
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
        current_version = 5.13.1
        [bumpsemver:json:file109.json]
        jsonpath = "}](!'
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(cfg)
    tmpdir.join("file109.json").write('{"version": {"release": "5.13.1"}}')
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Selector '\"}](!'' does not lead to a valid property in json file file109.json",
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
            [bumpsemver:json:package.json]
            jsonpath = version
            """
        ).strip()
    )
    tmpdir.join("package.json").write('{"version": "^86.10.1"}')

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["minor"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            f"Selector 'version' finds value '^86.10.1' "
            f"mismatches with the expectation '86.10.1' in json file package.json",
        ),
        order_matters=False,
    )

    assert "current_version = 86.10.1" in tmpdir.join(".bumpsemver.cfg").read()
    assert '{"version": "^86.10.1"}' in tmpdir.join("package.json").read()
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        # partial match (the last element mismatches, child element as an array)
        {
            "file": """
                {
                    "release": [{"version": "103.11.1"}, {"version": "103.11.1"}, {"child": {"version": "103.11.1"}}]
                }
                """,
            "path": "release[*].version",
            "expected": """
                {
                    "release": [{"version": "103.12.0"}, {"version": "103.12.0"}, {"child": {"version": "103.11.1"}}]
                }
                """,
            "version_before": "103.11.1",
            "version_after": "103.12.0",
        },
        # partial match (the last element mismatches, root is an array)
        {
            "file": '[{"version": "104.11.1"}, {"version": "104.11.1"}, {"child": {"version": "104.11.1"}}]',
            "path": "[*].version",
            "expected": '[{"version": "104.12.0"}, {"version": "104.12.0"}, {"child": {"version": "104.11.1"}}]',
            "version_before": "104.11.1",
            "version_after": "104.12.0",
        },
        # partial match (the fist element mismatches)
        {
            "file": '[{"child": {"version": "105.11.1"}}, {"version": "105.11.1"}, {"version": "105.11.1"}]',
            "path": "[*].version",
            "expected": '[{"child": {"version": "105.11.1"}}, {"version": "105.12.0"}, {"version": "105.12.0"}]',
            "version_before": "105.11.1",
            "version_after": "105.12.0",
        },
        # partial match (a middle element mismatches)
        {
            "file": '[{"version": "106.11.1"}, {"child": {"version": "106.11.1"}}, {"version": "106.11.1"}]',
            "path": "[*].version",
            "expected": '[{"version": "106.12.0"}, {"child": {"version": "106.11.1"}}, {"version": "106.12.0"}]',
            "version_before": "106.11.1",
            "version_after": "106.12.0",
        },
        # full match
        {
            "file": '[{"version": "107.11.1"}, {"version": "107.11.1"}, {"version": "107.11.1"}]',
            "path": "[*].version",
            "expected": '[{"version": "107.12.0"}, {"version": "107.12.0"}, {"version": "107.12.0"}]',
            "version_before": "107.11.1",
            "version_after": "107.12.0",
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
            [bumpsemver:json:test103.json]
            jsonpath = %s
            """
            % (array_positive["version_before"], array_positive["path"])
        ).strip()
    )
    tmpdir.join("test103.json").write(dedent(array_positive["file"]).strip())
    with pytest.raises(SystemExit) as exc:
        main(["minor"])
    expected = dedent(array_positive["expected"]).strip()
    assert f"current_version = {array_positive['version_after']}" in tmpdir.join(".bumpsemver.cfg").read()
    actual_obj = json.dumps(json.loads(tmpdir.join("test103.json").read()), sort_keys=True)
    expected_obj = json.dumps(json.loads(expected), sort_keys=True)
    assert actual_obj == expected_obj
    assert exc.value.code == 0


@pytest.fixture(
    params=[
        # partial match, the last element mismatched
        {
            "version": "108.11.1",
            "file": '[{"version": "108.11.1"}, {"version": "108.11.1"}, {"version": "108.11.0"}]',
            "error": f"Selector '[*].version' finds list of values ['108.11.1', '108.11.1', '108.11.0'] "
            f"with one more more elements mismatch with the expectation '108.11.1' in json file test108.json",
        },
        # partial match, the first element mismatched
        {
            "version": "109.11.1",
            "file": '[{"version": "109.11.0"}, {"version": "109.11.1"}, {"version": "109.11.1"}]',
            "error": f"Selector '[*].version' finds list of values ['109.11.0', '109.11.1', '109.11.1'] "
            f"with one more more elements mismatch with the expectation '109.11.1' in json file test108.json",
        },
        # partial match, a middle element mismatched
        {
            "version": "110.11.1",
            "file": '[{"version": "110.11.1"}, {"version": "110.11.0"}, {"version": "110.11.1"}]',
            "error": f"Selector '[*].version' finds list of values ['110.11.1', '110.11.0', '110.11.1'] "
            f"with one more more elements mismatch with the expectation '110.11.1' in json file test108.json",
        },
        # full mismatch
        {
            "version": "111.11.1",
            "file": '[{"version": "111.11.2"}, {"version": "111.11.3"}, {"version": "111.11.4"}]',
            "error": f"Selector '[*].version' finds list of values ['111.11.2', '111.11.3', '111.11.4'] "
            f"with one more more elements mismatch with the expectation '111.11.1' in json file test108.json",
        },
        # locator finds nothing
        {
            "version": "112.11.1",
            "file": '[{"version2": "112.11.1"}, {"version3": "112.11.1"}, {"version4": "112.11.1"}]',
            "error": "Selector '[*].version' does not lead to a valid property in json file test108.json",
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
        [bumpsemver:json:test108.json]
        jsonpath = [*].version
        """
        % array_negative["version"]
    ).strip()
    orig_file = dedent(array_negative["file"]).strip()

    tmpdir.join(".bumpsemver.cfg").write(orig_cfg)
    tmpdir.join("test108.json").write(orig_file)

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
    assert tmpdir.join("test108.json").read() == orig_file
    assert exc.value.code == 4
