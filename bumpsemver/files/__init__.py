from enum import Enum


class FileTypes(str, Enum):
    GENERIC = "plaintext"
    JSON = "json"
    TOML = "toml"
    YAML = "yaml"
