import os
import subprocess
from functools import partial
from textwrap import dedent

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main
from tests.test_cli import COMMIT, COMMIT_NOT_TAG, EXPECTED_OPTIONS, check_output

check_call = partial(subprocess.check_call, env=os.environ.copy())


def test_regression_help_in_work_dir(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("1.7.2013")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "r1.7.2013"])

    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    out, err = capsys.readouterr()

    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, f"Usage string is missing {option_line}"

    assert "Version that needs to be updated (default: 1.7.2013)" in out
    assert exc.value.code == 0


def test_dirty_work_dir(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("dirty").write("i'm dirty")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:file7]
            """
        ).strip()
    )

    check_call(["git", "add", "dirty"])

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "1", "--new-version", "2"])

    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Git working directory is not clean:\n"
            "A  dirty\n"
            "\n"
            "Use --allow-dirty to override this if you know what you're doing.",
        ),
        order_matters=True,
    )
    assert exc.value.code == 5


def test_force_dirty_work_dir(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("dirty2").write("i'm dirty! 1.1.1")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:dirty2]
            """
        ).strip()
    )

    check_call(["git", "add", "dirty2"])

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--allow-dirty", "--current-version", "1.1.1"])

    assert "i'm dirty! 1.1.2" == tmpdir.join("dirty2").read()
    assert exc.value.code == 0


def test_commit_and_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("47.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "47.1.1", "--commit"])

    assert "47.1.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-47.1.1" in log
    assert "+47.1.2" in log
    assert "build(repo): bumped version 47.1.1 → 47.1.2" in log
    assert exc.value.code == 0

    tag_out = check_output(["git", "tag"])

    assert b"v47.1.2" not in tag_out

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "47.1.2", "--commit", "--tag"])

    assert "47.1.3" == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])
    tag_out = check_output(["git", "tag"])

    assert b"v47.1.3" in tag_out
    assert exc.value.code == 0


def test_commit_and_tag_with_configfile(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            commit = True
            tag = True
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.1.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "48.1.1", "--no-tag"])

    assert "48.1.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-48.1.1" in log
    assert "+48.1.2" in log
    assert "build(repo): bumped version 48.1.1 → 48.1.2" in log

    tag_out = check_output(["git", "tag"])

    assert b"v48.1.2" not in tag_out
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "48.1.2"])

    assert "48.1.3" == tmpdir.join("VERSION").read()

    check_output(["git", "log", "-p"])

    tag_out = check_output(["git", "tag"])

    assert b"v48.1.3" in tag_out
    assert exc.value.code == 0


@pytest.mark.parametrize("config", [COMMIT, COMMIT_NOT_TAG])
def test_commit_and_not_tag_with_configfile(tmpdir, config):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    tmpdir.join("VERSION").write("48.10.1")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--current-version", "48.10.1"])

    assert "48.10.2" == tmpdir.join("VERSION").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")

    assert "-48.10.1" in log
    assert "+48.10.2" in log
    assert "build(repo): bumped version 48.10.1 → 48.10.2" in log

    tag_out = check_output(["git", "tag"])

    assert b"v48.10.2" not in tag_out
    assert exc.value.code == 0


def test_commit_explicitly_false(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 10.0.0
            commit = False
            tag = False
            [bumpsemver:plaintext:tracked_file]
            """
        ).strip()
    )

    check_call(["git", "init"])
    tmpdir.join("tracked_file").write("10.0.0")
    check_call(["git", "add", "tracked_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert "10.0.1" == tmpdir.join("tracked_file").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")
    assert "10.0.1" not in log

    diff = check_output(["git", "diff"]).decode("utf-8")
    assert "10.0.1" in diff

    assert exc.value.code == 0


def test_commit_configfile_true_cli_false_override(tmpdir):
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 27.0.0
            commit = True
            [bumpsemver:plaintext:dont_commit_file]
            """
        ).strip()
    )

    check_call(["git", "init"])
    tmpdir.join("dont_commit_file").write("27.0.0")
    check_call(["git", "add", "dont_commit_file"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--no-commit"])

    assert "27.0.1" == tmpdir.join("dont_commit_file").read()

    log = check_output(["git", "log", "-p"]).decode("utf-8")
    assert "27.0.1" not in log

    diff = check_output(["git", "diff"]).decode("utf-8")
    assert "27.0.1" in diff

    assert exc.value.code == 0


def test_current_version_from_tag(tmpdir):
    # prepare
    tmpdir.join("update_from_tag").write("26.6.0")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 26.6.0
            commit = True
            [bumpsemver:plaintext:update_from_tag]
            """
        ).strip()
    )

    tmpdir.chdir()
    check_call(["git", "init"])
    check_call(["git", "add", "update_from_tag"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r26.6.0"])

    with pytest.raises(SystemExit) as exc:
        # don't give current-version, that should come from tag
        main(["patch"])

    assert tmpdir.join("update_from_tag").read() == "26.6.1"
    assert exc.value.code == 0


def test_current_version_from_tag_written_to_config_file(tmpdir):
    # prepare
    tmpdir.join("updated_also_in_config_file").write("14.6.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            [bumpsemver:plaintext:updated_also_in_config_file]
        """
        )
    )

    check_call(["git", "init"])
    check_call(["git", "add", "updated_also_in_config_file"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r14.6.0"])

    with pytest.raises(SystemExit) as exc:
        # don't give current-version, that should come from tag
        main(["patch", "--commit", "--tag"])

    assert "14.6.1" == tmpdir.join("updated_also_in_config_file").read()
    assert "14.6.1" in tmpdir.join(".bumpsemver.cfg").read()

    assert exc.value.code == 0


def test_override_vcs_current_version(tmpdir):
    # prepare
    tmpdir.join("contains_actual_version").write("6.7.8")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 6.7.8
            commit = True
            [bumpsemver:plaintext:contains_actual_version]
            """
        ).strip()
    )
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

    with pytest.raises(SystemExit) as exc:
        # if we don't give current-version here, we get "AssertionError:
        # Did not find string 6.7.8 in file contains_actual_version"
        main(["patch", "--current-version", "7.0.0"])

    assert "7.0.1" == tmpdir.join("contains_actual_version").read()
    assert exc.value.code == 0


def test_read_version_tags_only(tmpdir):
    # prepare
    tmpdir.join("update_from_tag").write("29.6.0")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 29.6.0
            commit = True
            [bumpsemver:plaintext:update_from_tag]
            """
        ).strip()
    )
    tmpdir.chdir()
    check_call(["git", "init"])
    check_call(["git", "add", "update_from_tag"])
    check_call(["git", "commit", "-m", "initial"])
    check_call(["git", "tag", "r29.6.0"])
    check_call(["git", "commit", "--allow-empty", "-m", "a commit"])
    check_call(["git", "tag", "jenkins-deploy-my-project-2"])

    with pytest.raises(SystemExit) as exc:
        # don't give current-version, that should come from tag
        main(["patch"])

    assert "29.6.1" == tmpdir.join("update_from_tag").read()
    assert exc.value.code == 0


def test_tag_name(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("31.1.1")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 31.1.1
            commit = True
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "patch",
                "--current-version",
                "31.1.1",
                "--commit",
                "--tag",
                "--tag-name",
                "ReleasedVersion-{new_version}",
            ]
        )

    tag_out = check_output(["git", "tag"])

    assert b"ReleasedVersion-31.1.2" in tag_out
    assert exc.value.code == 0


def test_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("400.0.0")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 400.0.0
            new_version = 401.0.0
            commit: True
            tag: True
            message: {current_version} was old, {new_version} is new
            tag_name: from-{current_version}-to-{new_version}
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["major"])

    log = check_output(["git", "log", "-p"])

    assert b"400.0.0 was old, 401.0.0 is new" in log

    tag_out = check_output(["git", "tag"])

    assert b"from-400.0.0-to-401.0.0" in tag_out

    assert exc.value.code == 0


def test_unannotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.3.1")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "patch",
                "--current-version",
                "42.3.1",
                "--commit",
                "--tag",
                "--tag-name",
                "ReleasedVersion-{new_version}",
                "--tag-message",
                "",
            ]
        )

    tag_out = check_output(["git", "tag"])
    assert b"ReleasedVersion-42.3.2" in tag_out

    describe_out = subprocess.call(["git", "describe"])
    assert 128 == describe_out

    describe_out = subprocess.check_output(["git", "describe", "--tags"])
    assert describe_out.startswith(b"ReleasedVersion-42.3.2")

    assert exc.value.code == 0


def test_annotated_tag(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.4.1")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "patch",
                "--current-version",
                "42.4.1",
                "--commit",
                "--tag",
                "--tag-message",
                "test {new_version}-tag",
            ]
        )
    assert "42.4.2" == tmpdir.join("VERSION").read()

    tag_out = check_output(["git", "tag"])
    assert b"v42.4.2" in tag_out

    describe_out = subprocess.check_output(["git", "describe"])
    assert describe_out == b"v42.4.2\n"

    describe_out = subprocess.check_output(["git", "show", "v42.4.2"])
    assert describe_out.startswith(b"tag v42.4.2\n")
    assert b"test 42.4.2-tag" in describe_out

    assert exc.value.code == 0


def test_vcs_describe(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("42.5.1")
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            [bumpsemver:plaintext:VERSION]
            """
        ).strip()
    )

    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "patch",
                "--current-version",
                "42.5.1",
                "--commit",
                "--tag",
                "--tag-message",
                "test {new_version}-tag",
            ]
        )
    assert "42.5.2" == tmpdir.join("VERSION").read()

    describe_out = subprocess.check_output(["git", "describe"])
    assert b"v42.5.2\n" == describe_out
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "patch",
                "--current-version",
                "42.5.2",
                "--commit",
                "--tag",
                "--tag-name",
                "ReleasedVersion-{new_version}",
                "--tag-message",
                "",
            ]
        )
    assert "42.5.3" == tmpdir.join("VERSION").read()

    describe_only_annotated_out = subprocess.check_output(["git", "describe"])
    assert describe_only_annotated_out.startswith(b"v42.5.2-1-g")

    describe_all_out = subprocess.check_output(["git", "describe", "--tags"])
    assert b"ReleasedVersion-42.5.3\n" == describe_all_out

    assert exc.value.code == 0


def test_utf8_message_from_config_file(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("10.10.0")

    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    initial_config = dedent(
        """
        [bumpsemver]
        current_version = 10.10.0
        commit = True
        message = [{now}] [{utcnow} {utcnow:%YXX%mYY%d}]
        [bumpsemver:plaintext:VERSION]
        """
    ).strip()
    tmpdir.join(".bumpsemver.cfg").write(initial_config)

    with pytest.raises(SystemExit) as exc:
        main(["major"])

    log = check_output(["git", "log", "-p"])

    assert b"[20" in log
    assert b"] [" in log
    assert b"XX" in log
    assert b"YY" in log

    assert exc.value.code == 0


def test_commit_and_tag_from_below_vcs_root(tmpdir, monkeypatch):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("VERSION").write("30.0.3")
    check_call(["git", "add", "VERSION"])
    check_call(["git", "commit", "-m", "initial commit"])

    tmpdir.mkdir("subdir")
    monkeypatch.chdir(tmpdir.join("subdir"))
    tmpdir.join("subdir/.bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver:plaintext:../VERSION]
            """
        ).strip()
    )

    with pytest.raises(SystemExit) as exc:
        main(["major", "--current-version", "30.0.3", "--commit"])

    assert "31.0.0" == tmpdir.join("VERSION").read()
    assert exc.value.code == 0


def test_subjunctive_dry_run_logging(tmpdir):
    tmpdir.join("dont_touch_me.txt").write("0.8.0")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.8.0
            commit = True
            tag = True
            [bumpsemver:plaintext:dont_touch_me.txt]
            """
        ).strip()
    )

    check_call(["git", "init"])
    check_call(["git", "add", "dont_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose", "--dry-run"])

    log_capture.check(
        ("bumpsemver.config", "INFO", "Reading config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            (
                "[bumpsemver]\ncurrent_version = 0.8.0\ncommit = True\n"
                "tag = True\n[bumpsemver:plaintext:dont_touch_me.txt]"
            ),
        ),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.8.0' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=8, patch=0"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=8, patch=1"),
        ("bumpsemver.cli", "INFO", "Dry run active, won't touch any files."),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.8.1' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=8, patch=1"),
        ("bumpsemver.cli", "INFO", "New version will be '0.8.1'"),
        ("bumpsemver.cli", "INFO", "Asserting files dont_touch_me.txt contain the version string..."),
        ("bumpsemver.files.text", "INFO", "Found '0.8.0' in dont_touch_me.txt at line 0: 0.8.0"),
        ("bumpsemver.files.text", "INFO", "Would change plaintext file dont_touch_me.txt:"),
        (
            "bumpsemver.files.text",
            "INFO",
            "--- a/dont_touch_me.txt\n+++ b/dont_touch_me.txt\n@@ -1 +1 @@\n-0.8.0\n+0.8.1",
        ),
        ("bumpsemver.config", "INFO", "Would write to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            (
                "[bumpsemver]\ncurrent_version = 0.8.1\ncommit = True\n"
                "tag = True\n\n[bumpsemver:plaintext:dont_touch_me.txt]\n\n"
            ),
        ),
        ("bumpsemver.cli", "INFO", "Would prepare Git commit"),
        ("bumpsemver.cli", "INFO", "Would add changes in file 'dont_touch_me.txt' to Git"),
        ("bumpsemver.cli", "INFO", "Would add changes in file '.bumpsemver.cfg' to Git"),
        ("bumpsemver.cli", "INFO", "Would commit to Git with message 'build(repo): bumped version 0.8.0 \u2192 0.8.1'"),
        (
            "bumpsemver.cli",
            "INFO",
            "Would tag `v0.8.1` with message `build(repo): bumped version 0.8.0 \u2192 0.8.1` in Git and not signing",
        ),
    )

    assert exc.value.code == 0


def test_log_commit_message_if_no_commit_tag_but_usable_vcs(tmpdir):
    tmpdir.join("please_touch_me.txt").write("0.3.3")
    tmpdir.chdir()

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 0.3.3
            commit = False
            tag = False
            [bumpsemver:file:please_touch_me.txt]
            """
        ).strip()
    )

    check_call(["git", "init"])
    check_call(["git", "add", "please_touch_me.txt"])
    check_call(["git", "commit", "-m", "initial commit"])

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--verbose"])

    log_capture.check(
        ("bumpsemver.config", "INFO", "Reading config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            "[bumpsemver]\ncurrent_version = 0.3.3\ncommit = False\ntag = False\n[bumpsemver:file:please_touch_me.txt]",
        ),
        ("bumpsemver.config", "WARNING", "File type 'file' is deprecated, please use 'plaintext' instead."),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.3.3' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=3, patch=3"),
        ("bumpsemver.cli", "INFO", "Attempting to increment part 'patch'"),
        ("bumpsemver.cli", "INFO", "Values are now: major=0, minor=3, patch=4"),
        (
            "bumpsemver.version_part",
            "INFO",
            "Parsing version '0.3.4' using regexp '(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)'",
        ),
        ("bumpsemver.version_part", "INFO", "Parsed the following values: major=0, minor=3, patch=4"),
        ("bumpsemver.cli", "INFO", "New version will be '0.3.4'"),
        ("bumpsemver.cli", "INFO", "Asserting files please_touch_me.txt contain the version string..."),
        ("bumpsemver.files.text", "INFO", "Found '0.3.3' in please_touch_me.txt at line 0: 0.3.3"),
        ("bumpsemver.files.text", "INFO", "Changing plaintext file please_touch_me.txt:"),
        (
            "bumpsemver.files.text",
            "INFO",
            "--- a/please_touch_me.txt\n+++ b/please_touch_me.txt\n@@ -1 +1 @@\n-0.3.3\n+0.3.4",
        ),
        ("bumpsemver.config", "INFO", "Writing to config file .bumpsemver.cfg:"),
        (
            "bumpsemver.config",
            "INFO",
            (
                "[bumpsemver]\ncurrent_version = 0.3.4\ncommit = False\n"
                "tag = False\n\n[bumpsemver:file:please_touch_me.txt]\n\n"
            ),
        ),
        ("bumpsemver.cli", "INFO", "Would prepare Git commit"),
        ("bumpsemver.cli", "INFO", "Would add changes in file 'please_touch_me.txt' to Git"),
        ("bumpsemver.cli", "INFO", "Would add changes in file '.bumpsemver.cfg' to Git"),
        ("bumpsemver.cli", "INFO", "Would commit to Git with message 'build(repo): bumped version 0.3.3 \u2192 0.3.4'"),
        (
            "bumpsemver.cli",
            "INFO",
            "Would tag `v0.3.4` with message `build(repo): bumped version 0.3.3 \u2192 0.3.4` in Git and not signing",
        ),
    )

    assert exc.value.code == 0


def test_regression_tag_name_with_hyphens(tmpdir):
    tmpdir.chdir()
    tmpdir.join("some_source.txt").write("2014.10.22")
    check_call(["git", "init"])
    check_call(["git", "add", "some_source.txt"])
    check_call(["git", "commit", "-m", "initial commit"])
    check_call(["git", "tag", "very-unrelated-but-containing-lots-of-hyphens"])

    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 2014.10.22
            [bumpsemver:plaintext:some_source.txt]
            """
        )
    )

    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    assert exc.value.code == 0


def test_unclean_repo_exception(tmpdir, caplog):
    tmpdir.chdir()

    config = dedent(
        """
        [bumpsemver]
        current_version = 0.0.0
        tag = True
        commit = True
        message = XXX
        """
    ).strip()

    tmpdir.join("file1").write("foo")

    # If I have a repo with an initial commit
    check_call(["git", "init"])
    check_call(["git", "add", "file1"])
    check_call(["git", "commit", "-m", "initial commit"])

    # If I add the bumpsemver config, uncommitted
    tmpdir.join(".bumpsemver.cfg").write(config)

    # I expect bumpsemver patch to fail
    with pytest.raises(SystemExit) as exc:
        main(["patch"])

    # And return the output of the failing command
    assert "Failed to run" in caplog.text

    assert exc.value.code == 10


def test_dry_run(tmpdir):
    tmpdir.chdir()

    config = dedent(
        """
        [bumpsemver]
        current_version = 0.12.0
        tag = True
        commit = True
        message = DO NOT BUMP VERSIONS WITH THIS FILE
        [bumpsemver:file:file4]
        """
    ).strip()

    version = "0.12.0"

    tmpdir.join("file4").write(version)
    tmpdir.join(".bumpsemver.cfg").write(config)

    check_call(["git", "init"])
    check_call(["git", "add", "file4"])
    check_call(["git", "add", ".bumpsemver.cfg"])
    check_call(["git", "commit", "-m", "initial commit"])

    with pytest.raises(SystemExit) as exc:
        main(["patch", "--dry-run"])

    assert config == tmpdir.join(".bumpsemver.cfg").read()
    assert version == tmpdir.join("file4").read()

    vcs_log = check_output(["git", "log"]).decode("utf-8")

    assert "initial commit" in vcs_log
    assert "DO NOT" not in vcs_log
    assert exc.value.code == 0
