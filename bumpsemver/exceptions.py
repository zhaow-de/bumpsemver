class BumpVersionError(Exception):
    """Custom base class for all BumpVersion exception types."""


class IncompleteVersionRepresentationError(BumpVersionError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class MissingValueForSerializationError(BumpVersionError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class WorkingDirectoryIsDirtyError(BumpVersionError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class VersionNotFoundError(BumpVersionError):
    """A version number was not found in a source file."""


class MixedNewLineError(BumpVersionError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
