#!/usr/bin/python3
from PIL import Image, ImageDraw, ImageFont
import argparse
import tempfile
import os
import pathlib
import shutil
import subprocess


ART = True
INPUT_TEXT = ""
TEXT_COLOR = "255,155,0"
FFMPEG_VERBOSE = "quiet"
RESOLUTION = (600, 600)
TEXT_BBOX = (300, 200)
FONT = "DejaVuSans"
JUSTIFY = "center"
FPS = 30
VIDEO_LENGTH = 1.5
ANTIALIASING = False


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = """
    888888            db    88b 88 88 8b    d8    db    888888 88  dP"Yb  88b 88
      88             dPYb   88Yb88 88 88b  d88   dPYb     88   88 dP   Yb 88Yb88
      88   .o.      dP__Yb  88 Y88 88 88YbdP88  dP__Yb    88   88 Yb   dP 88 Y88
      88   `"'     dP""\""Yb 88  Y8 88 88 YY 88 dP""\""Yb   88   88  YbodP  88  Y8
    """
    if in_art:
        print(intro)
    print((" starting text animation ".center(80, "=")))
    print("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.
    ______     d88ooo  888_dPY8   88   8     ______
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX
             88bdPPP   Y8P   Y8   88oop'
    """
    print((" text animation finished ".center(80, "=")))
    if in_art:
        print(end)


def progress(count, total, status=''):
    bar_len = 40
    end_char = ''
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * (count + 1) / float(total), 1)

    bar = '=' * (filled_len - 1) + '>' + ' ' * (bar_len - filled_len)
    if count == total - 1:
        bar = '=' * bar_len
        end_char = '\n'
    msg = '\r[%s] %s%s [%s/%s] ... %s ' % (bar, percents, '%', count + 1, total, status)
    print(msg, end=end_char, flush=True)


def get_font_path(font_name):  # only for linux right now
    font_p = pathlib.Path(font_name)
    if font_p.is_file():
        if font_p.suffix == ".ttf":
            return font_name
    reduced_font_name = font_name.replace(" ", "").lower()
    if not reduced_font_name.endswith(".ttf"):
        reduced_font_name += ".ttf"

    # print(f"reduced: {reduced_font_name}")
    fonts_dict = {}
    installed_fonts = subprocess.run(["fc-list"], stdout=subprocess.PIPE).stdout.decode('utf-8').split("\n")
    for installed in installed_fonts:
        installed_path = installed.split(":")[0].strip()

        installed_name = pathlib.Path(installed_path).name.replace(" ", "").lower()
        fonts_dict[installed_name] = installed_path
        # print(installed_path)
        if installed_name == reduced_font_name:
            return installed_path
    for n, p in fonts_dict.items():
        if reduced_font_name[:-4] in n:
            return p
    alt_font_path = pathlib.Path(__file__).parent / "text_animator_overpass_font.ttf"
    if alt_font_path.is_file():
        return str(alt_font_path)
    return ""


def get_input_text():
    if shutil.which("zenity") is not None:
        res = subprocess.run(["zenity", "--entry" ,"--title", 'input', "--text", 'Please enter the animation text:'],
                             stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    elif shutil.which("kdialog") is not None:
        res = subprocess.run(["kdialog", "--title", "Input", "--inputbox", "Please enter the animation text:"],
                             stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    else:
        res = input("Please enter the animation text:")
    # print("=>" + res)
    return res


def choose_font_size(in_text, in_resolution, text_bbox, in_font):
    original = Image.new("RGB", in_resolution, (0, 255, 0))

    f_size = 0
    overflow = False
    while not overflow:
        f_size += 1
        draw = ImageDraw.Draw(original)
        font = ImageFont.truetype(in_font, f_size)
        bbox = draw.multiline_textbbox((1, 1), in_text, font=font)
        if bbox[2] - bbox[0] > text_bbox[0] or bbox[3] - bbox[1] > text_bbox[1]:
            overflow = True
        if f_size >= text_bbox[0]:
            overflow = True
        # print(f"bbox = [{bbox}] , f_size = {f_size}")
    f_size -= 1
    return f_size


def draw_typing_images(in_text, path, f_size, out, in_font, in_resolution, in_color, in_justify, in_antialiasing):
    progress_text = ""
    draw_justify = "m"
    if in_justify == "left":
        draw_justify = "r"
    elif in_justify == "right":
        draw_justify = "l"

    for i in range(len(in_text)):
        # print(progress_text)
        progress(i, len(in_text), "drawing images")
        progress_text += in_text[i]
        if not in_antialiasing:
            img = Image.new("RGBA", in_resolution, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(in_font, f_size)
            draw.multiline_text((int(in_resolution[0] / 2), int(in_resolution[1] / 2)), progress_text,
                                (in_color[0], in_color[1], in_color[2]), font=font, anchor=draw_justify + "m")
        else:
            img = Image.new("RGBA", (in_resolution[0] * 2, in_resolution[1] * 2), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(in_font, f_size * 2)
            draw.multiline_text((int(in_resolution[0] ), int(in_resolution[1])), progress_text,
                                (in_color[0], in_color[1], in_color[2]), font=font, anchor=draw_justify + "m")
            img = img.resize(in_resolution, resample=Image.ANTIALIAS)
        img.save(str(path / f"{i:03d}.png"))
        if i == len(in_text) - 1:
            img.save(out + ".png")


def merge_images_into_video(in_text, path, out, in_verbose, in_fps, in_video_length):
    # letters_speed = int(round((float(len(in_text))) / in_video_length))
    letters_speed = (float(len(in_text)) / in_video_length)
    cmd = f'ffmpeg -y -framerate {letters_speed} -i { path / "%03d.png"} -hide_banner -loglevel {in_verbose} '
    cmd += f' -vcodec png -r {in_fps} {out}.mov'
    # print(cmd)
    os.system(cmd)


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
    return res[0], res[1], res[2], 255


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Create a text typing animation video with a transparent background.'
                                                 'The font size is calculated automatically from the '
                                                 'text_bbox variable')
    parser.add_argument('-i', '--input', help='the input text (to be animated)',
                        type=str, default=INPUT_TEXT, metavar='\b')
    parser.add_argument('-r', '--resolution', help='output video resolution',
                        nargs='+', type=int, default=RESOLUTION, metavar='\b')
    parser.add_argument('-t', '--text_bbox', help='text bounding box size (text will be fit to this box)',
                        nargs='+', type=int, default=TEXT_BBOX, metavar='\b')
    parser.add_argument('-f', '--font', help='font name (will search in system using "fc-list" command), or font path',
                        type=str, default=FONT, metavar='\b')
    parser.add_argument('-p', '--fps', help='fps of the output video', type=int, default=FPS, metavar='\b')
    parser.add_argument('-l', '--length', help='length of video in seconds',
                        type=float, default=VIDEO_LENGTH, metavar='\b')
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: error, warning or info', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-n', '--antialiasing', help='activate anti aliasing but with longer processing time',
                        type=bool, default=ANTIALIASING, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-c', '--color', help='text font color', type=str,  default=TEXT_COLOR, metavar='\b')
    parser.add_argument('-j', '--justify', help='justify (align) text to left, right, center', type=str, metavar='\b',
                        default=JUSTIFY)
    parser.add_argument('-o', '--output', help='output video path. (without extension)', type=str, metavar='\b',
                        default="text_animation")
    parser.add_argument('-a', '--art', help='Display ASCII art', type=bool,
                        default=ART, metavar='\b', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    font_path = get_font_path(args.font)
    # print("Font path: " + font_path)
    if font_path == "":
        print("ERROR: Could not find path for the provided font: " + args.font)
        quit()

    intro_print(args.art)

    print(f"font path: {font_path}")
    input_text = args.input
    if input_text == "":
        input_text = get_input_text()
    if input_text == "":
        print("Warning: Empty input text")
        exit(0)

    color = tuple(parse_color(args.color))

    font_size = choose_font_size(input_text, args.resolution, args.text_bbox, font_path)
    print(f"estimated font size: {font_size}")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        print("generating png images")
        draw_typing_images(input_text, tmp_path, font_size, args.output, font_path,
                           args.resolution, color, args.justify, args.antialiasing)
        print("merging the pictures into one video")
        print(f"saving the final image, path: {args.output}.png")
        merge_images_into_video(input_text, tmp_path, args.output, args.verbose, args.fps, args.length)
        print(f"saving video, path: {args.output}.mov")
        print("")

    end_print(args.art)
