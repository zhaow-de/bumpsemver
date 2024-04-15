import re
from typing import Any

from tomlkit import parse


class TomlPath:
    @staticmethod
    def retrieve_property(obj, path) -> Any:
        keys = re.split(r"[.\[\]]", path)
        keys = [key for key in keys if key]  # remove empty strings from list
        result = []
        for key in keys:
            if isinstance(obj, list):
                if key.isdigit():
                    obj = obj[int(key)]
                else:
                    result = [TomlPath.retrieve_property(item, ".".join(keys[keys.index(key) :])) for item in obj]
                    break
            else:
                obj = obj[key]
        return result if result else obj

    @staticmethod
    def query(toml: str, tomlpath: str) -> Any:
        content = parse(toml)
        return TomlPath.retrieve_property(content, tomlpath)

    @staticmethod
    def set_property(obj, path, value) -> None:
        keys = re.split(r"[.\[\]]", path)
        keys = [key for key in keys if key]  # remove empty strings from list
        for i, key in enumerate(keys):
            if i == len(keys) - 1:  # if it's the last key
                if isinstance(obj, list):
                    if key.isdigit():
                        obj[int(key)] = value
                    else:
                        for item in obj:
                            item[key] = value
                else:
                    obj[key] = value
            else:
                if isinstance(obj, list):
                    if key.isdigit():
                        obj = obj[int(key)]
                    else:
                        obj = [TomlPath.set_property(item, ".".join(keys[keys.index(key) :]), value) for item in obj]
                        break
                else:
                    obj = obj[key]

    @staticmethod
    def update(toml: str, tomlpath: str, new_value: Any) -> str:
        content = parse(toml)
        TomlPath.set_property(content, tomlpath, new_value)
        return content.as_string()
