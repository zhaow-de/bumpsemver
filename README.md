# bumpsemver

[![image](https://img.shields.io/pypi/v/bumpsemver.svg)](https://pypi.org/project/bumpsemver/)
[![image](https://img.shields.io/pypi/l/bumpsemver.svg)](https://pypi.org/project/bumpsemver/)
[![image](https://img.shields.io/pypi/pyversions/bumpsemver.svg)](https://pypi.org/project/bumpsemver/)
[![codecov](https://codecov.io/gh/zhaow-de/bumpsemver/graph/badge.svg?token=WP4O30YLO3)](https://codecov.io/gh/zhaow-de/bumpsemver)
[![GitHub Actions](https://github.com/zhaow-de/bumpsemver/workflows/CI/badge.svg)](https://github.com/zhaow-de/bumpsemver/actions)


Current version: **2.0.0**

## Table of contents

<!--TOC-->

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [Command Line Interface](#command-line-interface)
- [Configuration file](#configuration-file)
  - [General config section](#general-config-section)
  - [File-specific config sections](#file-specific-config-sections)
  - [File types supported in the file-specific config section](#file-types-supported-in-the-file-specific-config-section)
    - [Plain text file](#plain-text-file)
    - [JSON file](#json-file)
    - [YAML file](#yaml-file)
    - [TOML file](#toml-file)

<!--TOC-->

## Overview

A utility to simplify the version bumping for git repos.

This application is a rework of the famous `bumpversion` tool. The  
[original repo](https://github.com/peritus/bumpversion) seems like abandoned. Several fundamental changes are
introduced, which make the fork-and-extend approach infeasible:
1. dropped Python 2 support
2. boosted the test coverage to 95%+
3. dropped many irrelevant features to reduce complexity. (e.g. customized version component support)
4. introduced JSON support to make it work for package-lock.json
5. introduced YAML support to make it work for Ansible playbooks
6. introduced TOML support to make it work for pyproject.toml 
7. narrowed the versioning scheme to semver-only

## Installation

```bash
pip install --upgrade bumpsemver
```

## Usage

This application supports both the CLI mode and config file mode.
Options on the command line take precedence over those from the config file, which take precedence over those from the
defaults.

## Command Line Interface

```bash
bumpsemver [options] part [file]
```
    
##### **`options`**    _**(optional)**_
  
Most of the configuration values described below can also be given as an option on the command-line.
Additionally, the following options are available:

`--dry-run`
Don't touch any files, just pretend. Best used with `--verbose`.

`--allow-dirty`
Normally, bumpsemver will abort if the working directory is dirty to avoid releasing not versioned files
and/or overwriting unsaved changes. Use this option to override this check.

`--verbose`
Print useful information about the action details.

`--alloy-checks`
Perform some extra checks for a private project. Generally irrelevant to the common daily usages.

`-h, --help`
Print help and exit.

##### **`part`**    _**(required)**_

The part of the version to increase. As we support semver only, the valid values include: `major`, `minor`, and `patch`.

For example, bumping file `src/VERSION` from 0.5.1 to 0.6.0:

```bash
bumpsemver --current-version 0.5.1 minor src/VERSION
```

##### **`file`**    _**(optional).**_    _**default**_: none

The file that will be modified.

If not given, the list of `[bumpsemver:*:…]` sections from the configuration file will be used.
If no files are mentioned on the configuration file either, no files will be modified.

For example, bumping file `setup.py` from 1.1.9 to 2.0.0:
```
bumpsemver --current-version 1.1.9 major setup.py
```

## Configuration file

`bumpsemver` looks up configuration file `.bumpsemver.cfg` at the current directory.
The config file uses [`ini` syntax](https://en.wikipedia.org/wiki/INI_file).
It consists of one general section `[bumpsemver]` and zero or more `[bumpsemver:type(suffix):filename]` file sections. 

Example `.bumpsemver.cfg`:

```ini
[bumpsemver]
current_version = 0.2.9
commit = True
tag = True

[bumpsemver:plaintext:README.md]
search = Version: **{current_version}**
replace = Version: **{new_version}**

[bumpsemver:plaintext(header):home.md]
search = Version: **{current_version}**
replace = Version: **{new_version}**

[bumpsemver:plaintext(footer 1):home.md]
search = Current version: {current_version}
replace = Current version: {new_version}

[bumpsemver:json:example.json]
jsonpath = foobar.items[1].version

[bumpsemver:yaml:example.yml]
yamlpath = dummy.version

[bumpsemver:toml:example.toml]
tomlpath = project.version
```

### General config section

General configuration is grouped in a `[bumpsemver]` section of `.bumpsemver.cfg`.
It has the following properties:

##### **`current_version =`**    _**(required).**_    _**default**_: none

The current version of the software package before bumping.

Also available as CLI argument `--current-version` (e.g. `bumpsemver --current-version 0.5.1 patch`)

##### **`tag = (True | False)`**    _**(optional).**_    _**default**_: `False`

Whether to create a git tag, that is the new version, prefixed with the character "`v`".

Also available as CLI argument `--tag` or `--no-tag`.

##### **`sign_tags = (True | False)`**    _**(optional).**_    _**default**_: `False`

Whether to sign tags.

Also available as CLI argument `--sign-tags` or `--no-sign-tags`.

##### **`tag_name =`**    _**(optional).**_    _**default**_: `v{new_version}`

The name of the tag that will be created. Only valid when `tag = True`.

It can be a template using the [Python Format String Syntax](https://docs.python.org/3/library/string.html#format-string-syntax).  
Available in the template context are `current_version` and `new_version` as well as `current_[part]` and `new_[part]`
(e.g. '`current_major`' or '`new_patch`'). You can also use the variables `now` or `utcnow` to get a current timestamp.
Both accept datetime formatting (when used like as in `{now:%d.%m.%Y}`).

Also available as CLI argument `--tag-name`, for example: `bumpsemver --tag-name 'release-{new_version}' patch`

In addition, it is also possible to provide a tag message by using CLI `--tag-message TAG_MESSAGE`. Example usage:
`bumpsemver --tag-name 'release-{new_version}' --tag-message "Release {new_version}" patch`

If neither tag message nor sign tag is provided, we use a `lightweight` tag in git. Otherwise, we utilize an `annotated`
git tag. Read more about Git tagging [here](https://git-scm.com/book/en/v2/Git-Basics-Tagging).

##### **`commit = (True | False)`**    _**(optional).**_    _**default**_: `False`

Create a commit using git when true.

Also available as CLI argument `--commit` or `--no-commit`.

##### **`message =`**    _**(optional).**_    _**default**_: `build(repo): bumped version {current_version} → {new_version}`

The commit message to use when creating a commit. Only valid when using `--commit` / `commit = True`.

It can be a template using the [Python Format String Syntax](https://docs.python.org/3/library/string.html#format-string-syntax).  
Available in the template context are `current_version` and `new_version` as well as `current_[part]` and `new_[part]`
(e.g. '`current_major`' or '`new_patch`'). You can also use the variables `now` or `utcnow` to get a current timestamp.
Both accept datetime formatting (when used like as in `{now:%d.%m.%Y}`).

Also available as CLI argument `--message`, for example: `bumpsemver --tag-name 'release-{new_version}' patch`

### File-specific config sections

A file-specific config section is required for each file to specify the handling of the particular file.
One config file can have zero or more file-specific config sections.
The section name looks like `[bumpsemver:type:filename]`.
It specifies the action to be done for a specific file.

We do have the use case that one file has multiple places to change, a popular example is `package-lock.json`:
```json
{
  "name": "rcplus-app-cli",
  "version": "1.1.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "rcplus-app-cli",
      "version": "1.1.0",
      "license": "SEE LICENSE IN LICENSE"
    }
  }
}
```
We need two config sections for the same file in this case, but INI format does not allow duplicated section names.
To make it work we could append a description between parens to the
`type` keyword: `[bumpsemver:plaintext(special one):…]`. It does not matter what inside the parens, just make it unique.
For the example below, the two patterns will be applied separately to the same file `README.md`:
```ini
[bumpsemver:plaintext(1):README.md]
search = current version: {current_version}
replace = current version: {new_version}

[bumpsemver:plaintext(footer):README.md]
search = **Version: {current_version}**
replace = **Version: {new_version}**
```

### File types supported in the file-specific config section

All the famous `bump*version` utilities family has a common pattern to handle the files as a plain text file.
The advantage of this approach is that in fact it makes the use scenario programming language-neutral.
Be it a package-lock.json for node.js project, or pyproject.toml for a Python application,
the `bump*version` is applicable as long as a proper regex pattern for version extraction can be defined.

However, it will bring significant side effect for complex file for example `package-lock.json`.
A typical (relatively) complex React projects contains 1000+ npm packages indirectly.
For randomly sampled 30 public projects at GitHub written in node.js/TypeScript,
the classical `bumpversion` or the renovated `bump2version` both made mistakes
for all 30 projects which changed something shouldn't be changed.

For instance, the `facebook/create-react-app` application has a large fleet of indirect
npm dependencies.
If we define the search pattern as `"version": "4.0.0"`, we will screw up the other 210 packages.
Or if we are unluckily releasing our app bumping the version from `7.16.0` to `8.0.0`,
other 132 npm packages in the version lock will be changed to `8.0.0`, which likely do not exist.
To address this issue, `bumpsemver` added the support of some popular file types
to access the particular version attribute using a deterministic locator/selector without regex.

The supported file types are:
* plaintext
* json
* yaml
* toml

#### Plain text file

The file-specific config section looks like:
```ini
[bumpsemver:plaintext:filename]
search = Version: {current_version}
replace = Version: {new_version}
```

A deprecated syntax is also supported:
```ini
[bumpsemver:file:filename]
```
We renamed (in a backward compatible way) `file` or `plaintext` to emphasize
that the file being processed is considered as a plain text file.
You can easily destroy a JSON file by a missing a double-quote or a comma in the regex pattern.

This file type should generally only be used for the files that are not JSON, YAML, or TOML.
`README.md` is a good use case for this one.

`[bumpsemver:plaintext:...]` can have two properties:

##### **`search =`**    _**default**_: `{current_version}`

Template string how to search for the string to be replaced in the file.
Useful if the remotest possibility exists that the current version number might be present multiple times in the file,
and you mean to only bump one of the occurrences.

##### **`replace =`**    _**default**_: `{new_version}`

Template to create the string that will replace the current version number in the file.

Given this `requirements.txt`:
```
    Django>=1.5.6,<1.6
    MyProject==1.5.6
```
using the following `.bumpsemver.cfg` will ensure only the line containing `MyProject` will be changed:
```ini
[bumpsemver]
current_version = 1.5.6

[bumpsemver:plaintext:requirements.txt]
search = MyProject=={current_version}
replace = MyProject=={new_version}
```

#### JSON file

The file-specific config section looks like:
```ini
[bumpsemver:json:package.json]
jsonpath = version 
```

It accepts only one property:

##### **`jsonpath =`**    **(required)**    _**default**_: none

Value of the parameter `jsonpath` is a [JSONPath](https://goessner.net/articles/JsonPath/) string,
it points to the exact property of the version string to be bumped.
For the typical `package.json`, using `version` or its jQuery-style alternative `$.version` is sufficient.
Otherwise, anything can be selected with JSONPath is support, so, nothing we can't do.
The underlying JSONPath processor is [jsonpath-ng](https://github.com/h2non/jsonpath-ng).
Checkout their document for some examples and hints.

The suffix is also supported for json file:
```ini
[bumpsemver:json(1):example.json]
jsonpath = version

[bumpsemver:json( same file):example.json]
jsonpath = dependencies[2].*.version

[bumpsemver:json (once again):example.json]
jsonpath = dependencies[0].*.lodash.dependencies[1].version
```

#### YAML file

Comparably, YAML is supported for the same reason that we should support native JSON, like
 ```ini
[bumpsemver:yaml:playbook.yml]
yamlpath = version 
```
OR
```ini
[bumpsemver:yaml(1):playbook.yml]
yamlpath = *.vars.project_version

[bumpsemver:yaml( same file):playbook.yaml]
yamlpath = *.vars.version

[bumpsemver:yaml (once again):playbook.yaml]
yamlpath = *.vars.app_version
```

Please note that we use
[yamlpath](https://github.com/wwkimball/yamlpath/wiki/Segments-of-a-YAML-Path#yaml-path-standard) here.
`yamlpath` is not a popular "standard" widely adopted as `jsonpath`.
For complex scenarios, it makes sense to test the expression with [yamlpath cli](https://pypi.org/project/yamlpath/)
before putting anything in the config file.

#### TOML file

The file-specific config section looks like:
```ini
[bumpsemver:toml:pyproject.toml]
tomlpath = tool.poetry.version
```

For whatever reason toml gets its acceptance and popularity, especially in the Go, Rust, and later Python community.
Despite the unlogical fashion and religion drives, in fact we have many toml files in the wild.
For instance `pyproject.toml` is everywhere now.

We cannot even find out a "tomlpath" or similar library to read/update the properties in a toml file by giving a
string as the "path" to the property.
We rolled our own tomlpath processor, which is not a standard, but offering similar functionality as yamlpath.
