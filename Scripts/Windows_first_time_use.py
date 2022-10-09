#!/usr/bin/python3
import os
import pathlib
import platform


if __name__ == "__main__":
    my_file = pathlib.Path(__file__)
    if platform.system().lower() != "windows":
        print("WARNING: this script should only be run for windows systems!")
        my_file.unlink()
        quit()

    scripts_folder = my_file.parent
    py_scripts_folder = scripts_folder / "py_scripts"
    py_scripts_folder.mkdir(exist_ok=True)

    for py_file in scripts_folder.glob("*.py"):
        name = py_file.stem
        bat_file = scripts_folder / (name + ".bat")
        if name == my_file.stem:
            continue
        with bat_file.open("w") as f:
            f.write(f"py {py_scripts_folder / (name + '.py')} %*")
        os.rename(str(scripts_folder / (name + ".py")), str(py_scripts_folder / (name + ".py")))
    for py_file in scripts_folder.glob("*.ttf"):
        os.rename(str(py_file), str(py_scripts_folder / py_file.name))
    print("finished")
    my_file.unlink()
