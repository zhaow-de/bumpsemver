# pylint: skip-file

import os
import subprocess
from functools import partial
from textwrap import dedent

# noinspection PyPackageRequirements
import pytest
# noinspection PyPackageRequirements
from testfixtures import LogCapture

from bumpsemver import exceptions
from bumpsemver.cli import main
from tests.test_cli import EXPECTED_OPTIONS, check_output, COMMIT, COMMIT_NOT_TAG

check_call = partial(subprocess.check_call, env=os.environ.copy())


def test_regression_help_in_work_dir(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("1.7.2013")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "r1.7.2013"])

    with pytest.raises(SystemExit):
        main(["--help"])

    out, err = capsys.readouterr()

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, f"Usage string is missing {option_line}"

    assert "Version that needs to be updated (default: 1.7.2013)" in out


def test_dirty_work_dir(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("dirty").write("i'm dirty")

    check_call(["git", "add", "dirty"])

    with pytest.raises(exceptions.WorkingDirectoryIsDirtyException):
        with LogCapture() as log_capture:
            main(["patch", "--current-version", "1", "--new-version", "2", "file7"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "WARNING",
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

    main(["patch", "--allow-dirty", "--current-version", "1.1.1", "dirty2"])

    assert "i'm dirty! 1.1.2" == tmpdir.join("dirty2").read()


def test_commit_and_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("47.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "47.1.1", "--commit", "VERSION"])

    assert "47.1.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-47.1.1" in log
    assert "+47.1.2" in log
    assert "[OPS] bumped version: 47.1.1 → 47.1.2" in log

    tag_out = check_output(["git", "tag"])

    assert b"r47.1.2" not in tag_out

    main(["patch", "--current-version", "47.1.2", "--commit", "--tag", "VERSION"])

    assert "47.1.3" == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])
    tag_out = check_output(["git", "tag"])

    assert b"r47.1.3" in tag_out


def test_commit_and_tag_with_configfile(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        commit = True
        tag = True
        """).strip())

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "48.1.1", "--no-tag", "VERSION"])

    assert "48.1.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-48.1.1" in log
    assert "+48.1.2" in log
    assert "[OPS] bumped version: 48.1.1 → 48.1.2" in log

    tag_out = check_output(["git", "tag"])

    assert b"r48.1.2" not in tag_out

    main(["patch", "--current-version", "48.1.2", "VERSION"])

    assert "48.1.3" == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])

    tag_out = check_output(["git", "tag"])

    assert b"r48.1.3" in tag_out


@pytest.mark.parametrize("config", [COMMIT, COMMIT_NOT_TAG])
def test_commit_and_not_tag_with_configfile(tmpdir, config):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.10.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "48.10.1", "VERSION"])

    assert "48.10.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-48.10.1" in log
    assert "+48.10.2" in log
    assert "[OPS] bumped version: 48.10.1 → 48.10.2" in log

    tag_out = check_output(["git", "tag"])

    assert b"v48.10.2" not in tag_out


def test_commit_explicitly_false(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 10.0.0
        commit = False
        tag = False
        """).strip())

    check_call(["git", "init"])
    tmpdir.join("tracked_file").write("10.0.0")
    check_call(["git", "add", "tracked_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "tracked_file"])

    assert "10.0.1" == tmpdir.join("tracked_file").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")
    assert "10.0.1" not in log

    diff = check_output(["git", "diff"]).decode("utf-8")
    assert "10.0.1" in diff


def test_commit_configfile_true_cli_false_override(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 27.0.0
        commit = True
        """).strip())

    check_call(["git", "init"])
    tmpdir.join("dont_commit_file").write("27.0.0")
    check_call(["git", "add", "dont_commit_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--no-commit", "dont_commit_file"])

    assert "27.0.1" == tmpdir.join("dont_commit_file").read()

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
    main(["patch", "update_from_tag"])

    assert tmpdir.join("update_from_tag").read() == "26.6.1"


def test_current_version_from_tag_written_to_config_file(tmpdir):
    # prepare
    tmpdir.join("updated_also_in_config_file").write("14.6.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write("""[bumpsemver]""")

    check_call(["git", "init"])
    check_call(["git", "add", "updated_also_in_config_file"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r14.6.0"])

    # don't give current-version, that should come from tag
    main(["patch", "updated_also_in_config_file", "--commit", "--tag"])

    assert "14.6.1" == tmpdir.join("updated_also_in_config_file").read()
    assert "14.6.1" in tmpdir.join(".bumpsemver.cfg").read()


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
    main(["patch", "--current-version", "7.0.0", "contains_actual_version"])

    assert "7.0.1" == tmpdir.join("contains_actual_version").read()


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
    main(["patch", "update_from_tag"])

    assert "29.6.1" == tmpdir.join("update_from_tag").read()


def test_tag_name(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("31.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "31.1.1", "--commit", "--tag", "VERSION", "--tag-name", "ReleasedVersion-{new_version}"])

    tag_out = check_output(["git", "tag"])

    assert b"ReleasedVersion-31.1.2" in tag_out


def test_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("400.0.0")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version: 400.0.0
        new_version: 401.0.0
        commit: True
        tag: True
        message: {current_version} was old, {new_version} is new
        tag_name: from-{current_version}-to-{new_version}
        """).strip())

    main(["major", "VERSION"])

    log = check_output(["git", "log", "-p"])

    assert b"400.0.0 was old, 401.0.0 is new" in log

    tag_out = check_output(["git", "tag"])

    assert b"from-400.0.0-to-401.0.0" in tag_out


def test_unannotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.3.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "42.3.1", "--commit", "--tag", "VERSION",
          "--tag-name", "ReleasedVersion-{new_version}", "--tag-message", ""])

    tag_out = check_output(["git", "tag"])
    assert b"ReleasedVersion-42.3.2" in tag_out

    describe_out = subprocess.call(["git", "describe"])
    assert 128 == describe_out

    describe_out = subprocess.check_output(["git", "describe", "--tags"])
    assert describe_out.startswith(b"ReleasedVersion-42.3.2")


def test_annotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.4.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "42.4.1", "--commit", "--tag", "VERSION", "--tag-message", "test {new_version}-tag"])
    assert "42.4.2" == tmpdir.join("VERSION").read()

    tag_out = check_output(["git", "tag"])
    assert b"r42.4.2" in tag_out

    describe_out = subprocess.check_output(["git", "describe"])
    assert describe_out == b"r42.4.2\n"

    describe_out = subprocess.check_output(["git", "show", "r42.4.2"])
    assert describe_out.startswith(b"tag r42.4.2\n")
    assert b"test 42.4.2-tag" in describe_out


def test_vcs_describe(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.5.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--current-version", "42.5.1", "--commit", "--tag", "VERSION", "--tag-message", "test {new_version}-tag"])
    assert "42.5.2" == tmpdir.join("VERSION").read()

    describe_out = subprocess.check_output(["git", "describe"])
    assert b"r42.5.2\n" == describe_out

    main(["patch", "--current-version", "42.5.2", "--commit", "--tag", "VERSION",
          "--tag-name", "ReleasedVersion-{new_version}", "--tag-message", ""])
    assert "42.5.3" == tmpdir.join("VERSION").read()

    describe_only_annotated_out = subprocess.check_output(["git", "describe"])
    assert describe_only_annotated_out.startswith(b"r42.5.2-1-g")

    describe_all_out = subprocess.check_output(["git", "describe", "--tags"])
    assert b"ReleasedVersion-42.5.3\n" == describe_all_out


def test_utf8_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("10.10.0")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    initial_config = dedent("""
        [bumpsemver]
        current_version = 10.10.0
        commit = True
        message = [{now}] [{utcnow} {utcnow:%YXX%mYY%d}]
        """).strip()
    tmpdir.join(".bumpsemver.cfg").write(initial_config)

    main(['major', "VERSION"])

    log = check_output(["git", "log", "-p"])

    assert b"[20" in log
    assert b"] [" in log
    assert b"XX" in log
    assert b"YY" in log


def test_commit_and_tag_from_below_vcs_root(tmpdir, monkeypatch):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("30.0.3")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.mkdir("subdir")
    monkeypatch.chdir(tmpdir.join("subdir"))

    main(["major", "--current-version", "30.0.3", "--commit", "../VERSION"])

    assert "31.0.0" == tmpdir.join("VERSION").read()


def test_subjunctive_dry_run_logging(tmpdir):
    tmpdir.join("dont_touch_me.txt").write("0.8.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 0.8.0
        commit = True
        tag = True
        [bumpsemver:file:dont_touch_me.txt]
    """).strip())

    check_call(["git", "init"])
    check_call(["git", "add", "dont_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture:
        main(["patch", "--verbose", "--dry-run"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 0.8.0\ncommit = True\ntag = True\n[bumpsemver:file:dont_touch_me.txt]"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.8.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=8, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=8, patch=1"),
        ("bumpsemver.cli", "INFO", 'Dry run active, won\'t touch any files.'),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.8.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=8, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.8.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files dont_touch_me.txt contain the version string..."),
        ("bumpsemver.files.generic", "INFO", "Found '0.8.0' in dont_touch_me.txt at line 0: 0.8.0"),
        ("bumpsemver.files.generic", "INFO", "Would change generic file dont_touch_me.txt:"),
        ("bumpsemver.files.generic", "INFO", "--- a/dont_touch_me.txt\n+++ b/dont_touch_me.txt\n@@ -1 +1 @@\n-0.8.0\n+0.8.1"),
        ("bumpsemver.cli", "INFO", "Would write to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 0.8.1\ncommit = True\ntag = True\n\n[bumpsemver:file:dont_touch_me.txt]\n\n"),
        ("bumpsemver.cli", "INFO", "Would prepare Git commit"),
        ("bumpsemver.cli", "INFO", "Would add changes in file 'dont_touch_me.txt' to Git"),
        ("bumpsemver.cli", "INFO", "Would add changes in file '.bumpsemver.cfg' to Git"),
        ("bumpsemver.cli", "INFO", "Would commit to Git with message '[OPS] bumped version: 0.8.0 \u2192 0.8.1'"),
        ("bumpsemver.cli", "INFO", "Would tag `r0.8.1` with message `[OPS] bumped version: 0.8.0 \u2192 0.8.1` in Git and not signing")
    )


def test_log_commit_message_if_no_commit_tag_but_usable_vcs(tmpdir):
    tmpdir.join("please_touch_me.txt").write("0.3.3")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
        [bumpsemver]
        current_version = 0.3.3
        commit = False
        tag = False
        [bumpsemver:file:please_touch_me.txt]
        """).strip())

    check_call(["git", "init"])
    check_call(["git", "add", "please_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.cli", "INFO", "Reading config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 0.3.3\ncommit = False\ntag = False\n[bumpsemver:file:please_touch_me.txt]"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.3.3' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=3, patch=3"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=3, patch=4"),
        ("bumpsemver.version_part", "INFO", "Parsing version '0.3.4' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'"),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=3, patch=4"),
        ("bumpsemver.cli", "INFO", "New version will be '0.3.4'"),
        ("bumpsemver.cli", "INFO", "Asserting files please_touch_me.txt contain the version string..."),
        ("bumpsemver.files.generic", "INFO", "Found '0.3.3' in please_touch_me.txt at line 0: 0.3.3"),
        ("bumpsemver.files.generic", "INFO", "Changing generic file please_touch_me.txt:"),
        ("bumpsemver.files.generic", "INFO", "--- a/please_touch_me.txt\n+++ b/please_touch_me.txt\n@@ -1 +1 @@\n-0.3.3\n+0.3.4"),
        ("bumpsemver.cli", "INFO", "Writing to config file .bumpsemver.cfg:"),
        ("bumpsemver.cli", "INFO",
         "[bumpsemver]\ncurrent_version = 0.3.4\ncommit = False\ntag = False\n\n[bumpsemver:file:please_touch_me.txt]\n\n"),
        ("bumpsemver.cli", "INFO", "Would prepare Git commit"),
        ("bumpsemver.cli", "INFO", "Would add changes in file 'please_touch_me.txt' to Git"),
        ("bumpsemver.cli", "INFO", "Would add changes in file '.bumpsemver.cfg' to Git"),
        ("bumpsemver.cli", "INFO", "Would commit to Git with message '[OPS] bumped version: 0.3.3 \u2192 0.3.4'"),
        ("bumpsemver.cli", "INFO", "Would tag `r0.3.4` with message `[OPS] bumped version: 0.3.3 \u2192 0.3.4` in Git and not signing"),
    )


def test_regression_tag_name_with_hyphens(tmpdir):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("2014.10.22")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "very-unrelated-but-containing-lots-of-hyphens"])

    tmpdir.join(".bumpsemver.cfg").write(dedent("""
    [bumpsemver]
    current_version = 2014.10.22
    """))

    main(["patch", 'some_source.txt'])


def test_unclean_repo_exception(tmpdir, caplog):
    tmpdir.chdir()

    config = dedent("""
        [bumpsemver]
        current_version = 0.0.0
        tag = True
        commit = True
        message = XXX
        """).strip()

    tmpdir.join("file1").write("foo")

    # If I have a repo with an initial commit
    check_call(["git", "init"])
    check_call(["git", "add", "file1"])
    check_call(["git", "commit", "-m", "initial commit"])

    # If I add the bumpsemver config, uncommitted
    tmpdir.join(".bumpsemver.cfg").write(config)

    # I expect bumpsemver patch to fail
    with pytest.raises(subprocess.CalledProcessError):
        main(["patch"])

    # And return the output of the failing command
    assert "Failed to run" in caplog.text


def test_dry_run(tmpdir):
    tmpdir.chdir()

    config = dedent("""
        [bumpsemver]
        current_version = 0.12.0
        tag = True
        commit = True
        message = DO NOT BUMP VERSIONS WITH THIS FILE
        [bumpsemver:file:file4]
        """).strip()

    version = "0.12.0"

    tmpdir.join("file4").write(version)
    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    check_call(["git", "add", "file4"])
    check_call(["git", "add", ".bumpsemver.cfg"])
    check_call(["git", "commit", "-m", "initial commit"])

    main(["patch", "--dry-run"])

    assert config == tmpdir.join(".bumpsemver.cfg").read()
    assert version == tmpdir.join("file4").read()

    vcs_log = check_output(["git", "log"]).decode('utf-8')

    assert "initial commit" in vcs_log
    assert "DO NOT" not in vcs_log
