from textwrap import dedent

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main


@pytest.fixture(
    params=[
        {
            "section_header": "bumpsemver:plaintext:file131.json",
            "error": "Wrong file type 'plaintext' specified for file file131.json, please use 'json' instead",
        },
        {
            "section_header": "bumpsemver:file:file131.json",
            "error": "Wrong file type 'file' specified for file file131.json, please use 'json' instead",
        },
        {
            "section_header": "bumpsemver:plaintext:file131.yml",
            "error": "Wrong file type 'plaintext' specified for file file131.yml, please use 'yaml' instead",
        },
        {
            "section_header": "bumpsemver:file:file131.yml",
            "error": "Wrong file type 'file' specified for file file131.yml, please use 'yaml' instead",
        },
        {
            "section_header": "bumpsemver:plaintext:file131.yaml",
            "error": "Wrong file type 'plaintext' specified for file file131.yaml, please use 'yaml' instead",
        },
        {
            "section_header": "bumpsemver:file:file131.yaml",
            "error": "Wrong file type 'file' specified for file file131.yaml, please use 'yaml' instead",
        },
        {
            "section_header": "bumpsemver:plaintext:file131.toml",
            "error": "Wrong file type 'plaintext' specified for file file131.toml, please use 'toml' instead",
        },
        {
            "section_header": "bumpsemver:file:file131.toml",
            "error": "Wrong file type 'file' specified for file file131.toml, please use 'toml' instead",
        },
    ]
)
def mismatched_file_type(request):
    return request.param


def test_section_config_unknown_type(tmpdir, mismatched_file_type):
    tmpdir.chdir()
    tmpdir.join("file131").write("131.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 131.10.2
            [%s]
            """
            % mismatched_file_type["section_header"]
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "current_version = 131.10.2" in tmpdir.join(".bumpsemver.cfg").read()
    log_capture.check_present(("bumpsemver.cli", "ERROR", mismatched_file_type["error"]))
    assert exc.value.code == 4


@pytest.fixture(
    params=[
        {
            "filename": "file132.json",
            "original_content": '{"version": "release: v132.10.2"}',
            "expected_content": '{"version": "release: v132.10.3"}',
        },
        {
            "filename": "file132.yml",
            "original_content": 'version: "release: v132.10.2"',
            "expected_content": 'version: "release: v132.10.3"',
        },
        {
            "filename": "file132.toml",
            "original_content": 'version = "release: v132.10.2"',
            "expected_content": 'version = "release: v132.10.3"',
        },
        {
            "filename": "file132.txt",
            "original_content": "release: v132.10.2",
            "expected_content": "release: v132.10.3",
        },
    ]
)
def override_file_type(request):
    return request.param


def test_section_config_override_type(tmpdir, override_file_type):
    tmpdir.chdir()
    tmpdir.join(override_file_type["filename"]).write(override_file_type["original_content"])
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 132.10.2
            [bumpsemver:plaintext!:%s]
            search = release: v{current_version}
            replace = release: v{new_version}
            """
            % override_file_type["filename"]
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "current_version = 132.10.3" in tmpdir.join(".bumpsemver.cfg").read()
    assert tmpdir.join(override_file_type["filename"]).read() == override_file_type["expected_content"]
    log_capture.check_present(
        (
            "bumpsemver.config",
            "WARNING",
            f"Section [bumpsemver:plaintext!:{override_file_type['filename']}] bypasses file type detection",
        )
    )
    assert exc.value.code == 0


def test_section_config_override_json(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file133.toml").write('{\n  "version": "133.10.2"\n}\n')
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 133.10.2
            [bumpsemver:json!:file133.toml]
            jsonpath = version
            """
        ).strip()
    )

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "current_version = 133.10.3" in tmpdir.join(".bumpsemver.cfg").read()
    assert tmpdir.join("file133.toml").read() == '{\n  "version": "133.10.3"\n}\n'
    log_capture.check_present(
        ("bumpsemver.config", "WARNING", f"Section [bumpsemver:json!:file133.toml] bypasses file type detection")
    )
    assert exc.value.code == 0
