from pathlib import Path
from typing import Dict, List

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bumpsemver.exceptions import DiscoveryError
from bumpsemver.git import Git

TO_BE_MANAGED = ["package.json", "package-lock.json", "pyproject.toml", "dbt_project.yml"]

yaml = YAML(typ="safe")


def check_package_lock_json(issues: List[str], managed_file: List[str]):
    """
    package-lock.json has two version positions to be changed.
    it is a common mistake that only the one in the root is managed.
    """
    package_lock_files: Dict[str, int] = {}
    for file in managed_file:
        if file == "package-lock.json" or file.endswith("/package-lock.json"):
            if file in package_lock_files.keys():
                package_lock_files[file] += 1
            else:
                package_lock_files[file] = 1
    for file in package_lock_files.keys():
        if package_lock_files[file] < 2:
            issues.append(
                f"File {file} has only one version position managed. " f"Please add another one into the config file"
            )


def mark_an_issue(issues: List[str], file: str):
    issues.append(f"File {file} is not managed. Please add it to the config file")


def discover_unmanaged_files(managed_files: List[str], ignore_files: List[str]):
    issues: List[str] = []

    check_package_lock_json(issues, managed_files)

    all_files = set(Git.list_files())

    # remove ignored_files and managed_files from all_files
    for file in ignore_files + managed_files:
        if file in all_files:
            all_files.remove(file)

    for file in all_files:
        if file == "README.md":
            # only README.md at the root is mandatory to be managed
            mark_an_issue(issues, file)
            continue
        detected = False
        for to_be_managed in TO_BE_MANAGED:
            # files in TO_BE_MANAGED should be managed no matter where they are
            if file == to_be_managed or file.endswith(f"/{to_be_managed}"):
                mark_an_issue(issues, file)
                detected = True
                break
        if detected:
            continue
        path = Path(file)
        if path.suffix == ".yml" or path.suffix == ".yaml":
            if "play" in path.name.lower():
                # might be an Ansible playbook. dig deeper to find out
                try:
                    data = yaml.load(path)
                except YAMLError:
                    continue
                if (
                    isinstance(data, list)
                    and len(data) > 0
                    and "roles" in data[0]
                    and "vars" in data[0]
                    and [prop for prop in data[0]["vars"] if "version" in prop]
                ):
                    # bingo!
                    mark_an_issue(issues, file)
                    continue
            # try to find out if it is a dbt source file
            try:
                data = yaml.load(path)
            except YAMLError:
                continue
            if (
                isinstance(data, dict)
                and "sources" in data
                and isinstance(data["sources"], list)
                and len(data["sources"]) > 0
                and "schema" in data["sources"][0]
                and "tables" in data["sources"][0]
                and isinstance(data["sources"][0]["tables"], list)
                and len(data["sources"][0]["tables"]) > 0
            ):
                # bingo!
                mark_an_issue(issues, file)
                continue

    if issues:
        issues.sort()
        raise DiscoveryError(issues)
