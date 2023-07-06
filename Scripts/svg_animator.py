#!/usr/bin/env python3
import pathlib
import argparse
import svg.path
import xml.etree.ElementTree as Xee
from PIL import Image, ImageDraw
from datetime import datetime
import enum
import tempfile
import math
import os
import shutil


INPUT = ""
OUTPUT = ""
FPS = 25
FFMPEG_VERBOSE = "error"
COLOR = "204,102,255"
NUM_FRAMES = 75
POPUP_LAST_FRAME = 20
DISAPPEAR_FIRST_FRAME = 55
MODE = 4  # 0:linear, 1:polynomial, 2:exponential, 3:blinks, 4:sigmoid
STEEPNESS = 2
LINE_WIDTH = 5
ANTIALIASING = False
ART = True
DEBUG = False


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = '''
        .dP"Y8 Yb    dP  dP""b8     Yb    dP        db        
        `Ybo."  Yb  dP  dP   `"      Yb  dP        dPYb       
        o.`Y8b   YbdP   Yb  "88       YbdP   .o.  dP__Yb  .o. 
        8bodP'    YP     YboodP        YP    `"' dP""""Yb `"' 
    '''

    if in_art:
        print(intro)
    print((" starting SVG animation ".center(80, "=")))
    print("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.
    ______     d88ooo  888_dPY8   88   8     ______
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX
             88bdPPP   Y8P   Y8   88oop'
    """
    print((" starting SVG animation finished ".center(80, "=")))
    if in_art:
        print(end)


class TransitionMathFunction:
    class Types(enum.Enum):  # steepness factor (s) controls how fast the function converge
        linear = 0  # f(x) = c1 * x + c2
        polynomial = 1  # f(x) = c1 * x^s + c2
        exponential = 2  # f(x) = c1 * exp(10 * s * x) + c2
        steps = 3  # f(x) = number of steps is equal  steepness factor
        sigmoid = 4  # f(x) = symmetric polynomial

    def __init__(self, a=0.0, f_a=0.0, b=1.0, f_b=1.0, fun_type=Types.linear, steepness_factor=3.0):
        self.a = a
        self.f_a = f_a
        self.b = b
        self.f_b = f_b
        self.type = fun_type
        self.s = steepness_factor
        self.round_output = False

    def map_value(self, x):
        if self.a >= self.b or self.a < 0:
            print("ERROR: lower bound 'a' should be positive and inferior to upper bound 'b' (0 <= a < b)")
            return []
        if self.s <= 0:
            print("ERROR: steepness functor should be strictly positive")
            return []
        if isinstance(x, (int, float)):
            x = [x]
        self.a, self.b, self.f_a, self.f_b = float(self.a), float(self.b), float(self.f_a), float(self.f_b)

        if self.type == self.Types.linear:
            return self._linear(x)
        if self.type == self.Types.polynomial:
            return self._polynomial(x)
        if self.type == self.Types.exponential:
            return self._exponential(x)
        if self.type == self.Types.steps:
            return self._steps(x)
        if self.type == self.Types.sigmoid:
            return self._sigmoid(x)
        else:
            return self._linear(x)

    def _linear(self, x):
        c1 = (self.f_b - self.f_a) / (self.b - self.a)
        c2 = self.f_a - c1 * self.a
        return self._process_result([c1 * xi + c2 for xi in x], x)

    def _polynomial(self, x):
        c1 = (self.f_b - self.f_a) / ((self.b - self.a) ** self.s)
        c2 = self.f_a
        tmp1 = self._process_result([c1 * ((xi - self.a) ** self.s) + c2 for xi in x], x)
        return tmp1

    def _exponential(self, x):
        c1 = (self.f_b - self.f_a) / (math.exp(10 * self.s) - math.exp(0))
        c2 = self.f_a - c1 * math.exp(0)
        return self._process_result([c1 * math.exp(10 * (xi - self.a) * self.s / (self.b - self.a)) + c2 for xi in x],
                                    x)

    def _steps(self, x):
        s = round(self.s)
        res = []
        for xi in x:
            if round((xi - self.a) / ((self.b - self.a) / (2 * s + 1))) % 2:
                res += [self.f_b]
            else:
                res += [self.f_a]
        return self._process_result(res, x)

    def _sigmoid(self, x):
        hp = (self.b + self.a) / 2
        f_hp = (self.f_b + self.f_a) / 2
        c2 = self.f_a
        c1 = (f_hp - self.f_a) / ((hp - self.a) ** self.s)

        c4 = self.f_b
        c3 = (f_hp - self.f_b) / ((hp - self.b) ** self.s)
        res = []
        for xi in x:
            if xi <= hp:
                yi = c1 * (xi - self.a) ** self.s + c2
            else:
                # print(xi - self.b)
                yi = c3 * (xi - self.b) ** self.s + c4
            res += [yi.real]
        # print(f"c1:{c1}  c2:{c2}  c3:{c3}  c4:{c4}  f_hp:{f_hp}")
        # [print(yi) for yi in res]
        return self._process_result(res, x)

    def _process_result(self, in_y, in_x):
        for i in range(len(in_y)):
            if in_x[i] <= self.a:
                in_y[i] = self.f_a
            elif in_x[i] >= self.b:
                in_y[i] = self.f_b

        if self.round_output:
            return [round(yi) for yi in in_y]
        return in_y

    def debug_function(self, in_title="Function graph"):
        try:
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            print("WARNING: to debug function graph, 'numpy and 'matplitlib' package should be installed first")
            return
        x = np.linspace(self.a, self.b, 100)
        y = np.array(self.map_value(x.tolist()))
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        plt.grid(True)
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('left')
        plt.plot(x, y, 'r')
        plt.plot([self.a], [self.f_a], 'g.', markersize=10)
        plt.plot([self.b], [self.f_b], 'b.', markersize=10)
        plt.title(in_title)
        plt.show()


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


def get_ordered_points(in_init_pts):
    histogram = [[] for _ in range(256)]
    # checked = set()
    # reduced = []
    # for p in in_init_pts:
    #     p_r = (round(p[0]), round(p[1]))
    #     if p_r not in checked:
    #         reduced.append(p)
    #         checked.add(p_r)
    # print(f"the number of point have been reduced from{len(in_init_pts)} to {len(reduced)}")

    for i, p in enumerate(in_init_pts):
        h_idx = int(math.floor(i * 256 / len(in_init_pts)))
        histogram[h_idx].append(p)
    return histogram


def get_indices_bounds(num_levels, last_popup_frame, first_disappear_frame, last_frame, mode=0, steepness=1,
                       debug=False):
    n, f, l, a = num_levels, first_disappear_frame, last_popup_frame, last_frame
    func1 = TransitionMathFunction(0, -1, l, num_levels + 1, TransitionMathFunction.Types.linear, steepness)
    func2 = TransitionMathFunction(f, -1, a, num_levels + 1, TransitionMathFunction.Types.linear, steepness)
    func1.round_output = True
    func2.round_output = True
    x = [i for i in range(last_frame)]

    if mode == 0:
        func1.type = TransitionMathFunction.Types.linear
        func2.type = TransitionMathFunction.Types.linear
    if mode == 1:
        func1.type = TransitionMathFunction.Types.polynomial
        func2.type = TransitionMathFunction.Types.polynomial
    elif mode == 2:
        func1.type = TransitionMathFunction.Types.exponential
        func2.type = TransitionMathFunction.Types.exponential
    elif mode == 3:
        func1.type = TransitionMathFunction.Types.steps
        func2.type = TransitionMathFunction.Types.steps
    elif mode == 4:
        func1.type = TransitionMathFunction.Types.sigmoid
        func2.type = TransitionMathFunction.Types.sigmoid
    else:
        func1.type = TransitionMathFunction.Types.linear
        func2.type = TransitionMathFunction.Types.linear
    if debug:
        func1.debug_function("Popup animation graph")
        func2.debug_function("Disappear animation graph")
    return func1.map_value(x), func2.map_value(x)


def get_points_to_draw_indices(im_idx, in_up_bounds, in_down_bounds, num_levels):
    indices = []
    for i in range(num_levels):
        if i <= in_down_bounds[im_idx]:
            if i >= in_up_bounds[im_idx]:
                indices += [i]
    return indices


def ellipse_to_path(in_x, in_y, in_rx, in_ry):
    d = f"M {in_x - in_rx},{in_y}"
    d += f" a {in_rx},{in_ry} 0 1,0 {in_rx * 2},0"
    d += f" a {in_rx},{in_ry} 0 1,0 {-in_rx * 2},0 z"
    return d


def rect_to_path(in_x, in_y, in_h, in_w, in_rx, in_ry):
    rrx = in_rx
    rry = in_ry
    if rrx == 0 and rry != 0:
        rrx = rry
    if rrx != 0 and rry == 0:
        rry = rrx

    d = f"m {in_x + rrx},{in_y}"
    d += f" L {in_x + in_w - rrx},{in_y}"
    d += f" Q {in_x + in_w},{in_y} {in_x + in_w},{in_y + rry}"
    d += f" L {in_x + in_w},{in_y + in_h - rry}"
    d += f" Q {in_x + in_w},{in_y + in_h} {in_x + in_w - rrx},{in_y + in_h}"
    d += f" L {in_x + rrx},{in_y + in_h}"
    d += f" Q {in_x},{in_y + in_h} {in_x},{in_y + in_h - rry}"
    d += f" L {in_x},{in_y + rry}"
    d += f" Q {in_x},{in_y} {in_x + rrx},{in_y}"
    return d


def determine_path_points(in_path):
    pp = svg.path.parse_path(in_path)
    print("estimating the appropriate number of points")
    for num_point in range(3, 100000):
        if num_point % 10000 == 0:
            print(f"number of points reached {num_point} ...")
        is_ok = True
        pts = [pp.point(0)]

        for i in range(num_point - 1):
            cur = pp.point(i / (num_point - 1))
            if abs(cur.real - pts[-1].real) > 0.8 or abs(cur.imag - pts[-1].imag) > 0.8:
                is_ok = False
                break
            pts.append(cur)
        if is_ok:
            print(f"num of points determined: {num_point}")
            return [(x.real, x.imag) for x in pts]


def get_image_size(in_xml_root):
    if "viewBox" not in in_xml_root.attrib:
        raise ValueError('ViewBox not found in svg file, Could not retrieve image size')
    words = in_xml_root.attrib["viewBox"].split(" ")
    return int(words[2]), int(words[3])


def draw_current_image(all_points, indices, img_size, save_path, rgba_color=(255, 0, 0, 255), point_size=5):
    new_img = Image.new(mode="RGBA", size=img_size, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(new_img)
    for line_idx in indices:
        for p in all_points[line_idx]:
            bbox = [p[0] - point_size / 2, p[1] - point_size / 2, p[0] + point_size / 2, p[1] + point_size / 2]
            draw.ellipse(bbox, fill=rgba_color)
    new_img.save(str(save_path))


def draw_current_image_anti_aliasing(all_points, indices, img_size, save_path,
                                     rgba_color=(255, 0, 0, 255), point_size=5):
    new_img = Image.new(mode="RGBA", size=(img_size[0] * 2, img_size[1] * 2), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(new_img)
    for line_idx in indices:
        for p in all_points[line_idx]:
            bbox = [p[0] * 2 - point_size, p[1] * 2 - point_size, p[0] * 2 + point_size, p[1] * 2 + point_size]
            draw.ellipse(bbox, fill=rgba_color)

    new_img = new_img.resize(img_size, resample=Image.ANTIALIAS)
    new_img.save(str(save_path))


def get_initial_points(xml_root):

    for child in xml_root:
        if "path" in child.tag.lower():
            path_str = child.attrib['d']
            return determine_path_points(path_str)

        if "ellipse" in child.tag.lower():
            e_cx = float(child.attrib['cx'])
            e_cy = float(child.attrib['cy'])
            e_rx = float(child.attrib['rx'])
            e_ry = float(child.attrib['ry'])
            elp_path = ellipse_to_path(e_cx, e_cy, e_rx, e_ry)
            return list(reversed(determine_path_points(elp_path)))

        if "circle" in child.tag.lower():
            e_cx = float(child.attrib['cx'])
            e_cy = float(child.attrib['cy'])
            e_rx = float(child.attrib['r'])
            e_ry = float(child.attrib['r'])
            elp_path = ellipse_to_path(e_cx, e_cy, e_rx, e_ry)
            return list(reversed(determine_path_points(elp_path)))

        if "rect" in child.tag.lower():
            r_x = float(child.attrib['x'])
            r_y = float(child.attrib['y'])
            r_h = float(child.attrib['height'])
            r_w = float(child.attrib['width'])
            r_rx, r_ry = 0, 0
            if "ry" in child.attrib:
                r_ry = float(child.attrib['ry'])
            if "rx" in child.attrib:
                r_ry = float(child.attrib['rx'])
            rect_path = rect_to_path(r_x, r_y, r_h, r_w, r_rx, r_ry)
            return determine_path_points(rect_path)


def merge_images_into_video(in_tmp_path, out, in_verbose, in_fps):
    cmd = f'ffmpeg -y -i {in_tmp_path / "%03d.png"} -hide_banner -loglevel {in_verbose} '
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


def pretty_time_delta(t_delta):
    seconds = int(t_delta.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%d d %d h %d m %d s' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '%d h %d m %d s' % (hours, minutes, seconds)
    elif minutes > 0:
        return '%d m %d s' % (minutes, seconds)
    else:
        return '%d s' % (seconds,)


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
                                     description='Create a line animation video from a svg file, '
                                                 'the supported shapes: path, ellipse, circle and rect. Only the first'
                                                 ' shape presented in the file is animated')
    parser.add_argument('-i', '--input', help='path to input svg file', type=str, metavar='\b', default=INPUT)
    parser.add_argument('-o', '--output', help='output video path. (without extension)', type=str, metavar='\b',
                        default=OUTPUT)
    parser.add_argument('-f', '--fps', help='frame per second of the output video', type=int, default=FPS, metavar='\b')
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: error, warning or info', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-c', '--color', help='line color', type=str, default=COLOR, metavar='\b')
    parser.add_argument('-n', '--num_frames', help='the total number of frames in the output video',
                        type=int, default=NUM_FRAMES, metavar='\b')
    parser.add_argument('-p', '--popup_frame', help='the last frame index of the popup animation', type=int,
                        default=POPUP_LAST_FRAME, metavar='\b')
    parser.add_argument('-d', '--disappear_frame', help='the first frame index of the disappear animation',
                        type=int, default=DISAPPEAR_FIRST_FRAME, metavar='\b')
    parser.add_argument('-m', '--mode', help='animation mode: 0:linear, 1:polynomial, 2:exponential, 3:blinks, '
                                             '4:sigmoid', type=int, metavar='\b', default=MODE)
    parser.add_argument('-s', '--steepness', help='controls how fast the animation (depends on the mode)',
                        type=float, metavar='\b', default=STEEPNESS)
    parser.add_argument('-w', '--width', help='line width in pixels', type=int, metavar='\b', default=LINE_WIDTH)
    parser.add_argument('-t', '--antialiasing', help='activate anti aliasing but with longer processing time',
                        type=str2bool, default=ANTIALIASING, metavar='\b')
    parser.add_argument('-a', '--art', help='Display ASCII art', type=str2bool, default=ART, metavar='\b')
    parser.add_argument('-g', '--debug', help='show debug information and graphs', type=str2bool,
                        default=DEBUG, metavar='\b')
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    start_time = datetime.now()

    in_file = pathlib.Path(args.input)
    if not in_file.is_file():
        print(f"ERROR: input SVG file not found, provided path: '{in_file}'")
        exit(1)

    color = tuple(parse_color(args.color))

    intro_print(args.art)

    svg_tree = Xee.parse(str(in_file))
    root = svg_tree.getroot()

    im_size = get_image_size(root)
    init_pts = get_initial_points(root)
    ordered_points = get_ordered_points(init_pts)

    output = f"{in_file.stem}_d{args.num_frames}_f{args.fps}_s{im_size[0]}-{im_size[1]}"
    if args.output != "":
        output = args.output
    down_bounds, up_bounds = get_indices_bounds(len(ordered_points), args.popup_frame,  args.disappear_frame,
                                                args.num_frames, args.mode, args.steepness, args.debug)
    if args.debug:
        [print(f"idx:{ii} => down_bnd:{down_bounds[ii]}, up_bnd:{up_bounds[ii]}") for ii in range(args.num_frames)]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        for idx in range(args.num_frames):
            indices_to_draw = get_points_to_draw_indices(idx, up_bounds, down_bounds, len(ordered_points))
            # print(f"idx:{idx} => [{len(indices_to_draw)}]")
            progress(idx, args.num_frames, "drawing images")
            img_path = tmp_path / f"{idx:03d}.png"
            if args.antialiasing:
                draw_current_image_anti_aliasing(ordered_points, indices_to_draw, im_size, img_path, color, args.width)
                if args.debug:
                    draw_current_image_anti_aliasing(ordered_points, range(len(ordered_points)), im_size,
                                                     output + "_debug.png",  color, args.width)
            else:
                draw_current_image(ordered_points, indices_to_draw, im_size, img_path, color, args.width)
                if args.debug:
                    draw_current_image(ordered_points, range(len(ordered_points)), im_size,
                                       output + "_debug.png",  color, args.width)
            tmp = 1

        print("merging images to the output video")
        merge_images_into_video(tmp_path, output, args.verbose, args.fps)

    print("")
    print("video animation creation finished. Duration = {} ".format(pretty_time_delta(datetime.now() - start_time)))
    print("")
    end_print(args.art)
