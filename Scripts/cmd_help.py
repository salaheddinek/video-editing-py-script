#!/usr/bin/python3
import curses
import os

SCRIPTS = []
HELP_MSG = ""
HELP_NAME = "useful cmd"
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
            elif SCRIPTS[i] == "exit":
                attr = attributes['exit']
            else:
                attr = attributes['normal']
            stdscr.addstr("{0}. ".format(i + 1))
            stdscr.addstr(SCRIPTS[i] + '\n', attr)
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
    cur_file_name = os.path.basename(__file__)
    scripts_path = os.path.dirname(os.path.abspath(__file__))

    SCRIPTS = []
    for file in os.listdir(scripts_path):
        if file.endswith(".py") or file.endswith(".sh") or file.endswith(".pyz"):
            if file != cur_file_name and file != "autolock.sh":
                SCRIPTS += [file]
    SCRIPTS.sort()
    SCRIPTS += [HELP_NAME, "exit"]


def get_title(i_str):
    return "\n{}:\n{}\n".format(i_str, "".center(len(i_str) + 1, "-"))


def format_help_message():
    global HELP_MSG, HEADER_MSG
    HEADER_MSG = "\nSelect the script to show its functionality.\n\n\n"

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


if __name__ == "__main__":
    get_scripts()
    format_help_message()
    curses.wrapper(character)

    if CHOICE == len(SCRIPTS) - 2:
        print(HELP_MSG)
    elif CHOICE == len(SCRIPTS) - 1:
        print("")
    else:
        os.system(SCRIPTS[CHOICE] + " -h")
