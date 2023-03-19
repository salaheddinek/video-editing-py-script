#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import shutil
import zlib
import binascii
import tempfile
import os


INPUT = ""
OUTPUT = ""
NUM_CHARACTERS_PER_LINE = 120
SEPERATOR = "\n"
PRINT_OUTPUT = False
INKSCAPE_MODE = False
INKSCAPE_COMMAND = "flatpak run org.inkscape.Inkscape"


def get_input_text_from_inkscape_svg(in_path):
    in_p = pathlib.Path(in_path)
    if in_p.suffix != ".svg":
        print("ERROR: not and svg file, please deactivate inkscape mode")
        return False, ""
    with tempfile.TemporaryDirectory(dir=str(in_p.parent)) as tmp_dir:
        tmp_p = pathlib.Path(tmp_dir) / "ss.svg"
        os.system(f'{INKSCAPE_COMMAND} -o {tmp_p} -l {in_p}')
        with tmp_p.open("rb") as f_handler:
            out_data = f_handler.read()

    return False, out_data


def get_input_text(in_path):
    in_p = pathlib.Path(in_path)
    is_this_text = False
    out_data = ""
    if in_p.is_file():
        if in_p.suffix == ".txt":
            with in_p.open("r") as f_handler:
                out_data = f_handler.read()
                is_this_text = True
        else:
            with in_p.open("rb") as f_handler:
                out_data = f_handler.read()

    else:
        if shutil.which("kdialog") is not None:
            out_data = subprocess.run(["kdialog", "--title", "Input text data", "--textinputbox",
                                       "Please enter the text:", "--geometry", "1200x600"],
                                      stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
        elif shutil.which("zenity") is not None:
            out_data = subprocess.run(
                ["zenity", "--text-info", "--editable", "--title", 'Please enter the text:', "--width", "1200",
                 "--height", "600"],
                stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]

        is_this_text = True
    return is_this_text, out_data


def data_to_text(in_data, line_size=80, separator="\n"):
    compressed = binascii.b2a_base64(zlib.compress(in_data)).decode("ascii")
    formatted = separator.join(compressed[i:i + line_size] for i in range(0, len(compressed), line_size))
    return formatted


def data_from_text(in_text, in_seperator):
    cleared = in_text.replace(in_seperator, "")
    tmp_data = zlib.decompress(binascii.a2b_base64(cleared.encode("ascii")))
    return tmp_data


def get_suggested_output(in_file_path, in_is_txt):
    in_fp = pathlib.Path(in_file_path)
    if str(in_fp) == "":
        suggested_name = "file2txt_output.txt"
    elif in_is_txt:
        suggested_name = str(in_fp.stem)
    else:
        suggested_name = str(in_fp.name) + ".txt"

    out_path = str(pathlib.Path.cwd() / suggested_name)
    if shutil.which("kdialog") is not None:
        out_path = subprocess.run(['kdialog', '--getsavefilename', f'{out_path}'],
                                  stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    elif shutil.which("zenity") is not None:
        out_path = subprocess.run(
            ['zenity', '--file-selection', '--title="Save File as"', '--save', '--filename', f'{out_path}'],
            stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]

    return out_path


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected, possible values: yes, y, true, 1, no, n, false, 0.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Transforms files to text and vise-versa. '
                                                 'Useful to embed images inside code for example.')
    parser.add_argument('-i', '--input', help='path to input file', type=str, metavar='\b', default=INPUT)
    parser.add_argument('-o', '--output', help='output file path', type=str, metavar='\b', default=OUTPUT)
    parser.add_argument('-n', '--num_char', help='number of characters per line in the output', type=int,
                        default=NUM_CHARACTERS_PER_LINE, metavar='\b')
    parser.add_argument('-s', '--seperator', help='character that separates each line in the output', type=str,
                        default=SEPERATOR, metavar='\b')
    parser.add_argument('-p', '--print', help='print output instead of saving it to file', type=str2bool,
                        default=PRINT_OUTPUT, metavar='\b')
    parser.add_argument('-k', '--inkscape_mode', help='transform inkscape svg to regular svg before processing',
                        type=str2bool, default=INKSCAPE_MODE, metavar='\b')
    args = parser.parse_args()

    if args.inkscape_mode:
        is_txt, data = get_input_text_from_inkscape_svg(args.input)
    else:
        is_txt, data = get_input_text(args.input)

    if len(data) == 0:
        print("ERROR: no data provided")
        quit()
    if is_txt:
        processed_data = data_from_text(data, args.seperator)
    else:
        processed_data = data_to_text(data, args.num_char, args.seperator)

    w_mode = "w"
    if isinstance(processed_data, bytes):
        w_mode = "wb"

    if args.print:
        if is_txt:
            print("cannot print none text data")
        else:
            print(processed_data)
    else:
        output_path = args.output
        if args.output == "":
            output_path = get_suggested_output(args.input, is_txt)

        try:
            with open(output_path, w_mode) as f:
                f.write(processed_data)
            print(f"successfully saved file to: {output_path}")
        except IOError:
            print(f"ERROR: could not save data in: {output_path}")
