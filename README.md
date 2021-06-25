# bumpsemver

**Current version: 1.0.4**

A utility to simplify the version bumping for git repos.

This application is a rework of the famous `bumpversion` tool. The  
[original repo](https://github.com/peritus/bumpversion) seems like abandoned. Several fundamental changes are
introduced, which make the fork-and-extend approach infeasible:
1. dropped Python 2 support
2. boosted the test coverage to 95%+
3. dropped many irrelevant features to reduce complexity. (e.g. customized version component support)
4. introduced JSON support to make it work for package-lock.json, YAML support to make it work for Ansible plays
5. narrowed the versioning scheme to semver-only

## Installation

```bash
pip3 install bumpsemver
```

## Usage

This application supports both the CLI mode and config file mode.

### Command Line Interface

```bash
bumpsemver [options] part [file]
```
    
#### `options`
_**(optional)**_<br />
  
Most of the configuration values described below can also be given as an option on the command-line.
Additionally, the following options are available:

`--dry-run`
  Don't touch any files, just pretend. Best used with `--verbose`.

`--allow-dirty`
  Normally, bumpsemver will abort if the working directory is dirty to protect
  yourself from releasing unversioned files and/or overwriting unsaved changes.
  Use this option to override this check.

`--verbose`
  Print useful information to stderr

`-h, --help`
  Print help and exit

#### `part`
_**required**_<br />

The part of the version to increase. As we support semver only, the valid values include: `major`, `minor`, and `patch`.

For example, bumping file `src/VERSION` from 0.5.1 to 0.6.0:

```bash
bumpsemver --current-version 0.5.1 minor src/VERSION
```

#### `file`
_**(optional)**_<br />
**default**: none

The file that will be modified.

If not given, the list of `[bumpsemver:file:…]` sections from the configuration file will be used. If no files are
mentioned on the configuration file either, then no files will be modified.

For example, bumping file `setup.py` from 1.1.9 to 2.0.0:
```
bumpsemver --current-version 1.1.9 major setup.py
```

### Configuration file

Options on the command line take precedence over those from the config file, which take precedence over those from the
defaults.

Example `.bumpsemver.cfg`:

```ini
[bumpsemver]
current_version = 0.2.9
commit = True
tag = True

[bumpsemver:file:README]
```

#### `.bumpsemver.cfg` -- Global configuration

General configuration is grouped in a `[bumpsemver]` section.

##### `current_version` 
_**required**_<br />
**default**: none

The current version of the software package before bumping.

Also available as CLI argument `--current-version` (e.g. `bumpsemver --current-version 0.5.1 patch`)

##### `tag = (True | False)`
_**(optional)**_<br />
**default**: False (Don't create a git tag)

Whether to create a git tag, that is the new version, prefixed with the character "`r`". Don't forget to `git-push`
with the `--tags` flag.

Also available as CLI argument `--tag` or `--no-tag`.

##### `sign_tags = (True | False)`
_**(optional)**_<br />
**default**: False (Don't sign tags)

Whether to sign tags.

Also available as CLI argument `--sign-tags` or `--no-sign-tags`.

##### `tag_name =`
_**(optional)**_<br />
**default:** `v{new_version}`

The name of the tag that will be created. Only valid when `tag = True`.

It can be a template using the [Python Format String Syntax](https://docs.python.org/3/library/string.html#format-string-syntax).  
Available in the template context are `current_version` and `new_version` as well as `current_[part]` and `new_[part]`
(e.g. '`current_major`' or '`new_patch`'). You can also use the variables `now` or `utcnow` to get a current timestamp.
Both accept datetime formatting (when used like as in `{now:%d.%m.%Y}`).

Also available as CLI argument `--tag-name`, for example: `bumpsemver --tag-name 'release-{new_version}' patch`

In addition, it is also possible to provide a tag message by using CLI `--tag-message TAG_MESSAGE`. Example usage:
`bumpsemver --tag-name 'release-{new_version}' --tag-message "Release {new_version}" patch`

If neither tag message or sign tag is provided, we use a `lightweight` tag in git. Otherwise, we utilize an `annotated`
git tag. Read more about Git tagging [here](https://git-scm.com/book/en/v2/Git-Basics-Tagging).

##### `commit = (True | False)`
_**(optional)**_<br />
**default:** False (Don't create a commit)

Create a commit using git when true.

Also available as CLI argument `--commit` or `--no-commit`.

##### `message =`
_**(optional)**_<br />
**default:** `[OPS] bumped version: {current_version} → {new_version}`

The commit message to use when creating a commit. Only valid when using `--commit` / `commit = True`.

It can be a template using the [Python Format String Syntax](https://docs.python.org/3/library/string.html#format-string-syntax).  
Available in the template context are `current_version` and `new_version` as well as `current_[part]` and `new_[part]`
(e.g. '`current_major`' or '`new_patch`'). You can also use the variables `now` or `utcnow` to get a current timestamp.
Both accept datetime formatting (when used like as in `{now:%d.%m.%Y}`).

Also available as CLI argument `--message`, for example: `bumpsemver --tag-name 'release-{new_version}' patch`

In addition, it is also possible to provide a tag message by using CLI `--tag-message TAG_MESSAGE`. Example usage:
`bumpsemver --message '[{now:%Y-%m-%d}] Jenkins Build {$BUILD_NUMBER}: {new_version}' patch`

#### `.bumpsemver.cfg` -- File specific configuration

This configuration is in the section: `[bumpsemver:file:…]` or `[bumpsemver:json:…]`

Note: The configuration file format requires each section header to be unique. If you want to process a certain file
multiple times (e.g. multiple location to be replaced separately), you may append a description between parens to the
`file` keyword: `[bumpsemver:file (special one):…]`. It does not matter what inside the parens, just make it unique.
e.g.

```ini
[bumpsemver:file(1):README.md]
search = current version: {current_version}
replace = current version: {new_version}

[bumpsemver:file(2):README.md]
search = **Version: {current_version}**
replace = current version: {new_version}
```

##### `search =`
**default:** `{current_version}`

Template string how to search for the string to be replaced in the file. Useful if the remotest possibility exists that
the current version number might be present multiple times in the file and you mean to only bump one of the occurrences.

#### `replace =`
**default:** `{new_version}`

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

[bumpsemver:file:requirements.txt]
search = MyProject=={current_version}
replace = MyProject=={new_version}
```

With `[bumpsemver:file:…]`, the specified file is processed as plain text file, which in fact makes this application
programming language neutral. However, it will be very error prone for complex file for example `package-lock.json`.

For randomly sampled 30 projects written in node.js/TypeScript, the classical `bumpversion` or the renovated `bump2version` both made
100% mistakes which changed something shouldn't be changed. A typical and relatively complex React projects contains 1000+ npm packages  
indirectly. There are too many "version": "1.2.3" in that file. To address this issue, `bumpsemver` added the support of json file.

To use it:
 ```ini
[bumpsemver:json:package-lock.json]
jsonpath = version 
```

Value of the parameter `jsonpath` is a [JSONPath](https://goessner.net/articles/JsonPath/) string. For the typical
`package.json` or `package-lock.json`, using `version` or its jQuery-style alternative `$.version` is sufficient.
Otherwise, anything can be selected with JSONPath is support, so, nothing we can't do. The underlying JSONPath processor
is [jsonpath-ng](https://github.com/h2non/jsonpath-ng). Checkout their document for some examples and hints.

The suffix is also supported for json file:
```ini
[bumpsemver:json(1):example.json]
jsonpath = version

[bumpsemver:json( same file):example.json]
jsonpath = dependencies[2].*.version

[bumpsemver:json (once again):example.json]
jsonpath = dependencies[0].*.lodash.dependencies[1].version
```

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
Please note that we use [yamlpath](https://github.com/wwkimball/yamlpath/wiki/Segments-of-a-YAML-Path#yaml-path-standard) instead of
`jsonpath` here. `yamlpath` is not a popular "standard" widely adopted. For complex scenarios, it makes sense to test the expression with
[yamlpath cli](https://pypi.org/project/yamlpath/) before putting anything in the config file.

## Test

Test in Docker container (recommended):
```bash
make test
```

Local test in the working environment (not recommended):
```bash
tox
```

To test the compatibility with a specific version of Python, put the version(s) into `./python-versions.txt` one version
per line. Then run:
```bash
make test
```
