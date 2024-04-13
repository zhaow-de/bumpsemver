import pytest

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

    with pytest.raises(VersionNotFoundError) as ex:
        file.should_contain_version(unknown_version, context)

    assert "VersionNotFoundError" == ex.typename
    assert "Did not find 'Version: 1.2.3' in file: 'file1'" in str(ex.value)

    known_version = vc.parse("75.0.1")
    try:
        file.should_contain_version(known_version, context)
    except VersionNotFoundError:
        pytest.fail("should_contain_version() raised VersionNotFoundException unexpectedly!")


def test_repr():
    file = ConfiguredPlainTextFile("file2", None)
    assert repr(file) == "<bumpsemver.files.ConfiguredPlainTextFile:file2>"
