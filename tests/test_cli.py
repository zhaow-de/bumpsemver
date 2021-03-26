import argparse
import json
import logging
import os
import subprocess
import warnings
from configparser import RawConfigParser
from datetime import datetime
from functools import partial
from shlex import split as shlex_split
from textwrap import dedent
from unittest import mock

# noinspection PyPackageRequirements
import pytest
# noinspection PyPackageRequirements
from testfixtures import LogCapture

import bumpsemver
from bumpsemver import exceptions
from bumpsemver.cli import DESCRIPTION, main, \
    split_args_in_optional_and_positional


def _get_subprocess_env():
    return os.environ.copy()


SUBPROCESS_ENV = _get_subprocess_env()
call = partial(subprocess.call, env=SUBPROCESS_ENV, shell=True)
check_call = partial(subprocess.check_call, env=SUBPROCESS_ENV)
check_output = partial(subprocess.check_output, env=SUBPROCESS_ENV)

COMMIT = "[bumpversion]\ncommit = True"
COMMIT_NOT_TAG = "[bumpversion]\ncommit = True\ntag = False"


@pytest.fixture(params=[
    "file",
    "file(suffix)",
    "file (suffix with space)",
    "file (suffix lacking closing paren",
])
def file_keyword(request):
    """Return multiple possible styles for the bumpversion:file keyword."""
    return request.param


@pytest.fixture(params=[
    "json",
    "json(suffix)",
    "json (suffix with space)",
    "json (suffix lacking closing paren",
])
def json_keyword(request):
    """Return multiple possible styles for the bumpversion:json keyword."""
    return request.param


RawConfigParser(empty_lines_in_values=False)


def _mock_calls_to_string(called_mock):
    return ["{}|{}|{}".format(
        name,
        args[0] if len(args) > 0 else args,
        repr(kwargs) if len(kwargs) > 0 else ""
    ) for name, args, kwargs in called_mock.mock_calls]


EXPECTED_OPTIONS = r"""
[-h]
[--config-file FILE]
[--verbose]
[--allow-dirty]
[--search SEARCH]
[--replace REPLACE]
[--current-version VERSION]
[--dry-run]
--new-version VERSION
[--commit | --no-commit]
[--tag | --no-tag]
[--sign-tags | --no-sign-tags]
[--tag-name TAG_NAME]
[--tag-message TAG_MESSAGE]
[--message COMMIT_MSG]
part
[file [file ...]]
""".strip().splitlines()

EXPECTED_USAGE = (r"""

%s

positional arguments:
  part                  Part of the version to be bumped.
  file                  Files to change (default: [])

optional arguments:
  -h, --help            show this help message and exit
  --config-file FILE    Config file to read most of the variables from
                        (default: .bumpsemver.cfg)
  --verbose             Print verbose logging to stderr (default: 0)
  --allow-dirty         Don't abort if working directory is dirty (default:
                        False)
  --search SEARCH       Template for complete string to search (default:
                        {current_version})
  --replace REPLACE     Template for complete string to replace (default:
                        {new_version})
  --current-version VERSION
                        Version that needs to be updated (default: None)
  --dry-run             Don't write any files, just pretend. (default: False)
  --new-version VERSION
                        New version that should be in the files (default:
                        None)
  --commit              Commit to version control (default: False)
  --no-commit           Do not commit to version control
  --tag                 Create a tag in version control (default: False)
  --no-tag              Do not create a tag in version control
  --sign-tags           Sign tags if created (default: False)
  --no-sign-tags        Do not sign tags if created
  --tag-name TAG_NAME   Tag name (only works with --tag) (default:
                        r{new_version})
  --tag-message TAG_MESSAGE
                        Tag message (default: [OPS] bumped version:
                        {current_version} → {new_version})
  --message COMMIT_MSG  Commit message (default: [OPS] bumped version:
                        {current_version} → {new_version})
""" % DESCRIPTION).lstrip()


def test_usage_string(tmpdir, capsys):
    tmpdir.chdir()

    with pytest.raises(SystemExit):
        main(['--help'])

    out, err = capsys.readouterr()
    assert err == ""

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, "Usage string is missing {}".format(
            option_line)

    assert EXPECTED_USAGE in out


def test_regression_help_in_work_dir(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("1.7.2013")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "r1.7.2013"])

    with pytest.raises(SystemExit):
        main(['--help'])

    out, err = capsys.readouterr()

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, "Usage string is missing {}".format(
            option_line)

    assert "Version that needs to be updated (default: 1.7.2013)" in out


def test_defaults_in_usage_with_config(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("my_defaults.cfg").write("""[bumpversion]
current_version: 18
new_version: 19
[bumpversion:file:file1]
[bumpversion:file:file2]
[bumpversion:file:file3]""")
    with pytest.raises(SystemExit):
        main(['--config-file', 'my_defaults.cfg', '--help'])

    out, err = capsys.readouterr()

    assert "Version that needs to be updated (default: 18)" in out
    assert "New version that should be in the files (default: 19)" in out
    assert "[--current-version VERSION]" in out
    assert "[--new-version VERSION]" in out
    assert "[file [file ...]]" in out


def test_missing_explicit_config_file(tmpdir):
    tmpdir.chdir()
    with pytest.raises(argparse.ArgumentTypeError):
        main(['--config-file', 'missing.cfg'])


def test_simple_replacement(tmpdir):
    tmpdir.join("VERSION").write("1.2.0")
    tmpdir.chdir()
    main(shlex_split(
        "patch --current-version 1.2.0 --new-version 1.2.1 VERSION"))
    assert "1.2.1" == tmpdir.join("VERSION").read()


def test_simple_replacement_in_utf8_file(tmpdir):
    tmpdir.join("VERSION").write("Kröt1.3.0".encode(), 'wb')
    tmpdir.chdir()
    tmpdir.join("VERSION").read('rb')
    main(shlex_split(
        "patch --verbose --current-version 1.3.0 --new-version 1.3.1 VERSION"))
    out = tmpdir.join("VERSION").read('rb')
    assert "'Kr\\xc3\\xb6t1.3.1'" in repr(out)


def test_config_file(tmpdir):
    tmpdir.join("file1").write("0.9.34")
    tmpdir.join("my_bump_config.cfg").write("""[bumpversion]
current_version: 0.9.34
new_version: 0.9.35
[bumpversion:file:file1]""")

    tmpdir.chdir()
    main(shlex_split("patch --config-file my_bump_config.cfg"))

    assert "0.9.35" == tmpdir.join("file1").read()


def test_default_config_files(tmpdir):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version: 0.10.2
new_version: 0.10.3
[bumpversion:file:file2]""")

    tmpdir.chdir()
    main(['patch'])

    assert "0.10.3" == tmpdir.join("file2").read()


def test_file_keyword_with_suffix_is_accepted(tmpdir, file_keyword):
    tmpdir.join("file2").write("0.10.2")
    tmpdir.join(".bumpsemver.cfg").write(
        """[bumpversion]
    current_version: 0.10.2
    new_version: 0.10.3
    [bumpversion:%s:file2]
    """ % file_keyword
    )

    tmpdir.chdir()
    main(['patch'])

    assert "0.10.3" == tmpdir.join("file2").read()


def test_config_file_is_updated(tmpdir):
    tmpdir.join("file3").write("0.0.13")
    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version: 0.0.13
new_version: 0.0.14
[bumpversion:file:file3]""")

    tmpdir.chdir()
    main(['patch', '--verbose'])

    assert """[bumpversion]
current_version = 0.0.14

[bumpversion:file:file3]
""" == tmpdir.join(".bumpsemver.cfg").read()


def test_dry_run(tmpdir):
    tmpdir.chdir()

    config = """[bumpversion]
current_version = 0.12.0
tag = True
commit = True
message = DO NOT BUMP VERSIONS WITH THIS FILE
[bumpversion:file:file4]
"""

    version = "0.12.0"

    tmpdir.join("file4").write(version)
    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    check_call(["git", "add", "file4"])
    check_call(["git", "add", ".bumpsemver.cfg"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', '--dry-run'])

    assert config == tmpdir.join(".bumpsemver.cfg").read()
    assert version == tmpdir.join("file4").read()

    vcs_log = check_output(["git", "log"]).decode('utf-8')

    assert "initial commit" in vcs_log
    assert "DO NOT" not in vcs_log


def test_bump_version(tmpdir):
    tmpdir.join("file5").write("1.0.0")
    tmpdir.chdir()
    main(['patch', '--current-version', '1.0.0', 'file5'])

    assert '1.0.1' == tmpdir.join("file5").read()


def test_dirty_work_dir(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("dirty").write("i'm dirty")

    check_call(["git", "add", "dirty"])

    with pytest.raises(exceptions.WorkingDirectoryIsDirtyException):
        with LogCapture() as log_capture:
            main(['patch', '--current-version', '1', '--new-version', '2',
                  'file7'])

    log_capture.check_present(
        (
            'bumpsemver.cli',
            'WARNING',
            "Git working directory is not clean:\n"
            "A  dirty\n"
            "\n"
            "Use --allow-dirty to override this if you know what you're doing."
        )
    )


def test_force_dirty_work_dir(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("dirty2").write("i'm dirty! 1.1.1")

    check_call(["git", "add", "dirty2"])

    main([
        'patch',
        '--allow-dirty',
        '--current-version',
        '1.1.1',
        'dirty2'
    ])

    assert "i'm dirty! 1.1.2" == tmpdir.join("dirty2").read()


def test_bump_major(tmpdir):
    tmpdir.join("fileMAJORBUMP").write("4.2.8")
    tmpdir.chdir()
    main(['--current-version', '4.2.8', 'major', 'fileMAJORBUMP'])

    assert '5.0.0' == tmpdir.join("fileMAJORBUMP").read()


def test_commit_and_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("47.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', '--current-version', '47.1.1', '--commit', 'VERSION'])

    assert '47.1.2' == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert '-47.1.1' in log
    assert '+47.1.2' in log
    assert '[OPS] bumped version: 47.1.1 → 47.1.2' in log

    tag_out = check_output(['git', 'tag'])

    assert b'r47.1.2' not in tag_out

    main(['patch', '--current-version', '47.1.2', '--commit', '--tag',
          'VERSION'])

    assert '47.1.3' == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])

    tag_out = check_output(['git', 'tag'])

    assert b'r47.1.3' in tag_out


def test_commit_and_tag_with_configfile(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        """[bumpversion]\ncommit = True\ntag = True""")

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', '--current-version', '48.1.1', '--no-tag', 'VERSION'])

    assert '48.1.2' == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert '-48.1.1' in log
    assert '+48.1.2' in log
    assert '[OPS] bumped version: 48.1.1 → 48.1.2' in log

    tag_out = check_output(['git', 'tag'])

    assert b'r48.1.2' not in tag_out

    main(['patch', '--current-version', '48.1.2', 'VERSION'])

    assert '48.1.3' == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])

    tag_out = check_output(['git', 'tag'])

    assert b'r48.1.3' in tag_out


@pytest.mark.parametrize("config", [COMMIT, COMMIT_NOT_TAG])
def test_commit_and_not_tag_with_configfile(tmpdir, config):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.10.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', '--current-version', '48.10.1', 'VERSION'])

    assert '48.10.2' == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert '-48.10.1' in log
    assert '+48.10.2' in log
    assert '[OPS] bumped version: 48.10.1 → 48.10.2' in log

    tag_out = check_output(['git', 'tag'])

    assert b'v48.10.2' not in tag_out


def test_commit_explicitly_false(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version: 10.0.0
commit = False
tag = False""")

    check_call(["git", "init"])
    tmpdir.join("tracked_file").write("10.0.0")
    check_call(["git", "add", "tracked_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', 'tracked_file'])

    assert '10.0.1' == tmpdir.join("tracked_file").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")
    assert "10.0.1" not in log

    diff = check_output(["git", "diff"]).decode("utf-8")
    assert "10.0.1" in diff


def test_commit_configfile_true_cli_false_override(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version: 27.0.0
commit = True""")

    check_call(["git", "init"])
    tmpdir.join("dont_commit_file").write("27.0.0")
    check_call(["git", "add", "dont_commit_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(['patch', '--no-commit', 'dont_commit_file'])

    assert '27.0.1' == tmpdir.join("dont_commit_file").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")
    assert "27.0.1" not in log

    diff = check_output(["git", "diff"]).decode("utf-8")
    assert "27.0.1" in diff


def test_current_version_from_tag(tmpdir):
    # prepare
    tmpdir.join("update_from_tag").write("26.6.0")
    tmpdir.chdir()
    check_call(["git", "init"])
    check_call(["git", "add", "update_from_tag"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r26.6.0"])

    # don't give current-version, that should come from tag
    main(['patch', 'update_from_tag'])

    assert '26.6.1' == tmpdir.join("update_from_tag").read()


def test_current_version_from_tag_written_to_config_file(tmpdir):
    # prepare
    tmpdir.join("updated_also_in_config_file").write("14.6.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]""")

    check_call(["git", "init"])
    check_call(["git", "add", "updated_also_in_config_file"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r14.6.0"])

    # don't give current-version, that should come from tag
    main([
        'patch',
        'updated_also_in_config_file',
        '--commit',
        '--tag',
    ])

    assert '14.6.1' == tmpdir.join("updated_also_in_config_file").read()
    assert '14.6.1' in tmpdir.join(".bumpsemver.cfg").read()


def test_override_vcs_current_version(tmpdir):
    # prepare
    tmpdir.join("contains_actual_version").write("6.7.8")
    tmpdir.chdir()
    check_call(["git", "init"])
    check_call(["git", "add", "contains_actual_version"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "v6.7.8"])

    # update file
    tmpdir.join("contains_actual_version").write("7.0.0")
    check_call(["git", "add", "contains_actual_version"])

    # but forgot to tag or forgot to push --tags
    check_call(["git", "commit", "-m", "major release"])

    # if we don't give current-version here we get "AssertionError:
    # Did not find string 6.7.8 in file contains_actual_version"
    main(['patch', '--current-version', '7.0.0', 'contains_actual_version'])

    assert '7.0.1' == tmpdir.join("contains_actual_version").read()


def test_non_existing_file(tmpdir):
    tmpdir.chdir()
    with pytest.raises(IOError):
        main(shlex_split(
            "patch --current-version 1.2.0 --new-version 1.2.1 does_not_exist.txt"))


def test_non_existing_second_file(tmpdir):
    tmpdir.chdir()
    tmpdir.join("my_source_code.txt").write("1.2.3")
    with pytest.raises(IOError):
        main(shlex_split(
            "patch --current-version 1.2.3 my_source_code.txt does_not_exist2.txt"))

    # first file is unchanged because second didn't exist
    assert '1.2.3' == tmpdir.join("my_source_code.txt").read()


def test_read_version_tags_only(tmpdir):
    # prepare
    tmpdir.join("update_from_tag").write("29.6.0")
    tmpdir.chdir()
    check_call(["git", "init"])
    check_call(["git", "add", "update_from_tag"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r29.6.0"])
    check_call(["git", "commit", "--allow-empty", "-m", "a commit"])
    check_call(["git", "tag", "jenkins-deploy-my-project-2"])

    # don't give current-version, that should come from tag
    main(['patch', 'update_from_tag'])

    assert '29.6.1' == tmpdir.join("update_from_tag").read()


def test_tag_name(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("31.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main([
        'patch', '--current-version', '31.1.1', '--commit', '--tag',
        'VERSION', '--tag-name', 'ReleasedVersion-{new_version}'
    ])

    tag_out = check_output(['git', 'tag'])

    assert b'ReleasedVersion-31.1.2' in tag_out


def test_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("400.0.0")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version: 400.0.0
new_version: 401.0.0
commit: True
tag: True
message: {current_version} was old, {new_version} is new
tag_name: from-{current_version}-to-{new_version}""")

    main(['major', 'VERSION'])

    log = check_output(["git", "log", "-p"])

    assert b'400.0.0 was old, 401.0.0 is new' in log

    tag_out = check_output(['git', 'tag'])

    assert b'from-400.0.0-to-401.0.0' in tag_out


def test_unannotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.3.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main([
        'patch', '--current-version', '42.3.1', '--commit', '--tag', 'VERSION',
        '--tag-name', 'ReleasedVersion-{new_version}', '--tag-message', ''
    ])

    tag_out = check_output(['git', 'tag'])
    assert b'ReleasedVersion-42.3.2' in tag_out

    describe_out = subprocess.call(["git", "describe"])
    assert 128 == describe_out

    describe_out = subprocess.check_output(["git", "describe", "--tags"])
    assert describe_out.startswith(b'ReleasedVersion-42.3.2')


def test_annotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.4.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main([
        'patch', '--current-version', '42.4.1', '--commit', '--tag',
        'VERSION', '--tag-message', 'test {new_version}-tag']
    )
    assert '42.4.2' == tmpdir.join("VERSION").read()

    tag_out = check_output(['git', 'tag'])
    assert b'r42.4.2' in tag_out

    describe_out = subprocess.check_output(["git", "describe"])
    assert describe_out == b'r42.4.2\n'

    describe_out = subprocess.check_output(["git", "show", "r42.4.2"])
    assert describe_out.startswith(b"tag r42.4.2\n")
    assert b'test 42.4.2-tag' in describe_out


def test_vcs_describe(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.5.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main([
        'patch', '--current-version', '42.5.1', '--commit', '--tag',
        'VERSION', '--tag-message', 'test {new_version}-tag'
    ])
    assert '42.5.2' == tmpdir.join("VERSION").read()

    describe_out = subprocess.check_output(["git", "describe"])
    assert b'r42.5.2\n' == describe_out

    main([
        'patch', '--current-version', '42.5.2', '--commit', '--tag', 'VERSION',
        '--tag-name', 'ReleasedVersion-{new_version}', '--tag-message', ''
    ])
    assert '42.5.3' == tmpdir.join("VERSION").read()

    describe_only_annotated_out = subprocess.check_output(["git", "describe"])
    assert describe_only_annotated_out.startswith(b'r42.5.2-1-g')

    describe_all_out = subprocess.check_output(["git", "describe", "--tags"])
    assert b'ReleasedVersion-42.5.3\n' == describe_all_out


config_parser_handles_utf8 = True
try:
    import configparser
except ImportError:
    config_parser_handles_utf8 = False


def test_utf8_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("10.10.0")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    initial_config = """[bumpversion]
current_version = 10.10.0
commit = True
message = [{now}] [{utcnow} {utcnow:%YXX%mYY%d}]

"""
    tmpdir.join(".bumpsemver.cfg").write(initial_config)

    main(['major', 'VERSION'])

    log = check_output(["git", "log", "-p"])

    assert b'[20' in log
    assert b'] [' in log
    assert b'XX' in log
    assert b'YY' in log


def test_commit_and_tag_from_below_vcs_root(tmpdir, monkeypatch):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("30.0.3")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.mkdir("subdir")
    monkeypatch.chdir(tmpdir.join("subdir"))

    main(['major', '--current-version', '30.0.3', '--commit', '../VERSION'])

    assert '31.0.0' == tmpdir.join("VERSION").read()


def test_non_vcs_operations_if_vcs_is_not_installed(tmpdir, monkeypatch):
    monkeypatch.setenv("PATH", "")

    tmpdir.chdir()
    tmpdir.join("VERSION").write("31.0.3")

    main(['major', '--current-version', '31.0.3', 'VERSION'])

    assert '32.0.0' == tmpdir.join("VERSION").read()


def test_log_no_config_file_info_message(tmpdir):
    tmpdir.chdir()

    tmpdir.join("a_file.txt").write("1.0.0")

    with LogCapture(level=logging.INFO) as log_capture:
        main(['--verbose', '--verbose', '--current-version', '1.0.0', 'patch',
              'a_file.txt'])

    log_capture.check_present(
        ('bumpsemver.cli', 'INFO',
         'Could not read config file at .bumpsemver.cfg'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '1.0.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=1, minor=0, patch=0'),
        ('bumpsemver.cli', 'INFO', "Attempting to increment part 'patch'"),
        ('bumpsemver.cli', 'INFO',
         'Values are now: major=1, minor=0, patch=1'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '1.0.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=1, minor=0, patch=1'),
        ('bumpsemver.cli', 'INFO', "New version will be '1.0.1'"),
        ('bumpsemver.cli', 'INFO',
         'Asserting files a_file.txt contain the version string...'),
        ('bumpsemver.utils', 'INFO',
         "Found '1.0.0' in a_file.txt at line 0: 1.0.0"),
        ('bumpsemver.utils', 'INFO', 'Changing file a_file.txt:'),
        ('bumpsemver.utils', 'INFO',
         '--- a/a_file.txt\n+++ b/a_file.txt\n@@ -1 +1 @@\n-1.0.0\n+1.0.1'),
        ('bumpsemver.cli', 'INFO',
         'Would write to config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 1.0.1\n\n'),
        order_matters=True
    )


def test_log_parse_doesnt_parse_current_version(tmpdir):
    tmpdir.chdir()

    with LogCapture() as log_capture:
        main(['--verbose', '--current-version', '12', '--new-version', '13',
              'patch'])

    log_capture.check_present(
        ('bumpsemver.cli', 'INFO',
         "Could not read config file at .bumpsemver.cfg"),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '12' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'WARNING',
         "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' does not parse current version '12'"),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '13' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'WARNING',
         "Evaluating 'parse' option: '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)' does not parse current version '13'"),
        ('bumpsemver.cli', 'INFO', "New version will be '13'"),
        ('bumpsemver.cli', 'INFO',
         "Asserting files  contain the version string..."),
        ('bumpsemver.cli', 'INFO',
         "Would write to config file .bumpsemver.cfg:"),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 13\n\n'),
    )


def test_complex_info_logging(tmpdir):
    tmpdir.join("fileE").write("0.4.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpversion]
        current_version = 0.4.0
        
        [bumpversion:file:fileE]
        """).strip())

    with LogCapture() as log_capture:
        main(['patch', '--verbose'])

    log_capture.check(
        ('bumpsemver.cli', 'INFO',
         'Reading config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.4.0\n\n[bumpversion:file:fileE]'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.4.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=4, patch=0'),
        ('bumpsemver.cli', 'INFO', "Attempting to increment part 'patch'"),
        ('bumpsemver.cli', 'INFO',
         'Values are now: major=0, minor=4, patch=1'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.4.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=4, patch=1'),
        ('bumpsemver.cli', 'INFO', "New version will be '0.4.1'"),
        ('bumpsemver.cli', 'INFO',
         'Asserting files fileE contain the version string...'),
        ('bumpsemver.utils', 'INFO',
         "Found '0.4.0' in fileE at line 0: 0.4.0"),
        ('bumpsemver.utils', 'INFO', 'Changing file fileE:'),
        ('bumpsemver.utils', 'INFO',
         '--- a/fileE\n+++ b/fileE\n@@ -1 +1 @@\n-0.4.0\n+0.4.1'),
        ('bumpsemver.cli', 'INFO',
         'Writing to config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.4.1\n\n[bumpversion:file:fileE]\n\n')
    )


def test_subjunctive_dry_run_logging(tmpdir):
    tmpdir.join("dont_touch_me.txt").write("0.8.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpversion]
        current_version = 0.8.0
        commit = True
        tag = True
        [bumpversion:file:dont_touch_me.txt]
    """).strip())

    check_call(["git", "init"])
    check_call(["git", "add", "dont_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture:
        main(['patch', '--verbose', '--dry-run'])

    log_capture.check(
        ('bumpsemver.cli', 'INFO',
         'Reading config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.8.0\ncommit = True\ntag = True\n[bumpversion:file:dont_touch_me.txt]'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.8.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=8, patch=0'),
        ('bumpsemver.cli', 'INFO', "Attempting to increment part 'patch'"),
        ('bumpsemver.cli', 'INFO',
         'Values are now: major=0, minor=8, patch=1'),
        ('bumpsemver.cli', 'INFO',
         "Dry run active, won't touch any files."),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.8.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=8, patch=1'),
        ('bumpsemver.cli', 'INFO', "New version will be '0.8.1'"),
        ('bumpsemver.cli', 'INFO',
         'Asserting files dont_touch_me.txt contain the version string...'),
        ('bumpsemver.utils', 'INFO',
         "Found '0.8.0' in dont_touch_me.txt at line 0: 0.8.0"),
        ('bumpsemver.utils', 'INFO',
         'Would change file dont_touch_me.txt:'),
        (
            'bumpsemver.utils', 'INFO',
            '--- a/dont_touch_me.txt\n+++ b/dont_touch_me.txt\n@@ -1 +1 @@\n-0.8.0\n+0.8.1'),
        ('bumpsemver.cli', 'INFO',
         'Would write to config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.8.1\ncommit = True\ntag = True\n\n[bumpversion:file:dont_touch_me.txt]\n\n'),
        ('bumpsemver.cli', 'INFO', 'Would prepare Git commit'),
        ('bumpsemver.cli', 'INFO',
         "Would add changes in file 'dont_touch_me.txt' to Git"),
        ('bumpsemver.cli', 'INFO',
         "Would add changes in file '.bumpsemver.cfg' to Git"),
        ('bumpsemver.cli', 'INFO',
         "Would commit to Git with message '[OPS] bumped version: 0.8.0 \u2192 0.8.1'"),
        ('bumpsemver.cli', 'INFO',
         "Would tag 'r0.8.1' with message '[OPS] bumped version: 0.8.0 \u2192 0.8.1' in Git and not signing")
    )


def test_log_commit_message_if_no_commit_tag_but_usable_vcs(tmpdir):
    tmpdir.join("please_touch_me.txt").write("0.3.3")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 0.3.3
        commit = False
        tag = False
        [bumpversion:file:please_touch_me.txt]
        """).strip())

    check_call(["git", "init"])
    check_call(["git", "add", "please_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture:
        main(['patch', '--verbose'])

    log_capture.check(
        ('bumpsemver.cli', 'INFO',
         'Reading config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.3.3\ncommit = False\ntag = False\n[bumpversion:file:please_touch_me.txt]'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.3.3' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=3, patch=3'),
        ('bumpsemver.cli', 'INFO', "Attempting to increment part 'patch'"),
        ('bumpsemver.cli', 'INFO',
         'Values are now: major=0, minor=3, patch=4'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '0.3.4' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=0, minor=3, patch=4'),
        ('bumpsemver.cli', 'INFO', "New version will be '0.3.4'"),
        ('bumpsemver.cli', 'INFO',
         'Asserting files please_touch_me.txt contain the version string...'),
        ('bumpsemver.utils', 'INFO',
         "Found '0.3.3' in please_touch_me.txt at line 0: 0.3.3"),
        ('bumpsemver.utils', 'INFO', 'Changing file please_touch_me.txt:'),
        ('bumpsemver.utils', 'INFO',
         '--- a/please_touch_me.txt\n+++ b/please_touch_me.txt\n@@ -1 +1 @@\n-0.3.3\n+0.3.4'),
        ('bumpsemver.cli', 'INFO',
         'Writing to config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 0.3.4\ncommit = False\ntag = False\n\n[bumpversion:file:please_touch_me.txt]\n\n'),
        ('bumpsemver.cli', 'INFO', 'Would prepare Git commit'),
        ('bumpsemver.cli', 'INFO',
         "Would add changes in file 'please_touch_me.txt' to Git"),
        ('bumpsemver.cli', 'INFO',
         "Would add changes in file '.bumpsemver.cfg' to Git"),
        ('bumpsemver.cli', 'INFO',
         "Would commit to Git with message '[OPS] bumped version: 0.3.3 \u2192 0.3.4'"),
        ('bumpsemver.cli', 'INFO',
         "Would tag 'r0.3.4' with message '[OPS] bumped version: 0.3.3 \u2192 0.3.4' in Git and not signing"),
    )


def test_multi_file_configuration(tmpdir):
    tmpdir.join("FULL_VERSION.txt").write("1.0.3")
    tmpdir.join("MAJOR_VERSION.txt").write("1.0.3")

    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent(r"""
        [bumpversion]
        current_version = 1.0.3

        [bumpversion:file:FULL_VERSION.txt]

        [bumpversion:file:MAJOR_VERSION.txt]
        """))

    main(['major', '--verbose'])
    assert '2.0.0' in tmpdir.join("FULL_VERSION.txt").read()
    assert '2.0.0' in tmpdir.join("MAJOR_VERSION.txt").read()

    main(['patch'])
    assert '2.0.1' in tmpdir.join("FULL_VERSION.txt").read()
    assert '2.0.1' in tmpdir.join("MAJOR_VERSION.txt").read()


def test_search_replace_to_avoid_updating_unconcerned_lines(tmpdir):
    tmpdir.chdir()

    tmpdir.join("requirements.txt").write(
        "Django>=1.5.6,<1.6\nMyProject==1.5.6")

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
      [bumpversion]
      current_version = 1.5.6

      [bumpversion:file:requirements.txt]
      search = MyProject=={current_version}
      replace = MyProject=={new_version}
      """).strip())

    with LogCapture() as log_capture:
        main(['minor', '--verbose'])

    log_capture.check(
        ('bumpsemver.cli', 'INFO',
         'Reading config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 1.5.6\n\n[bumpversion:file:requirements.txt]\nsearch = MyProject=={current_version}\nreplace = MyProject=={new_version}'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '1.5.6' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=1, minor=5, patch=6'),
        ('bumpsemver.cli', 'INFO', "Attempting to increment part 'minor'"),
        ('bumpsemver.cli', 'INFO',
         'Values are now: major=1, minor=6, patch=0'),
        ('bumpsemver.version_part', 'INFO',
         "Parsing version '1.6.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ('bumpsemver.version_part', 'INFO',
         'Parsed the following values: major=1, minor=6, patch=0'),
        ('bumpsemver.cli', 'INFO', "New version will be '1.6.0'"),
        ('bumpsemver.cli', 'INFO',
         'Asserting files requirements.txt contain the version string...'),
        ('bumpsemver.utils', 'INFO',
         "Found 'MyProject==1.5.6' in requirements.txt at line 1: MyProject==1.5.6"),
        ('bumpsemver.utils', 'INFO', 'Changing file requirements.txt:'),
        ('bumpsemver.utils', 'INFO',
         '--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1,2 +1,2 @@\n Django>=1.5.6,<1.6\n-MyProject==1.5.6\n+MyProject==1.6.0'),
        ('bumpsemver.cli', 'INFO',
         'Writing to config file .bumpsemver.cfg:'),
        ('bumpsemver.cli', 'INFO',
         '[bumpversion]\ncurrent_version = 1.6.0\n\n[bumpversion:file:requirements.txt]\nsearch = MyProject=={current_version}\nreplace = MyProject=={new_version}\n\n')
    )

    assert 'MyProject==1.6.0' in tmpdir.join("requirements.txt").read()
    assert 'Django>=1.5.6' in tmpdir.join("requirements.txt").read()


def test_search_replace_expanding_changelog(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGELOG.md").write(dedent("""
    My awesome software project Changelog
    =====================================

    Unreleased
    ----------

    * Some nice feature
    * Some other nice feature

    Version v8.1.1 (2014-05-28)
    ---------------------------

    * Another old nice feature

    """))

    config_content = dedent("""
      [bumpversion]
      current_version = 8.1.1

      [bumpversion:file:CHANGELOG.md]
      search =
        Unreleased
        ----------
      replace =
        Unreleased
        ----------
        Version v{new_version} ({now:%Y-%m-%d})
        ---------------------------
    """)

    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with mock.patch("bumpsemver.cli.logger"):
        main(['minor', '--verbose'])

    predate = dedent('''
      Unreleased
      ----------
      Version v8.2.0 (20
      ''').strip()

    postdate = dedent('''
      )
      ---------------------------

      * Some nice feature
      * Some other nice feature
      ''').strip()

    assert predate in tmpdir.join("CHANGELOG.md").read()
    assert postdate in tmpdir.join("CHANGELOG.md").read()


def test_non_matching_search_does_not_modify_file(tmpdir):
    tmpdir.chdir()

    changelog_content = dedent("""
    # Unreleased
    
    * bullet point A
    
    # Release v'older' (2019-09-17)
    
    * bullet point B
    """)

    config_content = dedent("""
      [bumpversion]
      current_version = 1.0.3

      [bumpversion:file:CHANGELOG.md]
      search = Not-yet-released
      replace = Release v{new_version} ({now:%Y-%m-%d})
    """)

    tmpdir.join("CHANGELOG.md").write(changelog_content)
    tmpdir.join(".bumpsemver.cfg").write(config_content)

    with pytest.raises(
            exceptions.VersionNotFoundException,
            match="Did not find 'Not-yet-released' in file: 'CHANGELOG.md'"
    ):
        main(['patch', '--verbose'])

    assert changelog_content == tmpdir.join("CHANGELOG.md").read()
    assert config_content in tmpdir.join(".bumpsemver.cfg").read()


def test_search_replace_cli(tmpdir):
    tmpdir.join("file89").write("My birthday: 3.5.98\nCurrent version: 3.5.98")
    tmpdir.chdir()
    main([
        '--current-version', '3.5.98',
        '--search', 'Current version: {current_version}',
        '--replace', 'Current version: {new_version}',
        'minor',
        'file89',
    ])

    assert 'My birthday: 3.5.98\nCurrent version: 3.6.0' == tmpdir.join(
        "file89").read()


def test_deprecation_warning_files_in_global_configuration(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileX").write("3.2.1")
    tmpdir.join("fileY").write("3.2.1")
    tmpdir.join("fileZ").write("3.2.1")

    tmpdir.join(".bumpsemver.cfg").write("""[bumpversion]
current_version = 3.2.1
files = fileX fileY fileZ
""")

    warning_registry = getattr(bumpsemver, '__warningregistry__', None)
    if warning_registry:
        warning_registry.clear()
    warnings.resetwarnings()
    warnings.simplefilter('always')
    with warnings.catch_warnings(record=True) as received_warnings:
        main(['patch'])

    w = received_warnings.pop()
    assert issubclass(w.category, PendingDeprecationWarning)
    assert "'files =' configuration will be deprecated, please use" in str(
        w.message)


def test_deprecation_warning_multiple_files_cli(tmpdir):
    tmpdir.chdir()

    tmpdir.join("fileA").write("1.2.3")
    tmpdir.join("fileB").write("1.2.3")
    tmpdir.join("fileC").write("1.2.3")

    warning_registry = getattr(bumpsemver, '__warningregistry__', None)
    if warning_registry:
        warning_registry.clear()
    warnings.resetwarnings()
    warnings.simplefilter('always')
    with warnings.catch_warnings(record=True) as received_warnings:
        main(['--current-version', '1.2.3', 'patch', 'fileA', 'fileB', 'fileC'])

    w = received_warnings.pop()
    assert issubclass(w.category, PendingDeprecationWarning)
    assert 'Giving multiple files on the command line will be deprecated' in str(
        w.message)


def test_multi_line_search_is_found(tmpdir):
    tmpdir.chdir()

    tmpdir.join("the_alphabet.txt").write(dedent("""
      A
      B
      C
    """))

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpversion]
    current_version = 9.8.7

    [bumpversion:file:the_alphabet.txt]
    search =
      A
      B
      C
    replace =
      A
      B
      C
      {new_version}
      """).strip())

    main(['major'])

    assert dedent("""
      A
      B
      C
      10.0.0
    """) == tmpdir.join("the_alphabet.txt").read()


def test_configparser_empty_lines_in_values(tmpdir):
    tmpdir.chdir()

    tmpdir.join("CHANGES.rst").write(dedent("""
    My changelog
    ============

    current
    -------

    """))

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpversion]
    current_version = 0.4.1

    [bumpversion:file:CHANGES.rst]
    search =
      current
      -------
    replace = current
      -------


      {new_version}
      -------
      """).strip())

    main(['patch'])
    assert dedent("""
      My changelog
      ============
      current
      -------


      0.4.2
      -------

    """) == tmpdir.join("CHANGES.rst").read()


def test_regression_tag_name_with_hyphens(tmpdir):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("2014.10.22")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "very-unrelated-but-containing-lots-of-hyphens"])

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpversion]
    current_version = 2014.10.22
    """))

    main(['patch', 'some_source.txt'])


def test_unclean_repo_exception(tmpdir, caplog):
    tmpdir.chdir()

    config = """[bumpversion]
current_version = 0.0.0
tag = True
commit = True
message = XXX
"""

    tmpdir.join("file1").write("foo")

    # If I have a repo with an initial commit
    check_call(["git", "init"])
    check_call(["git", "add", "file1"])
    check_call(["git", "commit", "-m", "initial commit"])

    # If I add the bumpversion config, uncommitted
    tmpdir.join(".bumpsemver.cfg").write(config)

    # I expect bumpversion patch to fail
    with pytest.raises(subprocess.CalledProcessError):
        main(['patch'])

    # And return the output of the failing command
    assert "Failed to run" in caplog.text


def test_regression_dont_touch_capitalization_of_keys_in_config(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpversion]
    current_version = 0.1.0

    [other]
    DJANGO_SETTINGS = Value
    """))

    main(['patch'])

    assert dedent("""
    [bumpversion]
    current_version = 0.1.1

    [other]
    DJANGO_SETTINGS = Value
    """).strip() == tmpdir.join(".bumpsemver.cfg").read().strip()


def test_regression_new_version_cli_in_files(tmpdir):
    """
    Reported here: https://github.com/peritus/bumpversion/issues/60
    """
    tmpdir.chdir()
    tmpdir.join("myp___init__.py").write("__version__ = '0.7.2'")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 0.7.2
        message = v{new_version}
        tag_name = {new_version}
        tag = true
        commit = true
        [bumpversion:file:myp___init__.py]
        """).strip())

    main("patch --allow-dirty --verbose --new-version 0.9.3".split(" "))

    assert "__version__ = '0.9.3'" == tmpdir.join("myp___init__.py").read()
    assert "current_version = 0.9.3" in tmpdir.join(
        ".bumpsemver.cfg").read()


def test_correct_interpolation_for_setup_cfg_files(tmpdir):
    """
    Reported here: https://github.com/c4urself/bump2version/issues/21
    """
    tmpdir.chdir()
    tmpdir.join("file.py").write("XX-XX-XXXX v. X.X.X")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 0.7.2
        search = XX-XX-XXXX v. X.X.X
        replace = {now:%m-%d-%Y} v. {new_version}
        [bumpversion:file:file.py]
        """).strip())

    main(["major"])

    assert datetime.now().strftime('%m-%d-%Y') + ' v. 1.0.0' == tmpdir.join(
        "file.py").read()
    assert "current_version = 1.0.0" in tmpdir.join(
        ".bumpsemver.cfg").read()


def test_json_file_simple(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.0.1
        [bumpversion:json:package.json]
        version_key = version
        """).strip())
    tmpdir.join("package.json").write('''
    {
      "version": "75.0.1"
    }
    ''')
    main(['minor'])
    assert 'current_version = 75.1.0' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '75.1.0'


def test_json_file_exact_path(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.2.1
        [bumpversion:json:package.json]
        version_key = version
        """).strip())
    tmpdir.join("package.json").write('''
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
    ''')
    main(['minor'])
    assert 'current_version = 75.3.0' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '75.3.0'
    assert data['dependencies']['@babel/code-frame']['version'] == '75.2.1'
    assert data['dependencies']['@babel/code-frame']['requires'][
               'version'] == '^75.2.1'


def test_json_file_with_suffix_two(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.4.1
        [bumpversion:json(a):package.json]
        version_key = version
        [bumpversion:json(b):package.json]
        version_key = dependencies."@babel/code-frame".version
        """).strip())
    tmpdir.join("package.json").write('''
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
    ''')
    main(['minor'])
    assert 'current_version = 75.5.0' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '75.5.0'
    assert data['dependencies']['@babel/code-frame']['version'] == '75.5.0'
    assert data['dependencies']['@babel/code-frame']['requires'][
               'version'] == '75.4.1'


def test_json_file_with_suffix_complex(tmpdir, json_keyword):
    tmpdir.join("file2").write('{"version": "5.10.2"}')
    tmpdir.join(".bumpsemver.cfg").write(
        """[bumpversion]
    current_version: 5.10.2
    new_version: 5.10.8
    [bumpversion:%s:file2]
    version_key: version
    """ % json_keyword
    )

    tmpdir.chdir()
    main(['patch'])

    assert "5.10.8" in tmpdir.join("file2").read()


def test_json_file_incl_array(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.6.1
        [bumpversion:json:package.json]
        version_key = dependencies[1].*.version
        """).strip())
    tmpdir.join("package.json").write('''
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
    ''')
    main(['minor'])
    assert 'current_version = 75.7.0' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '75.6.1'
    assert data['dependencies'][0]['@babel/code-frame']['version'] == '75.6.1'
    assert data['dependencies'][1]['@babel/highlight']['version'] == '75.7.0'


def test_json_file_key_does_not_exist(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.8.1
        [bumpversion:json:package.json]
        version_key = version_foo_bar
        """).strip())
    tmpdir.join("package.json").write('''
    {
      "version": "75.8.1"
    }
    ''')

    with pytest.raises(
            exceptions.VersionNotFoundException,
            match="Did not find '75.8.1' in file: 'package.json'"
    ):
        main(['minor'])

    assert 'current_version = 75.8.1' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '75.8.1'


def test_json_file_key_exists_but_wrong_value(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpversion]
        current_version = 75.10.1
        [bumpversion:json:package.json]
        version_key = version
        """).strip())
    tmpdir.join("package.json").write('''
    {
      "version": "^75.10.1"
    }
    ''')

    with pytest.raises(
            exceptions.VersionNotFoundException,
            match="Did not find '75.10.1' in file: 'package.json'"
    ):
        main(['minor'])

    assert 'current_version = 75.10.1' in tmpdir.join(
        ".bumpsemver.cfg").read()
    data = json.loads(tmpdir.join("package.json").read())
    assert data['version'] == '^75.10.1'


@pytest.mark.parametrize("newline", [b'\n', b'\r\n'])
def test_retain_newline(tmpdir, newline):
    tmpdir.join("file.py").write_binary(dedent("""
        0.7.2
        Some Content
        """).strip().encode(encoding='UTF-8').replace(b'\n', newline))
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write_binary(dedent("""
        [bumpversion]
        current_version = 0.7.2
        search = {current_version}
        replace = {new_version}
        [bumpversion:file:file.py]
        """).strip().encode(encoding='UTF-8').replace(b'\n', newline))

    main(["major"])

    assert newline in tmpdir.join("file.py").read_binary()
    new_config = tmpdir.join(".bumpsemver.cfg").read_binary()
    assert newline in new_config

    # Ensure there is only a single newline (not two) at the end of the file
    # and that it is of the right type
    assert new_config.endswith(b"[bumpversion:file:file.py]" + newline)


class TestSplitArgsInOptionalAndPositional:

    def test_all_optional(self):
        params = ['--allow-dirty', '--verbose', '--dry-run', '--tag-name',
                  '"Tag"']
        positional, optional = \
            split_args_in_optional_and_positional(params)

        assert positional == []
        assert optional == params

    def test_all_positional(self):
        params = ['minor', 'setup.py']
        positional, optional = \
            split_args_in_optional_and_positional(params)

        assert positional == params
        assert optional == []

    def test_no_args(self):
        assert split_args_in_optional_and_positional([]) == \
               ([], [])

    def test_1optional_2positional(self):
        params = ['--dry-run', 'major', 'setup.py']
        positional, optional = \
            split_args_in_optional_and_positional(params)

        assert positional == ['major', 'setup.py']
        assert optional == ['--dry-run']

    def test_2optional_1positional(self):
        params = ['--dry-run', '--message', '"Commit"', 'major']
        positional, optional = \
            split_args_in_optional_and_positional(params)

        assert positional == ['major']
        assert optional == ['--dry-run', '--message', '"Commit"']

    def test_2optional_mixed_2positional(self):
        params = ['--allow-dirty', '--message', '"Commit"', 'minor', 'setup.py']
        positional, optional = \
            split_args_in_optional_and_positional(params)

        assert positional == ['minor', 'setup.py']
        assert optional == ['--allow-dirty', '--message', '"Commit"']
