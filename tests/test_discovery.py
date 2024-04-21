import os
import subprocess
from functools import partial
from textwrap import dedent
import shutil

import pytest
from testfixtures import LogCapture

from bumpsemver.cli import main
from bumpsemver.discovery import check_package_lock_json
from bumpsemver.git import Git

check_call = partial(subprocess.check_call, env=os.environ.copy())


def test_package_lock_json_1():
    managed_files = [
        "dir2/dir1/package-lock.json",
        "dir1/package-lock.json",
        "package-lock.json",
        "endswith-is-not-enough-package-lock.json",
        "package.json",
        "dir1/package-lock.json",
        "dir2/dir1/package-lock.json",
    ]
    issues = []
    check_package_lock_json(issues, managed_files)
    assert issues == [
        "File package-lock.json has only one version position managed. Please add another one into the config file"
    ]


def test_package_lock_json_2():
    managed_files = [
        "dir1/package-lock.json",
        "dir1/package-lock.json",
        "package.json",
        "dir2/dir1/package-lock.json",
        "dir2/dir1/package-lock.json",
    ]
    issues = []
    check_package_lock_json(issues, managed_files)
    assert issues == []


def test_list_files_not_git_no_gitignore(tmpdir):
    tmpdir.chdir()
    tmpdir.join("file1").write("#")
    tmpdir.mkdir("dir1")
    tmpdir.mkdir("dir2").join("file2").write("#")
    actual = Git.list_files()
    actual.sort()

    assert actual == ["dir2/file2", "file1"]


def test_list_files_not_git_with_gitignore(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".gitignore").write("*")
    tmpdir.join("file1").write("#")
    tmpdir.mkdir("dir1")
    tmpdir.mkdir("dir2").join("file2").write("#")
    actual = Git.list_files()
    actual.sort()

    assert actual == [".gitignore", "dir2/file2", "file1"]


def test_list_files_with_git_no_gitignore(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("file1").write("#")
    tmpdir.mkdir("dir1")
    tmpdir.mkdir("dir2").join("file2").write("#")
    subprocess.run(["git", "add", "*", "--all"], check=False)
    actual = Git.list_files()
    actual.sort()

    assert actual == ["dir2/file2", "file1"]


def test_list_files_with_git_with_gitignore(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join(".gitignore").write("**/file4")
    tmpdir.join("file3").write("#")
    tmpdir.mkdir("dir1")
    tmpdir.mkdir("dir2").join("file4").write("#")
    subprocess.run(["git", "add", "*", "--all"], check=False)
    actual = Git.list_files()
    actual.sort()

    assert actual == [".gitignore", "file3"]


def test_list_files_with_git_with_gitignore_deep(tmpdir):
    tmpdir.chdir()
    check_call(["git", "init"])
    tmpdir.join("file5").write("#")
    subdir = tmpdir.mkdir("dir2")
    subdir.join("file6").write("#")
    subdir.join(".gitignore").write("*\n!.gitignore")

    subprocess.run(["git", "add", "*", "--all"], check=False)
    actual = Git.list_files()
    actual.sort()

    assert actual == ["dir2/.gitignore", "file5"]


def test_discovery_unknown_prop(tmpdir):
    tmpdir.chdir()
    tmpdir.join(".bumpsemver.cfg").write(
        dedent(
            """
            [bumpsemver]
            current_version = 75.0.1
            [bumpsemver:discovery]
            unknown = file1
            """
        ).strip()
    )
    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["patch", "--dry-run"])

    assert exc.value.code == 4
    log_capture.check_present(
        (
            "bumpsemver.cli",
            "ERROR",
            "Invalid config file. Unknown keys ['unknown'] in section 'bumpsemver:discovery'",
        )
    )
    assert exc.value.code == 4


def _setup_test_folder(tmpdir, data_path, capsys):
    tmpdir.chdir()
    shutil.copytree(data_path, tmpdir, dirs_exist_ok=True)
    check_call(["git", "init"])
    subprocess.run(["git", "add", "*", "--all"], check=False)


def test_all_in_one_positive(tmpdir, capsys):
    data_path = os.path.abspath(
        os.path.dirname(os.path.realpath(__file__)) + "/fixtures/yolla"
    )
    _setup_test_folder(tmpdir, data_path, capsys)

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["--config-file", ".bumpsemver-max.cfg", "patch", "--allow-dirty"])

    assert exc.value.code == 0
    assert log_capture.actual() == []

    #
    # app/node
    #
    app_node_package = tmpdir.join("app/node/package.json").read()
    assert '"version": "1.0.4"' in app_node_package
    assert '"has-proto": "1.0.3"' in app_node_package

    app_node_package_lock = tmpdir.join("app/node/package-lock.json").read()
    assert (
        '  "name": "bumpsemver-node",\n  "version": "1.0.4",\n' in app_node_package_lock
    )
    assert (
        '      "name": "bumpsemver-node",\n      "version": "1.0.4",\n'
        in app_node_package_lock
    )
    assert (
        '      "version": "1.0.3",\n      "resolved": "https://registry.npmjs.org/has-proto/-/has-proto-1.0.3.tgz",'
        in app_node_package_lock
    )

    app_node_interesting_package = tmpdir.join(
        "app/node/endswith-is-not-enough-package-lock.json"
    ).read()
    assert '"version": "1.0.3"' in app_node_interesting_package

    #
    # app/node-do-not-version
    #
    with open(data_path + "/app/node-do-not-version/package.json", "rt") as f:
        assert f.read() == tmpdir.join("app/node-do-not-version/package.json").read()
    with open(data_path + "/app/node-do-not-version/package-lock.json", "rt") as f:
        assert (
            f.read() == tmpdir.join("app/node-do-not-version/package-lock.json").read()
        )

    #
    # app/python
    #
    python_readme = tmpdir.join("app/python/README.md").read()
    assert "Current version: **v1.0.4**" in python_readme

    python_pyproject = tmpdir.join("app/python/pyproject.toml").read()
    assert '[tool.poetry]\nversion = "1.0.4"\n' in python_pyproject
    assert '[tool.a.fake-one]\nversion = "1.0.3"\n' in python_pyproject

    python_sources = tmpdir.join("app/python/assets/sources.yml").read()
    assert "version: 1.0.4" in python_sources
    assert "version: 1.0.3" not in python_sources

    python_dbt = tmpdir.join("app/python/dbt/dbt_project.yml").read()
    assert "version: 1.0.4" in python_dbt
    assert "version: 1.0.3" not in python_dbt

    #
    # infrastructure
    #
    assert (
        tmpdir.join("infrastructure/invalid-playbook.yaml").read()
        == "% this file is named like an Ansible playbook, but it is not syntax correct {\n"
    )

    #
    # root
    #
    root_bumpsemver_cfg = tmpdir.join(".bumpsemver-max.cfg").read()
    assert "current_version = 1.0.4" in root_bumpsemver_cfg

    root_readme = tmpdir.join("README.md").read()
    assert "Current version: **v1.0.4**" in root_readme
    assert "This 1.0.3 should not be replaced." in root_readme
    assert "Release: bumpsemver-1.0.4" in root_readme

    root_version = tmpdir.join("VERSION").read()
    assert root_version == "1.0.4\n"


def test_all_in_one_negative(tmpdir, capsys):
    data_path = os.path.abspath(
        os.path.dirname(os.path.realpath(__file__)) + "/fixtures/yolla"
    )
    _setup_test_folder(tmpdir, data_path, capsys)

    with LogCapture() as log_capture, pytest.raises(SystemExit) as exc:
        main(["--config-file", ".bumpsemver-min.cfg", "patch", "--allow-dirty"])

    assert exc.value.code == 32
    log_capture.check(
        (
            "bumpsemver.cli",
            "ERROR",
            (
                "Discovered unmanaged files. Please add them to the config file for versioning or to ignore:\n"
                "  - File README.md is not managed. Please add it to the config file\n"
                "  - File app/node-do-not-version/package-lock.json is not managed. Please add it to the config file\n"
                "  - File app/node-do-not-version/package.json is not managed. Please add it to the config file\n"
                "  - File app/node/package-lock.json is not managed. Please add it to the config file\n"
                "  - File app/node/package.json is not managed. Please add it to the config file\n"
                "  - File app/python/assets/sources.yml is not managed. Please add it to the config file\n"
                "  - File app/python/dbt/dbt_project.yml is not managed. Please add it to the config file\n"
                "  - File app/python/pyproject.toml is not managed. Please add it to the config file\n"
                "  - File infrastructure/playbook.yml is not managed. Please add it to the config file"
            ),
        )
    )
