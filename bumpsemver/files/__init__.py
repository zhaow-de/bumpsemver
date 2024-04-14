from enum import Enum


class FileTypes(str, Enum):
    GENERIC = "plaintext"
    JSON = "json"
    YAML = "yaml"
