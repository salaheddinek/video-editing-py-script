#!/usr/bin/env python3
import argparse
import tempfile
import colorsys
import os
import pathlib
import shutil
import subprocess
import copy
import math
import random
from enum import Enum
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


# +-----------------------------------------------------
# |         global variables
# +-----------------------------------------------------
# | 
# | global variables used in the script are divided
# | into two lists, the first one contains variables 
# | that can be changed via command line using argparse.
# | and the second one contains variables which are less
# | relevant (starts with '_'), and thus can only be set 
# | inside the script
# | 
# +-----------------------------------------------------

ART = True
INPUT_TEXT = ""
TEXT_COLOR = "255,155,0"
FFMPEG_VERBOSE = "quiet"
RESOLUTION = (600, 600)
TEXT_BBOX = (300, 200)
# RESOLUTION = (1920, 1080)
# TEXT_BBOX = (1000, 500)
STYLED_TEXT = True
FONT = "DejaVuSans"
JUSTIFY = "center"
FPS = 30
VIDEO_LENGTH = 1.5
ANTIALIASING = True
ANIMATION_TYPE = "typing"
ANIMATION_AMPLITUDE = 0.02
ANIMATION_FREQUENCY = 0.8



# internal variables
_NEW_LINE_CHARACTER = "|"  # character which will be replaced by a line break
_DEBUG_IMAGE = False  # produce an image with an opaque background and the bounding box (only for debug)
_DEBUG_IMAGE_BG_COLOR = (255, 255, 255, 255)  # color of the debug background image
_INNER_TOP_COLOR = (250, 250, 250)  # if STYLED_TEXT is set to True this ise used as the color of top edge
_INNER_BOTTOM_COLOR = (215, 215, 215)  # if STYLED_TEXT is set to True this ise used as the color of bottom edge
_OUTER_COLOR_PERCENTAGE_WIDTH = 0.07  # if STYLED_TEXT is set to True: percentage of the outer color
_OUTER_COLOR_LUMINOSITY_VARIATION = 0.2  # if STYLED_TEXT is set to True: the difference of luminosity of top and bottom
_USE_SHADOW = True  # use drop shadow if STYLED_TEXT is set to True
_SHADOW_OPACITY = 0.25  # opacity of the drop shadow when paint text if _USE_SHADOW is set to True
_SHADOW_WIDTH = 0.02  # shadow width percentage compared to font size
_SHADOW_DIRECTION = [1.0, 1.0]  # the direction of the drop shadow
_USE_FIXED_SEED = False  # in set to true then script will always use the same result (only for VIBRATION and WIGGLE)
_FIXED_SEEDS = (7, 9)  # will be used if _USE_FIXED_SEED is set to True
_RANDOM_SEEDS = (random.randint(0, 10000), random.randint(0, 10000))  # will be used if _USE_FIXED_SEED is set to False
_VIBRATION_OCTAVES = 1  # for Perlin Noise used in VIBRATION animation
_VIBRATION_INTERPOLATION = "cosine"  # for Perlin Noise used in VIBRATION animation


class Animation(Enum):
    """Text animation enumeration"""
    NONE = 0
    TYPING = 1
    VIBRATION = 2
    WIGGLE = 3

    @staticmethod
    def get_animations_listing():
        result = []
        for ani in Animation:
            result += [ani.name.lower()]
        return result


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

    p_bar = '=' * (filled_len - 1) + '>' + ' ' * (bar_len - filled_len)
    if count == total - 1:
        p_bar = '=' * bar_len
        end_char = '\n'
    msg = '\r[%s] %s%s [%s/%s] ... %s ' % (p_bar, percents, '%', count + 1, total, status)
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
    if shutil.which("fc-list"):
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


class TextPainter():
    """paint a text image"""
    def __init__(self, text, text_bbox, color, is_styled, font, justify, resolution, antialiasing):
        self.text = text.replace(_NEW_LINE_CHARACTER, "\n")
        self.text_bbox = text_bbox
        self.text_bbox_original = text_bbox
        self.text_height = 1
        self.num_dilations = 1
        self.color = color
        self.is_styled = is_styled
        self.font = font
        self.justify = "center"
        if justify.lower() == "left":
            self.justify = "left"
        elif justify.lower() == "right":
            self.justify = "right"
        self.resolution = resolution    
        self.resolution_original = resolution    
        self.antialiasing = antialiasing
        if self.antialiasing:
            self.text_bbox = (2 * text_bbox[0], 2 * text_bbox[1])
            self.resolution = (2 * resolution[0], 2 * resolution[1])  
        self.font_size = None
        self.inner_grad = None
        self.outer_grad = None
        self._choose_font_size()
        if is_styled:
            self._build_gradient_boxes()


    def get_image(self, num_letter_to_draw=-1):
        if self.is_styled:
            mask_inner = self._get_none_styled_text(as_mask=True, num_letters=num_letter_to_draw)
            empty1 = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
            img_inner = Image.composite(self.inner_grad, empty1, mask_inner)

            mask_outer = copy.deepcopy(mask_inner)

            for _ in range(self.num_dilations):
                mask_outer = mask_outer.filter(ImageFilter.MaxFilter(size=3))
            empty2 = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
            img_outer = Image.composite(self.outer_grad, empty2, mask_outer)
            img = Image.composite(img_inner, img_outer, mask_inner)
            if _USE_SHADOW:
                img = self._add_shadow(img, mask_outer, empty2)

        else:
            img = self._get_none_styled_text(as_mask=False, num_letters=num_letter_to_draw)
        
        # img = self.inner_grad 
        # img = self.outer_grad  
        if self.antialiasing:
            img = img.resize(self.resolution_original, resample=Image.Resampling.LANCZOS)
        
        if _DEBUG_IMAGE:
            img = self._debug_bounding_box(img)
        return img
    
    def _get_none_styled_text(self, as_mask=False, num_letters=-1):
        img = Image.new("RGBA", self.resolution, (0, 0, 0, 0))

        draw = ImageDraw.Draw(img)
        pil_font = ImageFont.truetype(self.font, self.font_size)
        used_color = (self.color[0], self.color[1], self.color[2])
        if as_mask:
            used_color = (255, 255, 255)
        text_to_draw = self.text
        if num_letters > 0 and num_letters < len(self.text):
            text_to_draw = self.text[:num_letters]
        draw.multiline_text((int(self.resolution[0] / 2), int(self.resolution[1] / 2)), text_to_draw,
                            used_color, font=pil_font, anchor="mm", align=self.justify)
        if as_mask:
            return img.convert('L')
        return img

    def _add_shadow(self, img, mask, empty):
        
        shadow_w = max(int(round(self.font_size * _SHADOW_WIDTH)), 1)
        # print("------ shadow width -----------> " + str(shadow_w))
        enhancer = ImageEnhance.Brightness(img)
        shadow = enhancer.enhance(0.0)
        shadow = shadow.filter(ImageFilter.BoxBlur(shadow_w * 2))
        coefficients = (1, 0, -shadow_w * _SHADOW_DIRECTION[0], 0, 1, -shadow_w * _SHADOW_DIRECTION[1])
        shadow = shadow.transform(img.size, Image.AFFINE, coefficients)
        shadow = Image.blend(empty, shadow, _SHADOW_OPACITY)

        img = Image.composite(img, shadow, mask)
        return img

    def _choose_font_size(self):
        original = Image.new("RGB", self.resolution, (0, 255, 0))

        print("estimating font size ...")
        f_size = 0
        overflow = False
        while not overflow:
            f_size += 1
            draw = ImageDraw.Draw(original)
            pil_font = ImageFont.truetype(self.font, f_size)
            bbox = draw.multiline_textbbox((1, 1), self.text, font=pil_font)
            if bbox[2] - bbox[0] > self.text_bbox[0] or bbox[3] - bbox[1] > self.text_bbox[1]:
                overflow = True
            else:
                self.text_height = bbox[3] - bbox[1]
            if f_size >= self.text_bbox[0]:
                overflow = True
            # print(f"bbox = [{bbox}] , f_size = {f_size}")
        f_size -= 1
        self.font_size = f_size
        print(f"estimated font size: {self.font_size}")
        self.num_dilations = int(math.ceil(self.font_size * _OUTER_COLOR_PERCENTAGE_WIDTH / 3)) + int(self.antialiasing)
        print(f"number of dilations to create outer color: {self.num_dilations}")
    
    def _build_gradient_boxes(self):
        print("building gradient maps ... ")
        self.inner_grad = Image.new("RGBA", self.resolution, (255, 255, 0, 255))
        self.outer_grad = Image.new("RGBA", self.resolution, (255, 255, 0, 255))
        res = self.resolution
        def interpolate(c_start, c_end, num_cells):
            grad_list = []
            for idx in range(num_cells):
                cur_color = []
                for k in range(3):
                    cur_color.append(int(round(c_start[k]- (c_start[k] - c_end[k]) * idx / num_cells)))
                grad_list.append(tuple(cur_color))
            return grad_list

        white_grad = interpolate(_INNER_TOP_COLOR, _INNER_BOTTOM_COLOR, self.text_height)
        color_grad = interpolate(self._change_lightness(self.color, _OUTER_COLOR_LUMINOSITY_VARIATION / 2), 
                                 self._change_lightness(self.color, -_OUTER_COLOR_LUMINOSITY_VARIATION / 2), 
                                 self.text_height)
        draw_inner = ImageDraw.Draw(self.inner_grad) 
        draw_outer = ImageDraw.Draw(self.outer_grad) 

        for i in range(res[1]):
            c_idx = 0
            if i > int(res[1] / 2 - self.text_height / 2):
                c_idx = i - int(res[1] / 2 - self.text_height / 2)
            if c_idx > self.text_height - 1:
                c_idx = self.text_height - 1
            white_color = white_grad[c_idx]
            user_color = color_grad[c_idx]
            line_xy = [(0, i), (res[0], i)]
            draw_inner.line(line_xy, tuple(white_color), width=1)
            draw_outer.line(line_xy, tuple(user_color), width=1)


    def _debug_bounding_box(self, img):
        res = self.resolution_original
        tbx = self.text_bbox_original
        background = Image.new("RGBA", res, _DEBUG_IMAGE_BG_COLOR)
        img = Image.alpha_composite(background, img)
        draw = ImageDraw.Draw(img) 
        draw_box = [(int(res[0] / 2 - tbx[0] / 2), int(res[1] / 2 - tbx[1] / 2)),
                    (int(res[0] / 2 + tbx[0] / 2), int(res[1] / 2 + tbx[1] / 2)),]
        draw.rectangle(draw_box, outline ="red")
        return img
    
    @staticmethod
    def _change_lightness(rgb, added_lightness):
        c_h, c_l, c_s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        n_l = c_l + added_lightness
        n_l = max(0, min(1, n_l))
        c_r, c_g, c_b = colorsys.hls_to_rgb(c_h, n_l, c_s)
        return int(round(255 * c_r)), int(round(255 * c_g)), int(round(255 * c_b))


#PerlinNoise by alexandr-gnrk
class Interpolation(Enum):
    """Interpolation enumeration used by Perlin noise"""
    LINEAR = 1
    COSINE = 2
    CUBIC = 3


class PerlinNoise():
    """Perlin noise is a type of gradient noise, used to apply pseudo-random changes to a variable"""
    def __init__(self, seed, amplitude=1, frequency=1, octaves=1, interpolation=Interpolation.COSINE, use_fade=False):
        self.seed = random.Random(seed).random()
        self.amplitude = amplitude
        self.frequency = frequency
        self.octaves = octaves
        self.interpolation = interpolation
        self.use_fade = use_fade

        self.mem_x = dict()


    def __noise(self, x):
        # made for improve performance
        if x not in self.mem_x:
            self.mem_x[x] = random.Random(self.seed + x).uniform(-1, 1)
        return self.mem_x[x]


    def __interpolated_noise(self, x):
        prev_x = int(x) # previous integer
        next_x = prev_x + 1 # next integer
        frac_x = x - prev_x # fractional of x

        if self.use_fade:
            frac_x = self.__fade(frac_x)

        # intepolate x
        if self.interpolation is Interpolation.LINEAR:
            res = self.__linear_interp(
                self.__noise(prev_x), 
                self.__noise(next_x),
                frac_x)
        elif self.interpolation is Interpolation.COSINE:
            res = self.__cosine_interp(
                self.__noise(prev_x), 
                self.__noise(next_x),
                frac_x)
        else:
            res = self.__cubic_interp(
                self.__noise(prev_x - 1), 
                self.__noise(prev_x), 
                self.__noise(next_x),
                self.__noise(next_x + 1),
                frac_x)

        return res


    def get(self, x):
        frequency = self.frequency
        amplitude = self.amplitude
        result = 0
        for _ in range(self.octaves):
            result += self.__interpolated_noise(x * frequency) * amplitude
            frequency *= 2
            amplitude /= 2

        return result


    def __linear_interp(self, a, b, x):
        return a + x * (b - a)


    def __cosine_interp(self, a, b, x):
        x2 = (1 - math.cos(x * math.pi)) / 2
        return a * (1 - x2) + b * x2


    def __cubic_interp(self, v0, v1, v2, v3, x):
        p = (v3 - v2) - (v0 - v1)
        q = (v0 - v1) - p
        r = v2 - v0
        s = v1
        return p * x**3 + q * x**2 + r * x + s


    def __fade(self, x):
        # useful only for linear interpolation
        return (6 * x**5) - (15 * x**4) + (10 * x**3)


class ImageAnimation():
    """uses TextPainter to generate images and then it uses ffmpeg to animate the images"""
    def __init__(self, text_painter, animation_type, output_name, tmp_folder, fps, vid_length, 
                 ffmpeg_verbose, text, frequency, amplitude):
        self.text_painter = text_painter
        self.animation_type = animation_type
        self.output_name = output_name
        self.tmp_folder = tmp_folder
        self.fps = fps
        self.vid_length = vid_length
        self.ffmpeg_verbose = ffmpeg_verbose
        self.text = text
        self.frequency = frequency
        self.amplitude = amplitude
        self.output_image = self.output_name + ".png"
        self.output_video = self.output_name + ".mov"
        if _USE_FIXED_SEED:
            self.seed_x = _FIXED_SEEDS[0]
            self.seed_y = _FIXED_SEEDS[1]
        else:
            self.seed_x = _RANDOM_SEEDS[0]
            self.seed_y = _RANDOM_SEEDS[1]


    def create_animation(self):
        self._print_animation_info()

        if self.animation_type == Animation.TYPING:
            for i in range(len(self.text)):
                progress(i, len(self.text), "generating images")
                img = self.text_painter.get_image(num_letter_to_draw=i + 1)
                img.save(str(self.tmp_folder / f"{i:03d}.png"))

        elif self.animation_type == Animation.VIBRATION:
            num_images = int(self.vid_length * self.fps)
            img = self.text_painter.get_image()
            gen_x , gen_y = self._vibration_animation_generators(img.size)
            for i in range(num_images):
                progress(i, num_images, "generating images")
                cur_img = copy.deepcopy(img)
                img_x, img_y = gen_x.get(i), gen_y.get(i)
                # print(f"idx:{i} => (x:{img_x:g}, y:{img_y:g})")
                cur_img = cur_img.transform(cur_img.size, Image.AFFINE, (1, 0, img_x, 0, 1, img_y))
                cur_img.save(str(self.tmp_folder / f"{i:03d}.png"))

        elif self.animation_type == Animation.WIGGLE:
            num_images = int(self.vid_length * self.fps)
            img = self.text_painter.get_image()
            for i in range(num_images):
                progress(i, num_images, "generating images")
                cur_img = copy.deepcopy(img)
                img_x, img_y = self._wiggle_animation(i, cur_img.size)
                # print(f"idx:{i} => (x:{img_x:g}, y:{img_y:g})")
                cur_img = cur_img.transform(cur_img.size, Image.AFFINE, (1, 0, img_x, 0, 1, img_y))
                cur_img.save(str(self.tmp_folder / f"{i:03d}.png"))

        img = self.text_painter.get_image()
        print(f"saving output image to: {self.output_image}")
        img.save(self.output_image)
        
        if self.animation_type != Animation.NONE:
            print("merging images into a video ...")
            self._merge_images_into_video()

            vid_path = pathlib.Path(self.output_video)
            if vid_path.is_file():
                print(f"saved video to {str(vid_path)} (size: {self._sizeof_fmt(vid_path.stat().st_size)})")
            else:
                print("ERROR: could not produce video to: " + str(vid_path))

    def _print_animation_info(self):
        print(f"video length: {self.vid_length} s | video FPS: {self.fps}")
        if self.animation_type == Animation.NONE or self.animation_type == Animation.TYPING:
            print(f"animation type: {self.animation_type.name}")
        else:
            print(f"animation type: {self.animation_type.name} | animation amplitude: {self.amplitude}")
            print(f"frequency: {self.frequency} | animation randomness seeds: ({self.seed_x}, {self.seed_y})")

    def _merge_images_into_video(self):
        cmd = f'ffmpeg -y -framerate {self.fps} -i { self.tmp_folder / "%03d.png"} '
        if self.animation_type == Animation.TYPING:
            letters_speed = float(len(self.text)) / self.vid_length
            cmd = f'ffmpeg -y -framerate {letters_speed} -i { self.tmp_folder / "%03d.png"} '

        cmd += f'-hide_banner -loglevel {self.ffmpeg_verbose} -vcodec png -crf 25 -r {self.fps} {self.output_video}'
        # print(cmd)
        os.system(cmd)
        

    def _vibration_animation_generators(self, img_size):       
        interpolation = Interpolation.LINEAR
        if _VIBRATION_INTERPOLATION.lower().strip() == "cosine":
            interpolation = Interpolation.COSINE
        elif _VIBRATION_INTERPOLATION.lower().strip() == "cubic":
            interpolation = Interpolation.CUBIC
        
        gen_x = PerlinNoise(seed=self.seed_x, amplitude=img_size[0] * self.amplitude, frequency=self.frequency,
                            octaves=_VIBRATION_OCTAVES,  interpolation=interpolation, use_fade=True)
        gen_y = PerlinNoise(seed=self.seed_y, amplitude=img_size[1] * self.amplitude, frequency=self.frequency, 
                            octaves=_VIBRATION_OCTAVES,  interpolation=interpolation, use_fade=True)
        return gen_x, gen_y


    def _wiggle_animation(self, img_idx, img_size, complexity=10):
        wiggle_amplitude = self.amplitude * min(img_size) * 1.5
        translation = [0, 0]
        seeds = [self.seed_x, self.seed_y]
        for i in range(2):
            seed = seeds[i]
            value = 0
            for var_x in range (2, complexity):
                random.seed(seed)
                factor = random.randint(1,1000)
                time = float(img_idx)
                value += math.sin((time / self.fps + factor) * (self.frequency * 40 / var_x) ) * wiggle_amplitude
            translation[i] = value
        return translation[0], translation[1]

    @staticmethod
    def _sizeof_fmt(num, suffix="B"):
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f} Yi{suffix}"


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


def str2bool(var):
    if isinstance(var, bool):
        return var
    if var.lower() in ('yes', 'true', 't', 'y', 'on', '1'):
        return True
    elif var.lower() in ('no', 'false', 'f', 'n', 'off', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected, possible values: yes, y, true, 1, no, n, false, 0.')


def main():
    animations = Animation.get_animations_listing()
    justify_options = ["left", "right", "center"]
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Create a text animation video with a transparent background.'
                                                 'The font size is calculated automatically from the '
                                                 f'text_bbox variable. all occurrences of "{_NEW_LINE_CHARACTER}" will '
                                                 'be replaced by new lines')
    parser.add_argument('-i', '--input', help='the input text (to be animated)',
                        type=str, default=INPUT_TEXT, metavar='\b')
    parser.add_argument('-r', '--resolution', help='output video resolution',
                        nargs=2, type=int, default=RESOLUTION, metavar='\b')
    parser.add_argument('-t', '--text_bbox', help='text bounding box size (width and height), text will be fit to '
                                                  'this box, the box is placed in the center of the image',
                        nargs=2, type=int, default=TEXT_BBOX, metavar='\b')
    parser.add_argument('-s', '--styled_text', help='if set to "True", then generate a styled'
                                                    ' text instead of using plain color',
                        type=str2bool, default=STYLED_TEXT, metavar='\b')                    
    parser.add_argument('-f', '--font', help='font name (will search in system using "fc-list" command), or font path',
                        type=str, default=FONT, metavar='\b')
    parser.add_argument('-p', '--fps', help='frame per second of the output video', type=int, default=FPS, metavar='\b')
    parser.add_argument('-l', '--length', help='length of video in seconds',
                        type=float, default=VIDEO_LENGTH, metavar='\b')
    parser.add_argument('-a', '--animation_type', help='animation type to use, possible values: ' +str(animations),
                        type=str, default=ANIMATION_TYPE, metavar='\b', choices=animations)
    parser.add_argument('-F', '--animation_frequency', help='animation frequency for WIGGLE and VIBRATION animation ',
                        type=float, default=ANIMATION_FREQUENCY, metavar='\b')
    parser.add_argument('-x', '--animation_amplitude', help='animation amplitude for WIGGLE and VIBRATION animation ',
                        type=float, default=ANIMATION_AMPLITUDE, metavar='\b')
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: "error", "warning" or "info"', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-n', '--antialiasing', help='activate anti aliasing but with longer processing time',
                        type=str2bool, default=ANTIALIASING, metavar='\b')
    parser.add_argument('-c', '--color', help='text font color (HEX and RGB are accepted)', type=str,  
                        default=TEXT_COLOR, metavar='\b')
    parser.add_argument('-j', '--justify', help='text alignment options: ' + str(justify_options), type=str, 
                        metavar='\b', default=JUSTIFY, choices=justify_options)
    parser.add_argument('-o', '--output', help='output video path. (without extension)', type=str, metavar='\b',
                        default="text_animation")
    parser.add_argument('-A', '--art', help='Display ASCII art', type=str2bool, default=ART, metavar='\b')
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    font_path = get_font_path(args.font)
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

    painter = TextPainter(input_text, args.text_bbox, color, args.styled_text, font_path, 
                          args.justify, args.resolution, args.antialiasing)

    print("")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        animation_type = Animation.TYPING
        for ani in Animation:
            if ani.name.lower() == args.animation_type.lower():
                animation_type = ani
        animator = ImageAnimation(painter, animation_type, args.output, tmp_path, args.fps, args.length,
                                  args.verbose, painter.text, args.animation_frequency, args.animation_amplitude)
        animator.create_animation()

    print("")
    end_print(args.art)

if __name__ == "__main__":
    main()
