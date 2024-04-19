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
    def __init__(self, path: str, file_new_lines: Tuple[str, ...]):
        message = f"File {path} has mixed newline characters: {file_new_lines}"
        super().__init__(message)
        self.message = message


# NOTE: this exception is for plain text file only.
# because for plain text file we do not have the concept of XPATH-like locator,
# there is either a match or not.
# we cannot distinguish the mismatch cases like json, yaml, toml
# with InvalidFileError, PathNotFoundError, SingleValueMismatchError, and MultiValuesMismatchError
class VersionNotFoundError(BumpVersionError):
    def __init__(self, search_expression: str, path: str):
        message = f"Did not find '{search_expression}' in plaintext file: '{path}'"
        super().__init__(message)
        self.message = message


class InvalidFileError(BumpVersionError):
    def __init__(self, path: str, file_type: str):
        message = f"File {path} cannot be parsed as a valid {file_type} file"
        super().__init__(message)
        self.message = message


class PathNotFoundError(BumpVersionError):
    def __init__(self, selector: str, file_type: str, path: str):
        message = f"Selector '{selector}' does not lead to a valid property in {file_type} file {path}"
        super().__init__(message)
        self.message = message


class SingleValueMismatchError(BumpVersionError):
    def __init__(
        self,
        selector: str,
        file_type: str,
        path: str,
        actual_value: Union[str, int, float, bool],
        expected_value: Union[str, int, float, bool],
    ):
        message = (
            f"Selector '{selector}' finds value '{actual_value}' "
            f"mismatches with the expectation '{expected_value}' in {file_type} file {path}"
        )
        super().__init__(message)
        self.message = message


class MultiValuesMismatchError(BumpVersionError):
    def __init__(
        self,
        selector: str,
        file_type: str,
        path: str,
        actual_value: List[Union[str, int, float, bool]],
        expected_value: Union[str, int, float, bool],
    ):
        message = (
            f"Selector '{selector}' finds list of values {actual_value} "
            f"with one more more elements mismatch with the expectation '{expected_value}' in {file_type} file {path}"
        )
        super().__init__(message)
        self.message = message
