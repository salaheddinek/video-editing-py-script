#!/usr/bin/env python3
import pathlib
import platform
import argparse
import shutil
import stat


def check_if_delete(in_installation_path):
    if not in_installation_path.is_dir():
        return True

    print(f"The installation path already exists: {in_installation_path}")
    print("choices:")
    print(" [d]   delete this folder and make a new installation")
    print(" [k]   keep this folder and append to it my scripts")
    print(" [c]   cancel installation")
    user_opt = input("which option: ")
    print("")
    # print(user_opt)
    if user_opt.lower() == "d":
        shutil.rmtree(str(in_installation_path))
        # print(f"deleted {in_installation_path}")
        return
    if user_opt.lower() == "k":
        return
    print("installation cancelled")
    quit()


def copy_script_files(in_src, in_dst):
    num_copied = 0
    for ext in ["*.ttf", "*.py", "*.pyz"]:
        for ele in in_src.glob(ext):
            shutil.copyfile(str(ele), str(in_dst / ele.name))
            num_copied += 1
    print(f"copied {num_copied} scripts")


def give_execution_permission(in_installation_path):
    for ext in ["*.py", "*.pyz"]:
        for ele in in_installation_path.glob(ext):
            ele.chmod(ele.stat().st_mode | stat.S_IEXEC)
    print("gave scripts execution permission")


def modify_bashrc_file(in_installation_path):
    bashrc_path = pathlib.Path().home() / ".bashrc"
    make_global_cmd = f'export PATH=$PATH:"{in_installation_path}"'
    with bashrc_path.open("r") as f:
        bashrc_txt = f.read()
        if make_global_cmd in bashrc_txt:
            print(f"{bashrc_path.name} was not change to give execution permission (this was already done)")
            return
    with bashrc_path.open("a") as f:
        f.write("\n" + make_global_cmd)
    print(f"modified '{bashrc_path}' to make scripts executable in {in_installation_path}")
    print("scripts now can be executed from anywhere in the system (only works for bash)")


def produce_the_bat_files(in_installation_path, in_installation_py_scripts):
    num_file = 0
    for ext in ["*.py", "*.pyz"]:
        for py_file in in_installation_py_scripts.glob(ext):
            stem = py_file.stem
            bat_file = in_installation_path / (stem + ".bat")
            if bat_file.is_file():
                continue
            with bat_file.open("w") as f:
                f.write(f"py {in_installation_py_scripts / (stem + '.py')} %*")
            num_file += 1
    print(f"generated {num_file} new '.bat' files,  these well be used to launch the '.py' files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='copies all the script to the desired installation folder, '
                                                 'and make it possible for the user to use them from anywhere '
                                                 'on the system (make them global)')
    parser.add_argument('Installation_folder', metavar='IDir', type=str,
                        help='The path where to copy all the python scripts')
    args = parser.parse_args()
    my_file = pathlib.Path(__file__)
    scripts_folder = my_file.parent / "Scripts"

    if platform.system().lower() == "linux":
        input_path = args.Installation_folder
        if input_path.startswith("~/"):
            input_path = str(pathlib.Path().home() / input_path[2:])
        installation_path = pathlib.Path(input_path)
        print("detected platform: LINUX")
        check_if_delete(installation_path)
        installation_path.mkdir(parents=True, exist_ok=True)
        copy_script_files(scripts_folder, installation_path)
        give_execution_permission(installation_path)
        modify_bashrc_file(installation_path)
        print(f"finished installing the scripts to '{installation_path}'")

    elif platform.system().lower() == "windows":
        installation_path = pathlib.Path(args.Installation_folder)
        print("detected platform: WINDOWS")
        check_if_delete(installation_path)
        installation_path.mkdir(parents=True, exist_ok=True)
        installation_py_scripts_path = installation_path / "py_scripts"
        installation_py_scripts_path.mkdir(parents=True, exist_ok=True)
        copy_script_files(scripts_folder, installation_py_scripts_path)
        produce_the_bat_files(installation_path, installation_py_scripts_path)
        print(f"finished installing the scripts to '{installation_path}'")
        print("to make scripts in this folder accessible from anywhere in the system (GLOBAL scripts)")
        print("run the following command in PowerShell in ADMINISTRATOR mode: \n\n")

        print(f'setx path "%PATH%;{installation_path}"')
        print("")
    else:
        print(f"The detected platform '{platform.system()}' is not support yet. abort installation!")
