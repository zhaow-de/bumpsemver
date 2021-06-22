

class BumpVersionException(Exception):
    """Custom base class for all BumpVersion exception types."""


class IncompleteVersionRepresentationException(BumpVersionException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class MissingValueForSerializationException(BumpVersionException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class WorkingDirectoryIsDirtyException(BumpVersionException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class VersionNotFoundException(BumpVersionException):
    """A version number was not found in a source file."""
