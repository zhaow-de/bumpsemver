import re
from typing import Any

from tomlkit import items as tomlkit_types
from tomlkit import parse


class TomlPath:
    # noinspection GrazieInspection
    @staticmethod
    def is_valid(path: str) -> bool:
        # 1. a path can consist of zero or more parts
        # 2. for a path with two or more parts, parts must be separated by "."
        # 3. part must not contain "."
        # 4. empty string is not a valid part
        # 5. part must not start with dot
        # 6. part must not end with "["
        # 7. "[" must pair with "]"
        # 8. within "[" and "]", there must be a number or nothing
        # 9. "[" "]" pair must not be nested
        # 10. "[" " pair must not at the beginning or the middle of a part
        # 11. if a part contains whitespace, it must be enclosed in double-quotes
        if "'" in path:
            return False

        parts = [p for p in path.split(".") if p.strip()]
        if not parts:
            return False

        for part in parts:
            if part.startswith("["):
                return False

            key = re.match(r"(?P<key>^.*?)(\[(?P<index>\d*)])?$", part).groupdict()["key"]

            if not key or "[" in key or "]" in key:
                return False

            if key.startswith('"'):
                if not (len(key) >= 3 and key.endswith('"') and '"' not in key[1:-1]):
                    return False
            elif " " in key or '"' in key:
                return False

        return True

    @staticmethod
    def query(toml_str: str, tomlpath: str) -> Any:
        content = parse(toml_str)
        result = retrieve_property(content, tomlpath)
        if isinstance(result, list):
            return [item for item in result if item]
        if result is None or result == []:
            return None
        return result

    @staticmethod
    def update(toml_str: str, tomlpath: str, new_value: Any) -> str:
        content = parse(toml_str)
        set_property(content, tomlpath, new_value)
        return content.as_string()


def set_property(obj: Any, path: str, value: Any) -> None:
    keys = [key for key in re.split(r"[.\[\]]", path) if key]
    last_key_index = len(keys) - 1

    for i, key in enumerate(keys):
        if isinstance(obj, list):
            if key.isdigit():
                if i == last_key_index:
                    obj[int(key)] = value
                else:
                    obj = obj[int(key)]
            else:
                try:
                    for item in obj:
                        set_property(item, ".".join(keys[keys.index(key) :]), value)
                finally:
                    pass
                break
        elif i == last_key_index:
            if key in obj.keys():
                obj[key] = value
        else:
            obj = obj[key]


def unwrap_object(obj: Any) -> Any:
    if (
        isinstance(obj, tomlkit_types.String)
        or isinstance(obj, tomlkit_types.Bool)
        or isinstance(obj, tomlkit_types.Integer)
        or isinstance(obj, tomlkit_types.Float)
    ):
        return obj.unwrap()
    return obj


def retrieve_property(obj, path: str) -> Any:
    keys = re.split(r"[.\[\]]", path)
    keys = [key for key in keys if key]  # remove empty strings from the list
    result = []
    for i, key in enumerate(keys):
        if isinstance(obj, list):
            if key.isdigit():

                obj = unwrap_object(obj[int(key)])
            else:
                try:
                    result = [retrieve_property(item, ".".join(keys[keys.index(key) :])) for item in obj]
                finally:
                    pass
                break
        elif i == len(keys) - 1:
            if key in obj.keys():
                obj = unwrap_object(obj[key])
            else:
                return None
        else:
            obj = obj[key]
    return result if result else obj
