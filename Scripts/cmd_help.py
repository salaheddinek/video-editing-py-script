#!/usr/bin/env python3
__version__ = "1.7.1"

import curses
import os
import platform
import pathlib
import tempfile
import subprocess
import shutil
import re
import argparse
import stat

SCRIPTS = []
HELP_MSG = ""
HELP_NAME = "useful cmd"
UPDATE_NAME = "update all scripts"
GITHUB_URL = "https://github.com/salaheddinek/video-editing-py-script.git"
HEADER_MSG = ""
CHOICE = 0


def character(stdscr):
    global CHOICE
    attributes = {}
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    attributes['normal'] = curses.color_pair(1)

    curses.init_pair(2, curses.COLOR_CYAN, -1)
    attributes['req'] = curses.color_pair(2)

    curses.init_pair(3, curses.COLOR_RED, -1)
    attributes['exit'] = curses.color_pair(3)

    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)
    attributes['highlighted'] = curses.color_pair(4)

    c = 0  # last character read
    option = 0  # the current option that is marked
    while c != 10:  # Enter in ascii
        stdscr.erase()
        stdscr.addstr(HEADER_MSG, curses.A_UNDERLINE)
        for i in range(len(SCRIPTS)):
            if i == option:
                attr = attributes['highlighted']
            elif SCRIPTS[i] == HELP_NAME:
                attr = attributes['req']
            elif SCRIPTS[i] == UPDATE_NAME:
                attr = attributes['req']
            elif SCRIPTS[i] == "exit":
                attr = attributes['exit']
            else:
                attr = attributes['normal']
            stdscr.addstr("{0}. ".format(i + 1))
            if isinstance(SCRIPTS[i], str):
                stdscr.addstr(SCRIPTS[i] + '\n', attr)
            else:
                stdscr.addstr(SCRIPTS[i].stem + '\n', attr)
        c = stdscr.getch()
        if c == curses.KEY_UP:
            option -= 1
        elif c == curses.KEY_DOWN:
            option += 1

        if option == -1:
            option = len(SCRIPTS) - 1
        if option == len(SCRIPTS):
            option = 0

    CHOICE = option
    # stdscr.addstr("You chose {0}".format(SCRIPTS[option]))
    # stdscr.getch()


def get_scripts():
    global SCRIPTS

    cur_file = pathlib.Path(__file__)
    scripts_path = cur_file.parent
    SCRIPTS = []
    for ext in [".py", ".sh", ".pyz"]:
        for s_path in scripts_path.glob("*" + ext):
            if s_path.name != cur_file.name and s_path.name != "autolock.sh":
                SCRIPTS += [s_path]
    SCRIPTS.sort()
    SCRIPTS += [HELP_NAME, UPDATE_NAME, "exit"]


def get_title(i_str):
    return "\n{}:\n{}\n".format(i_str, "".center(len(i_str) + 1, "-"))


def format_help_message():
    global HELP_MSG, HEADER_MSG
    HEADER_MSG = "\nSelect the script to show its functionality.\n\n\n"

    HELP_MSG = "Not implemented yet for Windows"
    if platform.system().lower() == "windows":
        return
    HELP_MSG = get_title("Finding files")
    HELP_MSG += "* Find file in all subdirectories: ex:'find ./ -name \"*.txt\"'\n"
    HELP_MSG += "* Find only in current directory: ex 'find ./ -maxdepth 1 -name \"*.txt\"'\n"
    HELP_MSG += "* Search for files only: 'find -type f', for directories only: 'find -type d'\n"

    HELP_MSG += get_title("Searching in text")
    HELP_MSG += "* Find text in file(s): ex:'grep -n \"<WORD>\" <FILE1> <FILE2> ...'\n"
    HELP_MSG += "* Find text case insensitive: ex:'grep -i -n \"<WORD>\" <FILE1> <FILE2> ...'\n"
    HELP_MSG += "* Find text in all subdirectories: ex 'grep -n -r \"<WORD>\"'\n"
    HELP_MSG += "* Find + grep together: 'find <WHATEVER> | xargs grep -rn \"<WORD>\"'\n"

    HELP_MSG += get_title("Image manipulation")
    HELP_MSG += "* Append images horizontaly: 'convert +append 1.png 2.png result.png'\n"
    HELP_MSG += "* Append images vertically (all images): 'convert -append *.png result.png'\n"

    HELP_MSG += get_title("Copy(cp/mv) complex")
    HELP_MSG += "* copy with find: 'find <WHATEVER> | xargs cp -t <TARGET_FODLER>'\n"
    HELP_MSG += "* copy with grep: 'grep -lir \"<WORD>\" | xargs cp -t <TARGET_FODLER>'\n"


class Updater:
    def __init__(self, git_url):
        self.git_url = git_url
        self.scripts_tmp_path = None

    def update_all_scripts(self):
        # print(self.git_url)
        init_version = self._get_version_from_file()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            if not self._download_update(tmp_path):
                return
            self._replace_current_files()

        self._update_bat_files_for_windows()
        self._give_execution_permission()
        new_version = self._get_version_from_file()
        print(f"successfully updated from version {init_version} to version {new_version}")

    def _download_update(self, in_tmp_path):

        if not shutil.which("git"):
            print("ERROR: could not update scripts: the command 'git' is not installed, "
                  "please install it before updating (for example: scoop install git)")
            return False
        print("cloning the repository from github ...")
        subprocess.run(["git", "clone", self.git_url], cwd=str(in_tmp_path))

        for child in in_tmp_path.iterdir():
            self.scripts_tmp_path = child / "Scripts"

        if not self.scripts_tmp_path.is_dir():
            print(f"ERROR: could not download the project files, path: {self.scripts_tmp_path}")
            return False
        print("successfully downloaded the git repository files")

        return True

    @staticmethod
    def _get_version_from_file():
        cur_file = pathlib.Path(__file__)
        with cur_file.open("r") as f:
            content = f.read()
            if "__version__" not in content:
                return "unknown"
        with cur_file.open("r") as f:
            txt = f.read()
            v_re = r"^__version__ = ['\"]([^'\"]*)['\"]"
            version = re.search(v_re, txt, re.M)
            version = version.group(1)
        return version

    def _replace_current_files(self):
        cur_scripts_folder = pathlib.Path(__file__).parent

        for child in self.scripts_tmp_path.iterdir():
            old_script = cur_scripts_folder / child.name
            old_script.unlink(missing_ok=True)
            child.rename(old_script)

    @staticmethod
    def _update_bat_files_for_windows():
        if platform.system().lower() != "windows":
            return
        cur_file = pathlib.Path(__file__)
        cur_scripts_folder = cur_file.parent
        bat_files_folder = cur_scripts_folder.parent
        cur_file_bat_launcher = bat_files_folder / (cur_file.stem + ".bat")
        if not cur_file_bat_launcher.is_file():
            return
        num_py_scripts = 0
        for ext in ["*.py", "*.pyz"]:
            for py_script in cur_scripts_folder.glob(ext):
                bat_launcher = bat_files_folder / (py_script.stem + ".bat")
                if bat_launcher.is_file():
                    continue
                with bat_launcher.open("w") as f:
                    f.write(f"py {py_script} %*")
                num_py_scripts += 1
        print(f"generated {num_py_scripts} '.bat' script launchers, path: {bat_files_folder}")

    @staticmethod
    def _give_execution_permission():
        if platform.system().lower() != "linux":
            return
        cur_file = pathlib.Path(__file__)
        cur_scripts_folder = cur_file.parent
        for ext in ["*.py", "*.pyz"]:
            for ele in cur_scripts_folder.glob(ext):
                ele.chmod(ele.stat().st_mode | stat.S_IEXEC)

        print("updated execution permissions for the new files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Show the list of other scripts, and let you select which one you'
                                                 ' want to use to display its help.')
    args = parser.parse_args()

    get_scripts()
    format_help_message()
    curses.wrapper(character)

    if CHOICE == len(SCRIPTS) - 3:
        print(HELP_MSG)
    elif CHOICE == len(SCRIPTS) - 2:
        update_process = Updater(GITHUB_URL)
        update_process.update_all_scripts()
    elif CHOICE == len(SCRIPTS) - 1:
        print("")
    else:
        if platform.system().lower() == "windows":
            print("")
            os.system(f"py {SCRIPTS[CHOICE]} -h")
        else:
            os.system(f"{SCRIPTS[CHOICE]} -h")
