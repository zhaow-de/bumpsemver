from enum import Enum


class FileTypes(str, Enum):
    generic = 'generic'
    json = 'json'
    yaml = 'yaml'
