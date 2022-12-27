import argparse
import os
import pathlib
import sys

import nox

# fmt: off
sys.path.append(".")
from tools import release  # isort:skip  # noqa

sys.path.pop()

# fmt: on

nox.options.sessions = ["lint", "test"]  # Sessions other than 'dev'

REQUIREMENTS = {
    "tests": "tests/requirements.txt",
}


@nox.session(python=["3.6", "3.9", "3.10", "3.11"])
def lint(session):
    session.install("flake8")
    session.run("flake8", "src", "tests", "noxfile.py")


@nox.session(python=["3.6", "3.9"])
def test(session: nox.Session):
    # Install source
    session.install(".")

    # Install test dependencies
    session.install("-r", REQUIREMENTS["tests"])

    # Parallelize tests as much as possible, by default.
    arguments = session.posargs or ["-n", "auto"]
    session.run("pytest", env={"LC_CTYPE": "en_US.UTF-8"})


VENV_DIR = pathlib.Path('./.venv').resolve()


@nox.session
def dev(session: nox.Session) -> None:
    """
    Sets up a python development environment for the project.

    This session will:
    - Create a python virtualenv for the session
    - Install the `virtualenv` cli tool into this environment
    - Use `virtualenv` to create a global project virtual environment
    - Invoke the python interpreter from the global project environment to install
      the project and all it's development dependencies.
    """

    session.install("virtualenv")
    # the VENV_DIR constant is explained above
    session.run("virtualenv", os.fsdecode(VENV_DIR), silent=True)

    python = os.fsdecode(VENV_DIR.joinpath("bin/python"))

    # Use the venv's interpreter to install the project along with
    # all it's dev dependencies, this ensures it's installed in the right way
    session.run(python, "-m", "pip", "install", "-e", ".[dev]", external=True)


def check_changelog_version(new_version: str) -> bool:
    """Returns True if the new version is in the changelog, False otherwise."""
    changelog = pathlib.Path("CHANGELOG").read_text(encoding="utf-8")
    first_line = changelog.splitlines()[0]
    return new_version in first_line


@nox.session
def release(session: nox.Session) -> None:
    """
    Kicks off an automated release process by creating and pushing a new tag.

    Invokes bump2version with the posarg setting the version.

    Usage:
    $ nox -s release -- [major|minor|patch]
    """
    parser = argparse.ArgumentParser(description="Release a semver version.")
    parser.add_argument(
        "version",
        type=str,
        nargs=1,
        help="The type of semver release to make.",
        choices={"major", "minor", "patch", "build"},
    )
    args: argparse.Namespace = parser.parse_args(args=session.posargs)
    version: str = args.version.pop()

    version_info = session.run("bump2version", "--dry-run", "--list", version,
                               silent=True, env={"LC_CTYPE": "en_US.UTF-8"})
    current_version = [line for line in version_info.splitlines()
                       if "current_version" in line][0].split("=")[1]
    new_version = [line for line in version_info.splitlines()
                   if "new_version" in line][0].split("=")[1]

    # If we get here, we should be good to go
    # Let's do a final check for safety
    confirm = input(
        f"You are about to bump from v{current_version} to v{new_version}. "
        "This will create a new tag and push it to the remote. Continue? [y/N] "
    )

    # Abort on anything other than 'y'
    if confirm.lower().strip() != "y":
        session.error(f"You said no when prompted to bump the {version!r} version.")

    if not check_changelog_version(new_version):
        session.error(
            f"Could not find {new_version} in CHANGELOG. "
            "Please make sure the latest version is at the top of the changelog.")

    session.install("bump2version")

    session.log(f"Bumping the {version!r} version")
    # session.run("bump2version", version)

    session.log("Pushing the new tag")
    # session.run("git", "push", external=True)
    # session.run("git", "push", "--tags", external=True)
    session.log("Done!")
    session.log("A new release should be available on GitHub and the rpm repo shortly.")
