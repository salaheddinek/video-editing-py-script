#!/usr/bin/env python3
import pathlib
import argparse
import shutil
import os
import platform


SIZE = [600, 600]  # width, height
COLOR = '255,0,125'  # rgb
THICKNESS = 12
SHAPE = "ellipse"  # possible value: "rectangle", "ellipse", "line"
ROUNDED_CORNERS = 0
SHAPE_WIDTH_TO_HEIGHT_RATIO = 0.6  # ratio between longest and smallest edge (should be <= 1)
OUTPUT = ''
DEBUG = False


def generate_xml_header(in_im_size):
    s = " " * 3
    txt = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    txt += '<svg\n'
    txt += s + f'height="{in_im_size[1]}px"\n'
    txt += s + f'width="{in_im_size[0]}px"\n'
    txt += s + f'viewBox="0 0 {in_im_size[0]} {in_im_size[1]}"\n'
    txt += s + 'id="svg5ss">\n'
    return txt


def draw_shape(i_size, i_ratio, i_color, i_thickness, i_shape, in_rounded_corners):
    s3 = " " * 3
    s2 = " " * 2
    center = (int(i_size[0] / 2), int(i_size[1] / 2))
    length = int(min(i_size) * 3 / 4)
    style1 = f'fill="none" stroke="rgb({i_color[0]},{i_color[1]},{i_color[2]})" stroke-width="{i_thickness}"\n'
    style2 = f'style="stroke-linecap:round;stroke-linejoin:round" />\n'
    txt = ""
    if i_shape == "rectangle":
        txt += s2 + '<rect\n'
        txt += s2 + s3 + 'id="rect5"\n'
        txt += s2 + s3 + f'x="{center[0]  - length / 2:.5f}"\n'
        txt += s2 + s3 + f'y="{center[1]- (length / 2) * i_ratio:.5f}"\n'
        txt += s2 + s3 + f'width="{length:.5f}"\n'
        txt += s2 + s3 + f'height="{length * i_ratio:.5f}"\n'
        if in_rounded_corners > 0:
            txt += s2 + s3 + f'rx="{length * i_ratio * in_rounded_corners:.5f}"\n'

    elif i_shape == "ellipse":
        txt += s2 + '<ellipse\n'
        txt += s2 + s3 + 'id="ellipse6"\n'
        txt += s2 + s3 + f'cx="{center[0]:.5f}"\n'
        txt += s2 + s3 + f'cy="{center[1]:.5f}"\n'
        txt += s2 + s3 + f'rx="{length / 2:.5f}"\n'
        txt += s2 + s3 + f'ry="{length * i_ratio / 2:.5f}"\n'
    elif i_shape == "line":
        txt += s2 + '<path\n'
        txt += s2 + s3 + 'id="path7"\n'
        txt += s2 + s3 + f'd="m {center[0]:.5f},{i_size[1] * 1 / 4:.5f} V {i_size[1] * 3 / 4:.5f}"\n'
    else:
        print('WARNING: invalid SHAPE, please select one of: "rectangle", "ellipse", "line" ')
    txt += s2 + s3 + style1
    txt += s2 + s3 + style2
    return txt


def parse_color(in_c: str):
    c_str = in_c.lower().strip(" #()")
    if c_str.startswith("rgb"):
        c_str = c_str[3:].strip(" ()")
    if c_str.startswith("rgba"):
        c_str = c_str[4:].strip(" ()")
    res = []
    if len(c_str) == 6:
        res = [int(c_str[i:i+2], 16) for i in (0, 2, 4)]
    else:
        c_str = c_str.replace(",", " ")
        for word in c_str.split(" "):
            if word.isnumeric():
                if 0 <= int(word) <= 255:
                    res += [int(word)]
    if len(res) < 3:
        raise ValueError(f'ERROR: the color {in_c} could not parsed as color, please use HEX or "R,G,B" color format')
    return res[0], res[1], res[2]


def check_size(i_size):
    if len(i_size) != 2:
        return SIZE
    if i_size[0] < 1 or i_size[1] < 1:
        return SIZE
    return i_size


def check_ratio(i_ratio):
    if i_ratio < 0 or i_ratio > 1:
        return SHAPE_WIDTH_TO_HEIGHT_RATIO
    return i_ratio


def check_shape(i_shape):
    if i_shape != "rectangle" and i_shape != "ellipse" and i_shape != "line":
        print(f"WARNING: The shape '{i_shape}' is not recognized, '{SHAPE}' is used instead.")
        return SHAPE
    return i_shape


def check_rounded_corner_percentage(i_rc):
    if i_rc < 0:
        return 0
    if i_rc > 0.5:
        return 0.5
    return i_rc


def produce_and_copy_additional_cmd_line(i_color, i_thickness, i_out_path):
    animation_script = pathlib.Path(__file__).parent / "svg_animator.py"
    if not animation_script.is_file():
        return
    cmd = f'{animation_script} -i {i_out_path} -c {i_color[0]},{i_color[1]},{i_color[2]} -w {i_thickness}'
    if platform.system().lower() == "windows":
        cmd = "py " + cmd
    print('to create an animation from the SVG file, use the following command:\n\n')
    print(cmd)
    print("")
    if shutil.which("xclip"):
        os.system(f'echo "{cmd}" | xclip -select clipboard')
        print("the command has been copied to the clipboard (Ctrl+V)\n")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='generate simple shape in the form of SVG file.')
    parser.add_argument('-s', '--size', help='size = (width, height) is the dimensions of the output video',
                        nargs='+', type=int, default=SIZE, metavar='\b')
    parser.add_argument('-c', '--color', help='color = (red, green, blue) is the color of the shape; max value is 255',
                        type=str, default=COLOR, metavar='\b')
    parser.add_argument('-t', '--thickness', help='thickness of the shape in pixels', type=int,
                        default=THICKNESS, metavar='\b')
    parser.add_argument('-a', '--shape', help='shape, option: "rectangle", "ellipse", "line"', type=str,
                        default=SHAPE, metavar='\b')
    parser.add_argument('-n', '--corners', help='the percentage of rounded corners, should be in [0,0.5]', type=float,
                        default=ROUNDED_CORNERS, metavar='\b')
    parser.add_argument('-r', '--ratio', help='ratio between longest and smallest edge, should be in [0,1]', type=float,
                        default=SHAPE_WIDTH_TO_HEIGHT_RATIO, metavar='\b')
    parser.add_argument('-o', '--output', help='name of the output file name', type=str,
                        default=OUTPUT, metavar='\b')
    args = parser.parse_args()

    in_size = check_size(args.size)
    in_color = parse_color(args.color)
    in_ratio = check_ratio(args.ratio)
    in_shape = check_shape(args.shape)
    in_rc_percentage = check_rounded_corner_percentage(args.corners)
    output = f"{in_shape}.svg"
    if args.output != "":
        output = args.output
    if not output.endswith(".svg"):
        output += ".svg"

    svg_txt = generate_xml_header(in_size)
    svg_txt += draw_shape(in_size, in_ratio, in_color, args.thickness, in_shape, in_rc_percentage)

    svg_txt += "</svg>"
    out_path = pathlib.Path(output)
    # print(svg_txt)
    with out_path.open("w") as f:
        f.write(svg_txt)

    print(f"finished generating the SVG file, path: {out_path}")
    produce_and_copy_additional_cmd_line(in_color, args.thickness, out_path)
