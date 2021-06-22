from enum import Enum


class FileTypes(str, Enum):
    GENERIC = 'generic'
    JSON = 'json'
    YAML = 'yaml'
