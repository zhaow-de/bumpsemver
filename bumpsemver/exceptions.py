from typing import List, Tuple, Union

from typing_extensions import Buffer


class BumpVersionError(Exception):
    """Custom base class for all BumpVersion exception types."""


class InvalidConfigSectionError(BumpVersionError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class WorkingDirectoryIsDirtyError(BumpVersionError):
    def __init__(self, lines: List[Buffer]):
        message = "Git working directory is not clean:\n{}".format(b"\n".join(lines).decode())
        super().__init__(message)
        self.message = message


class CannotParseVersionError(BumpVersionError):
    def __init__(self):
        message = "The specific version could not be parsed with semver scheme. Please double check the config file"
        super().__init__(message)
        self.message = message


class MixedNewLineError(BumpVersionError):
    def __init__(self, filename: str, file_new_lines: Tuple[str, ...]):
        message = f"File {filename} has mixed newline characters: {file_new_lines}"
        super().__init__(message)
        self.message = message


# NOTE: this exception is for plain text file only.
# because for plain text file we do not have the concept of XPATH-like locator,
# there is either a match or not.
# we cannot distinguish the mismatch cases like json, yaml, toml
# with InvalidFileError, PathNotFoundError, SingleValueMismatchError, and MultiValuesMismatchError
class VersionNotFoundError(BumpVersionError):
    def __init__(self, search_expression: str, filename: str):
        message = f"Did not find '{search_expression}' in plaintext file: '{filename}'"
        super().__init__(message)
        self.message = message


class InvalidFileError(BumpVersionError):
    def __init__(self, filename: str, file_type: str):
        message = f"File {filename} cannot be parsed as a valid {file_type} file"
        super().__init__(message)
        self.message = message


class PathNotFoundError(BumpVersionError):
    def __init__(self, selector: str, file_type: str, filename: str):
        message = f"Selector '{selector}' does not lead to a valid property in {file_type} file {filename}"
        super().__init__(message)
        self.message = message


class SingleValueMismatchError(BumpVersionError):
    def __init__(
        self,
        selector: str,
        file_type: str,
        filename: str,
        actual_value: Union[str, int, float, bool],
        expected_value: Union[str, int, float, bool],
    ):
        message = (
            f"Selector '{selector}' finds value '{actual_value}' "
            f"mismatches with the expectation '{expected_value}' in {file_type} file {filename}"
        )
        super().__init__(message)
        self.message = message


class MultiValuesMismatchError(BumpVersionError):
    def __init__(
        self,
        selector: str,
        file_type: str,
        filename: str,
        actual_value: List[Union[str, int, float, bool]],
        expected_value: Union[str, int, float, bool],
    ):
        message = (
            f"Selector '{selector}' finds list of values {actual_value} with one more more elements "
            f"mismatch with the expectation '{expected_value}' in {file_type} file {filename}"
        )
        super().__init__(message)
        self.message = message


class FileTypeMismatchError(BumpVersionError):
    def __init__(self, file_type: str, file_type_expected: str, filename: str):
        message = (
            f"Wrong file type '{file_type}' specified for file {filename}, "
            f"please use '{file_type_expected}' instead"
        )
        super().__init__(message)
        self.message = message


class DiscoveryError(BumpVersionError):
    def __init__(self, issues: List[str]):
        issues_str = "\n  - ".join(issues)
        message = (
            f"Discovered unmanaged files. "
            f"Please add them to the config file for versioning or to ignore:\n  - {issues_str}"
        )
        super().__init__(message)
        self.message = message
