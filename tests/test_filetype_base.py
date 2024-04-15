import logging

import pytest
from testfixtures import LogCapture

from bumpsemver.exceptions import MixedNewLineError
from bumpsemver.files.base import FileTypeBase
from bumpsemver.version_part import VersionConfig

logger = logging.getLogger(__name__)


class ConfiguredDummyFile(FileTypeBase):
    def __repr__(self):
        super().__repr__()

    def __init__(self, filename: str, version_config: VersionConfig, file_type="dummy", path: str = None):
        super().__init__(filename, version_config, file_type, path, logger)

    def should_contain_version(self, version, context):
        pass

    def contains(self, search):
        pass

    def replace(self, current_version, new_version, context, dry_run):
        pass


def test_update_no_change(tmpdir):
    tmpdir.chdir()
    #
    tmpdir.join("file1").write("Line 1\nLine 2\n")
    file = ConfiguredDummyFile("file1", VersionConfig())

    with LogCapture() as log_capture1:
        file.update_file("Line 1\nLine 2\n", "Line 1\nLine 2\n", True)

    log_capture1.check_present(
        ("tests.test_filetype_base", "INFO", "Would not change dummy file file1"), order_matters=False
    )

    with LogCapture() as log_capture2:
        file.update_file("Line 1\nLine 2\n", "Line 1\nLine 2\n", False)

    log_capture2.check_present(
        ("tests.test_filetype_base", "INFO", "Not changing dummy file file1"), order_matters=False
    )


def test_update_changed(tmpdir):
    tmpdir.chdir()
    #
    tmpdir.join("file2").write("Line 1\nLine 2\n")
    file = ConfiguredDummyFile("file2", VersionConfig())

    with LogCapture() as log_capture1:
        file.update_file("Line 1\nLine 2\n", "Line 1\nLine 3\n", True)

    log_capture1.check_present(
        ("tests.test_filetype_base", "INFO", "Would change dummy file file2:"), order_matters=False
    )
    file_content = tmpdir.join("file2").read()
    assert file_content == "Line 1\nLine 2\n"  # because it was a dry run

    with LogCapture() as log_capture2:
        file.update_file("Line 1\nLine 2\n", "Line 1\nLine 3\n", False)

    log_capture2.check_present(("tests.test_filetype_base", "INFO", "Changing dummy file file2:"), order_matters=False)
    file_content = tmpdir.join("file2").read()
    assert file_content == "Line 1\nLine 3\n"


def test_update_mixed_newlines(tmpdir):
    tmpdir.chdir()
    wf = tmpdir.join("file3")
    with open(wf, "wt", newline="") as f:
        f.write("Line 1\r\nLine 2\nLine 3\rLine 4\n\n")
    file = ConfiguredDummyFile("file3", VersionConfig())

    with pytest.raises(MixedNewLineError) as ex:
        file.update_file("Line 1\nLine 2\n", "Line 1\nLine 2\n", True)

    assert ex.typename == "MixedNewLineError"
    assert "File file3 has mixed newline characters: ('\\r', '\\n', '\\r\\n')" in str(ex.value)
