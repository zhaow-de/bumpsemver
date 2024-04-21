import errno
import logging
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Optional, Union

from bumpsemver.exceptions import WorkingDirectoryIsDirtyError

logger = logging.getLogger(__name__)


class Git:

    @classmethod
    def commit(cls, message: str, context, extra_args=None):
        extra_args = extra_args or []
        with NamedTemporaryFile("wb", delete=False) as temp_fp:
            temp_fp.write(message.encode("utf-8"))
        env = os.environ.copy()
        for key in ("current_version", "new_version"):
            env[str("BUMPSEMVER_" + key.upper())] = str(context[key])
        try:
            subprocess.check_output(["git", "commit", "-F", temp_fp.name, *extra_args], env=env)
        except subprocess.CalledProcessError as exc:
            err_msg = f"Failed to run {exc.cmd}: return code {exc.returncode}, output: {exc.output}"
            logger.exception(err_msg)
            raise exc
        finally:
            os.unlink(temp_fp.name)

    @classmethod
    def is_usable(cls):
        try:
            return (
                subprocess.call(["git", "rev-parse", "--git-dir"], stderr=subprocess.PIPE, stdout=subprocess.PIPE) == 0
            )
        except OSError as err:
            if err.errno in (errno.ENOENT, errno.EACCES):
                return False

    @classmethod
    def assert_non_dirty(cls):
        lines = [
            line.strip()
            for line in subprocess.check_output(["git", "status", "--porcelain"]).splitlines()
            if not line.strip().startswith(b"??")
        ]

        if lines:
            raise WorkingDirectoryIsDirtyError(lines)

    @classmethod
    def latest_tag_info(cls):
        try:
            # git-describe doesn't update the git-index, so we do that
            subprocess.check_output(["git", "update-index", "--refresh"])

            # get info about the latest tag in git
            describe_out = (
                subprocess.check_output(
                    [
                        "git",
                        "describe",
                        "--dirty",
                        "--tags",
                        "--long",
                        "--abbrev=40",
                        "--match=r*",
                    ],
                    stderr=subprocess.STDOUT,
                )
                .decode()
                .split("-")
            )
        except subprocess.CalledProcessError:
            logger.debug("Error when running git describe")
            return {}

        info = {}

        if describe_out[-1].strip() == "dirty":
            info["dirty"] = True
            describe_out.pop()

        info["commit_sha"] = describe_out.pop().lstrip("g")
        info["distance_to_latest_tag"] = int(describe_out.pop())
        info["current_version"] = "-".join(describe_out).lstrip("r")

        return info

    @classmethod
    def add_path(cls, path: Union[str, Path]):
        subprocess.check_output(["git", "add", "--update", str(path)])

    @classmethod
    def tag(cls, name: str, sign: bool = False, message: Optional[str] = None) -> None:
        """
        Create a tag of the new_version in Git.

        If only name is given, bumpversion uses a lightweight tag.
        Otherwise, it uses an annotated tag.
        """
        command = ["git", "tag", name]
        if sign:
            command += ["--sign"]
        if message:
            command += ["--message", message]
        subprocess.check_output(command)

    @classmethod
    def list_files(cls) -> List[str]:
        try:
            return [line.decode().strip() for line in subprocess.check_output(["git", "ls-files"]).splitlines()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("'git ls-files' failed. Listing files without respecting '.gitignore'")
            path = os.getcwd()
            return [
                os.path.relpath(str(os.path.join(dir_path, f)))
                for (dir_path, dirs, filenames) in os.walk(path)
                for f in filenames
            ]
