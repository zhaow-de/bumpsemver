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
