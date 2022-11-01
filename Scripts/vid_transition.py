#!/usr/bin/python3
__package__ = "vid_transition"
import math
import pathlib
import enum
import logging
import datetime
import shutil
import subprocess
import argparse
import tempfile
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

# default variables used in arg-parser
INPUT_VIDEOS = []
OUTPUT = ""
NUM_FRAMES = 10
ANIMATION = "rotation"
MAX_ROTATION = 45
MAX_DISTORTION = 0.7
MAX_BLUR = 0.2
MAX_BRIGHTNESS = 1.0
MAX_ZOOM = 2.0
DEBUG = False
ART = True
REMOVE_ORIGINAL = False


# variable that cannot be changed by arg-parser
_OUTPUT_VIDEO_TYPE = ".mp4"
_OUTPUT_VIDEO_CODEC = "h264"
_LIMITS = {"rotation": (5, 90), "brightness": (0.0, 2.0), "blur": (0.005, 1.0),
           "distortion": (0.3, 1.0), "zoom": (0.5, 2.0)}


def log_debug(msg):
    logging.getLogger(__package__).debug(msg)


def log_info(msg):
    logging.getLogger(__package__).info(msg)


def log_warning(msg):
    logging.getLogger(__package__).info("WARNING: " + msg)


def log_error(msg):
    logging.getLogger(__package__).error("ERROR: " + msg + " (use --debug from more info)")


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = """
    Yb    dP          dP""b8  dP"Yb  8b    d8 88""Yb 88""Yb 888888 .dP"Y8 .dP"Y8 
     Yb  dP          dP   `" dP   Yb 88b  d88 88__dP 88__dP 88__   `Ybo." `Ybo." 
      YbdP   .o.     Yb      Yb   dP 88YbdP88 88\"""  88"Yb  88""   o.`Y8b o.`Y8b 
       YP    `"'      YboodP  YbodP  88 YY 88 88     88  Yb 888888 8bodP' 8bodP' 
    """
    if in_art:
        log_info(intro)
    log_debug("=" * 80)
    log_info((" starting video transition creation ".center(80, "=")))
    log_debug("=" * 80)
    log_info("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.            
    ______     d88ooo  888_dPY8   88   8     ______ 
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX 
             88bdPPP   Y8P   Y8   88oop'               
    """
    log_info((" video transition finished ".center(80, "=")))
    if in_art:
        log_info(end)


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


def format_list(in_list, format_str=""):
    format_str = "{:" + format_str + "}"
    return "[" + (", ".join([format_str.format(ii) for ii in in_list])) + "]"


class Animations(enum.IntEnum):
    rotation = 0
    rotation_inv = 1
    zoom_in = 2
    zoom_out = 3
    translation = 4
    translation_inv = 5
    long_translation = 6
    long_translation_inv = 7


class FramesActions:
    class Type(enum.IntEnum):
        mirror = 0
        zoom = 1
        crop = 2
        rotation = 3
        blur = 4
        distortion = 5
        brightness = 6

    class Function(enum.IntEnum):
        linear = 0
        polynomial = 1
        polynomial_inv = 2

    class MirrorDirection(enum.IntEnum):
        all_directions_1 = 0
        left_1 = 1
        right_1 = 2
        left_3 = 3
        right_3 = 4

    def __init__(self, action_type=Type.mirror):
        self.action_type = action_type
        self.values = []
        self.function = FramesActions.Function.linear


class AnimationActions:
    def __init__(self, max_zoom, max_brightness, max_rotation, max_blur, max_distortion, half_animation_num_frames):
        self.phase1_actions = []
        self.phase2_actions = []
        self.max_zoom = max_zoom
        self.max_brightness = max_brightness
        self.max_rotation = max_rotation
        self.max_blur = max_blur
        self.max_distortion = max_distortion
        self.half_animation_num_frames = half_animation_num_frames

    def get_actions_values(self, animation_type):
        if animation_type == Animations.rotation:
            self._get_rotation_phase1_actions(clockwise=True)
            self._get_rotation_phase2_actions(clockwise=True)

        self._print_info(animation_type)
        return self.phase1_actions, self.phase2_actions

    def _get_rotation_phase1_actions(self, clockwise=True):
        num_frames = self.half_animation_num_frames
        num_frames_30p = int(round(num_frames * 0.3, 0))
        num_frames_70p = num_frames - num_frames_30p
        # --- mirror frames ---
        fa_mirror = FramesActions(FramesActions.Type.mirror)
        for _ in range(num_frames):
            fa_mirror.values.append(FramesActions.MirrorDirection.all_directions_1)
        self.phase1_actions.append(fa_mirror)
        # --- rotation ---
        if _LIMITS["rotation"][0] < self.max_rotation <= _LIMITS["rotation"][1]:
            fa_rot = FramesActions(FramesActions.Type.rotation)
            mul = 1
            if not clockwise:
                mul = -1
            # [fa_rot.values.append(0) for _ in range(num_frames_30p)]
            self._polynomial(fa_rot, 0, mul * self.max_rotation, num_frames)
            self.phase1_actions.append(fa_rot)
        # --- crop ---
        fa_crop = FramesActions(FramesActions.Type.crop)
        for _ in range(num_frames):
            fa_crop.values.append((1, 1, 2, 2))
        self.phase1_actions.append(fa_crop)
        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            fa_brightness = FramesActions(FramesActions.Type.brightness)
            self._linear(fa_brightness, 0, self.max_blur, num_frames)
            self.phase1_actions.append(fa_brightness)
        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            fa_blur = FramesActions(FramesActions.Type.blur)
            [fa_blur.values.append(0) for _ in range(num_frames_30p)]
            self._polynomial(fa_blur, 0, self.max_blur, num_frames_70p)
            self.phase1_actions.append(fa_blur)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            fa_distortion = FramesActions(FramesActions.Type.distortion)
            self._linear(fa_distortion, 0, self.max_distortion, num_frames_70p)
            [fa_distortion.values.append(self.max_distortion) for _ in range(num_frames_30p)]
            self.phase1_actions.append(fa_distortion)

    def _get_rotation_phase2_actions(self, clockwise=True):
        num_frames = self.half_animation_num_frames
        num_frames_30p = int(round(num_frames * 0.3, 0))
        num_frames_70p = num_frames - num_frames_30p
        # --- mirror frames ---
        fa_mirror = FramesActions(FramesActions.Type.mirror)
        for _ in range(num_frames):
            fa_mirror.values.append(FramesActions.MirrorDirection.all_directions_1)
        self.phase2_actions.append(fa_mirror)
        # --- rotation ---
        if _LIMITS["rotation"][0] < self.max_rotation <= _LIMITS["rotation"][1]:
            fa_rot = FramesActions(FramesActions.Type.rotation)
            mul = 1
            if not clockwise:
                mul = -1
            self._polynomial_inv(fa_rot, - mul * self.max_rotation, 0, num_frames)
            # [fa_rot.values.append(0) for _ in range(num_frames_30p)]
            self.phase2_actions.append(fa_rot)
        # --- crop ---
        fa_crop = FramesActions(FramesActions.Type.crop)
        for _ in range(num_frames):
            fa_crop.values.append((1, 1))
        self.phase2_actions.append(fa_crop)
        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            fa_brightness = FramesActions(FramesActions.Type.brightness)
            self._linear(fa_brightness, self.max_blur, 0, num_frames)
            self.phase1_actions.append(fa_brightness)
        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            fa_blur = FramesActions(FramesActions.Type.blur)
            self._polynomial(fa_blur, self.max_blur, 0, num_frames_70p)
            [fa_blur.values.append(0) for _ in range(num_frames_30p)]
            self.phase2_actions.append(fa_blur)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            fa_distortion = FramesActions(FramesActions.Type.distortion)
            [fa_distortion.values.append(self.max_distortion) for _ in range(num_frames_30p)]
            self._linear(fa_distortion, self.max_distortion, 0, num_frames_70p)
            self.phase2_actions.append(fa_distortion)

    def _print_info(self, animation_type):
        log_info("")
        log_debug("".center(80, "="))
        log_info(" Transition animation info ".center(80, "="))
        log_debug("".center(80, "="))
        animation_types = {0: "clockwise rotation", 1: "anticlockwise rotation", 2: "zoom in", 3: "zoom out",
                           4: "translation (left to right)", 5: "translation (right to left)",
                           6: "long translation (left to right)", 7: "inverse long translation(right to left)"}
        log_info(f"transition animation type: [{animation_types[animation_type]}]")
        log_info(f"transition activated effects (in order):")

        phase1_activated = [action.action_type.name for action in self.phase1_actions]
        phase2_activated = [action.action_type.name for action in self.phase2_actions]
        log_info(f"* phase 1 activated effects: [{', '.join(phase1_activated)}]")
        log_info(f"* phase 2 activated effects: [{', '.join(phase2_activated)}]")
        log_debug("")

        for phase_idx, actions in enumerate([self.phase1_actions, self.phase2_actions]):
            log_debug(f" transition phase_{phase_idx + 1} ".center(80, "-"))
            for action in actions:
                if action.action_type == FramesActions.Type.mirror:
                    log_debug(f"mirroring frames, type: [{action.action_type.name}], "
                              f"function: [{action.function.name}]")
                    log_debug(f"* values: [{action.values[0].name}] - num frames: [{len(action.values)}]")
                elif action.action_type == FramesActions.Type.zoom:
                    log_debug(f"zoom effect, max value: [{self.max_zoom:.1%}], function: [{action.function.name}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.crop:
                    log_debug(f"crop effect")
                    cropped = [f"({v[0]:g}, {v[1]:g})" for v in action.values]
                    log_debug(f"* values: {format_list(cropped, 's')}, function: [{action.function.name}]")
                elif action.action_type == FramesActions.Type.rotation:
                    log_debug(f"rotation effect, max value (in degrees): [{self.max_rotation:.1f}], "
                              f"function: [{action.function.name}]")
                    log_debug(f"* values (degree): {format_list(action.values, '.1f')}")
                elif action.action_type == FramesActions.Type.blur:
                    log_debug(f"blur effect, max value: [{self.max_blur:.1%}], function: [{action.function.name}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.distortion:
                    log_debug(f"len pincushion distortion effect, max value: [{self.max_distortion:.1%}], "
                              f"function: [{action.function.name}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.brightness:
                    log_debug(f"brightness effect, max value: [{self.max_brightness:.1%}], "
                              f"function: [{action.function.name}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
            log_debug("")
        log_debug("")

    @staticmethod
    def _linear(frame_action, f_a, f_b, length):
        xa, xb = 0, length - 1
        c1 = (f_b - f_a) / (xb - xa)
        c2 = f_a - c1 * xa
        for xi in range(length):
            frame_action.values.append(c1 * xi + c2)
        frame_action.function = FramesActions.Function.linear

    @staticmethod
    def _polynomial(frame_action, f_a, f_b, length, strength=2.0):
        xa, xb = 0, length - 1
        c1 = (f_b - f_a) / ((xb - xa) ** strength)
        c2 = f_a
        for xi in range(length):
            frame_action.values.append(c1 * ((xi - xa) ** strength) + c2)
        frame_action.function = FramesActions.Function.polynomial

    @staticmethod
    def _polynomial_inv(frame_action, f_a, f_b, length, strength=2.0):
        AnimationActions._polynomial(frame_action, f_a, f_b, length, 1 / strength)
        frame_action.function = FramesActions.Function.polynomial_inv


class AnimationImages:
    class PincushionDeformation:
        def __init__(self, strength=0.2, zoom=1.2, auto_zoom=False):
            self.correction_radius = None
            self.zoom = zoom
            self.strength = strength
            if strength <= 0:
                self.strength = 0.00001
            self.auto_zoom = auto_zoom
            self.half_height = None
            self.half_width = None

        def transform(self, x, y):
            new_x = x - self.half_width
            new_y = y - self.half_height
            distance = math.sqrt(new_x ** 2 + new_y ** 2)
            r = distance / self.correction_radius
            if r == 0:
                theta = 1
            else:
                theta = math.atan(r) / r
            source_x = self.half_width + theta * new_x * self.zoom
            source_y = self.half_height + theta * new_y * self.zoom
            return source_x, source_y

        def transform_rectangle(self, x0, y0, x1, y1):
            return (*self.transform(x0, y0),
                    *self.transform(x0, y1),
                    *self.transform(x1, y1),
                    *self.transform(x1, y0))

        def determine_parameters(self, img):
            width, height = img.size
            self.half_width = width / 2
            self.half_height = height / 2
            self.correction_radius = (min(self.half_width, self.half_height) * 10) * (1 - self.strength) ** 2 + 1
            # print(f"correction radius => {self.correction_radius}")
            if self.auto_zoom:
                r = math.sqrt(min(self.half_height, self.half_width) ** 2) / self.correction_radius
                self.zoom = r / math.atan(r)

        # TODO use log instead of print
        def get_debug_info(self, img):
            self.determine_parameters(img)
            w, h = img.size
            msg = [" lens distortion debug info ".center(80, '=')]
            msg += [f"input image size: [w:{w}, h:{h}]"]
            if not self.auto_zoom:
                msg += [f"strength: [{self.strength:.0%}] , automatic zoom: [Off] , provided zoom: [{self.zoom:.0%}]"]
            else:
                msg += [f"strength: [{self.strength:.0%}] , automatic zoom: [On] , calculated zoom: [{self.zoom:.0%}]"]
            msg += ["corner points displacement:"]
            points = {"top-left": (0, 0), "top-center": (self.half_width, 0), "top-right": (w, 0),
                      "left": (0, self.half_height), "right": (w, self.half_height),
                      "bottom-left": (0, h), "bottom-center": (self.half_width, h), "bottom-right": (w, h)}
            for key, value in points.items():
                res = self.transform(value[0], value[1])
                msg += [f"* {key:<13s} [x:{res[0]:<6.1f}, y:{res[1]:<6.1f}] => [{value[0]:<4.0f}, {value[1]:<4.0f}]"]
            msg += [""]
            return msg

        def getmesh(self, img):
            self.determine_parameters(img)
            width, height = img.size

            grid_space = 20
            target_grid = []
            for x in range(0, width, grid_space):
                for y in range(0, height, grid_space):
                    target_grid.append((x, y, x + grid_space, y + grid_space))

            source_grid = [self.transform_rectangle(*rect) for rect in target_grid]
            return [t for t in zip(target_grid, source_grid)]

    @staticmethod
    def make_transition(working_dir, in_images1, in_images2, in_actions1, in_actions2, debug=False):
        log_info("")
        log_debug("".center(80, "="))
        log_info(" Transition image processing ".center(80, "="))
        log_debug("".center(80, "="))
        images_path = [in_images1, in_images2]
        res_folder = [None, None]

        for phase_idx, actions in enumerate([in_actions1, in_actions2]):
            log_debug("=" * 80)
            log_info(f"processing transition phase_{phase_idx+1} images")

            for img_idx, img_path in enumerate(images_path[phase_idx]):
                if not debug:
                    progress(img_idx, len(images_path[phase_idx]), f"phase_{phase_idx+1} images")
                img = Image.open(str(img_path))
                original_size = img.size
                log_debug(f" image [{img_idx+1}/{len(images_path[phase_idx])}] processing ".center(80, "-"))
                log_debug(f"image path {img_path}")
                for action_idx, action in enumerate(actions):

                    suffix = action.action_type.name
                    if action_idx == len(actions) - 1:
                        suffix += "_final"
                    img_save_folder = working_dir / f"{action_idx+2}_phase{phase_idx+1}_{suffix}"
                    img_save_folder.mkdir(exist_ok=True)
                    if action_idx == len(actions) - 1:
                        res_folder[phase_idx] = img_save_folder
                    value = action.values[img_idx]
                    msg = f"phase_{phase_idx+1} - img [{img_idx+1}/{len(images_path[phase_idx])}]"
                    if isinstance(value, tuple):
                        msg += f" - action [{action.action_type.name} => ({value[0]:.1%}, {value[1]:.1%})]"
                    else:
                        msg += f" - action [{action.action_type.name} => {value:g}]"
                    msg += f" - folder [{img_save_folder.name}]"
                    log_debug(msg)
                    if action.action_type == FramesActions.Type.mirror:
                        img = AnimationImages.mirror_image_effect(img, value)
                    elif action.action_type == FramesActions.Type.zoom:
                        img = AnimationImages.zoom_effect(img, value)
                    elif action.action_type == FramesActions.Type.crop:
                        img = AnimationImages.crop_effect(img, value, original_size)
                    elif action.action_type == FramesActions.Type.rotation:
                        img = AnimationImages.rotation_effect(img, value)
                    elif action.action_type == FramesActions.Type.blur:
                        img = AnimationImages.blur_effect(img, value)
                    elif action.action_type == FramesActions.Type.distortion:
                        img = AnimationImages.distortion_effect(img, value)
                    elif action.action_type == FramesActions.Type.brightness:
                        img = AnimationImages.brightness_effect(img, value)
                    if debug or action_idx == len(actions) - 1:
                        img.save(str(img_save_folder / img_path.name))

                log_debug("")
        return res_folder

    @staticmethod
    def mirror_image_effect(in_img, mirror_direction):
        images = [in_img, in_img.transpose(0), in_img.transpose(1),
                  in_img.transpose(0).transpose(1)]
        w, h = in_img.width, in_img.height
        if mirror_direction == FramesActions.MirrorDirection.all_directions_1:
            new_size = (3 * w, 3 * h)
            pos_dict = {(0, 0): 3, (1, 0): 2, (2, 0): 3,
                        (0, 1): 1, (1, 1): 0, (2, 1): 1,
                        (0, 2): 3, (1, 2): 2, (2, 2): 3}
        elif mirror_direction == FramesActions.MirrorDirection.left_1:
            new_size = (2 * w, 1 * h)
            pos_dict = {(0, 0): 1, (1, 0): 0}
        elif mirror_direction == FramesActions.MirrorDirection.right_1:
            new_size = (2 * w, 1 * h)
            pos_dict = {(0, 0): 0, (1, 0): 1}
        elif mirror_direction == FramesActions.MirrorDirection.left_3:
            new_size = (4 * w, 1 * h)
            pos_dict = {(0, 0): 1, (1, 0): 0, (2, 0): 1, (3, 0): 0}
        elif mirror_direction == FramesActions.MirrorDirection.right_3:
            new_size = (4 * w, 1 * h)
            pos_dict = {(0, 0): 0, (1, 0): 1, (2, 0): 0, (3, 0): 1}
        else:
            return in_img
        res = Image.new('RGB', new_size)
        [res.paste(images[idx], (w * xy[0], h * xy[1])) for xy, idx in pos_dict.items()]
        return res

    @staticmethod
    def zoom_effect(in_img, zoom_value):
        w, h = in_img.size
        zoom2 = zoom_value * 2
        new_img = in_img.crop((w/2 - w / zoom2, h/2 - h / zoom2, w/2 + w / zoom2, h/2 + h / zoom2))
        return new_img.resize((w, h), Image.Resampling.BICUBIC)

    @staticmethod
    def crop_effect(in_img, top_left_corner, original_img_size):
        h, w = original_img_size[0], original_img_size[1]
        tfc_x, tfc_y = int(round(top_left_corner[0] * h, 0)), int(round(top_left_corner[1] * w, 0))
        return in_img.crop((tfc_x, tfc_y, tfc_x + h, tfc_y + w))

    @staticmethod
    def rotation_effect(in_img, rot_angle):
        return in_img.rotate(rot_angle)

    @staticmethod
    def blur_effect(in_img, blur_value):
        blue_strength = min(in_img.size[0], in_img.size[1]) * blur_value * 0.1
        # print(blue_strength)
        return in_img.filter(ImageFilter.GaussianBlur(blue_strength))

    @staticmethod
    def distortion_effect(in_img, distortion_strength):
        return ImageOps.deform(in_img, AnimationImages.PincushionDeformation(distortion_strength, 1.0))

    @staticmethod
    def brightness_effect(in_img, brightness_value):
        enhancer = ImageEnhance.Brightness(in_img)
        return enhancer.enhance(brightness_value)


class DataHandler:
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.tmp_path = None
        self.output = None
        self.phase1_vid = None
        self.phase2_vid = None
        self.fps = 30
        self.vid1_raw_images_folder = None
        self.vid2_raw_images_folder = None
        self.phase1_images = []
        self.phase2_images = []
        self.animation = None

    def verify_arguments(self, in_args, in_tmp_path):
        self.tmp_path = in_tmp_path
        self.output = pathlib.Path(in_args.output)
        if in_args.output == "":
            self._suggest_output()
        if in_args.debug:
            self.tmp_path = self.output.parent / (self.output.stem + "_debug")
            if self.tmp_path.is_dir():
                shutil.rmtree(str(self.tmp_path))
            self.tmp_path.mkdir()

        self._setup_logging(in_args.debug, self.tmp_path / f"{__package__}.log")
        intro_print(in_args.art)
        if not self._verify_critical_info(in_args):
            return False
        in_vid1 = pathlib.Path(in_args.input[0])
        in_vid2 = pathlib.Path(in_args.input[1])
        self.phase1_vid = self.output.parent / (self.output.stem + "_phase1" + _OUTPUT_VIDEO_TYPE)
        self.phase2_vid = self.output.parent / (self.output.stem + "_phase2" + _OUTPUT_VIDEO_TYPE)
        log_info(f"first input video: {in_vid1}")
        log_info(f"second input video: {in_vid2}")
        log_info(f"output animation phase1 video: {self.phase1_vid}")
        log_info(f"output animation phase2 video: {self.phase2_vid}")
        self._get_fps_from_video()
        log_info(f"frames per second (FPS): {self.fps}")

        self.vid1_raw_images_folder = self.tmp_path / "1_phase1_raw"
        self.vid2_raw_images_folder = self.tmp_path / "1_phase2_raw"
        self.vid1_raw_images_folder.mkdir()
        log_debug(f"created vid1_raw_images_folder: {self.vid1_raw_images_folder}")
        self.vid2_raw_images_folder.mkdir()
        log_debug(f"created vid2_raw_images_folder: {self.vid2_raw_images_folder}")
        if not self._extract_phase1_images(in_args.num_frames, in_vid1):
            return False
        num_frames_for_vid2 = in_args.num_frames
        if self.animation == Animations.long_translation or self.animation == Animations.long_translation_inv:
            num_frames_for_vid2 = 2 * in_args.num_frames
        if not self._extract_phase2_images(num_frames_for_vid2, in_vid2):
            return False
        log_info(f"number of frames for phase1: [{len(self.phase1_images)}], for phase2: [{len(self.phase2_images)}]")
        return True

    def final_images_to_video(self, res_folders):
        # images_speeds = [(float(len(self.phase1_images)) / (int_duration))]
        output_videos = [self.phase1_vid, self.phase2_vid]
        for idx in range(2):
            log_info(f"merging phase_{idx} images into a video ...")
            cmd = ["ffmpeg", "-hide_banner", "-framerate", str(self.fps), "-y", "-r", f"{self.fps}",  "-i",
                   str(res_folders[idx] / "%04d.png"), "-r", str(self.fps), "-vcodec", _OUTPUT_VIDEO_CODEC,
                   str(output_videos[idx])]
            self._exec_command(cmd, f"command used for merging phase_{idx} images into a video ...")
            if not output_videos[idx].is_file():
                log_error(f"ffmpeg failed to convert images to: {output_videos[idx]}")
                return False
        log_info(f"output animation phase1 video: {self.phase1_vid}")
        log_info(f"output animation phase2 video: {self.phase2_vid}")
        return True

    @staticmethod
    def get_animation_help():  # TODO complete me
        msg = """
        TODO later
        """
        return msg

    def _verify_critical_info(self, in_args):
        if shutil.which("ffmpeg") is None:
            log_error("'ffmpeg' is not installed, please install it before use")
            return False
        if len(in_args.input) < 2 or len(in_args.input) > 2:
            log_error(f"2 input videos needed, [{len(in_args.input)}] provided")
            return False
        in_vid1 = pathlib.Path(in_args.input[0])
        if not in_vid1.is_file():
            log_error(f"could not find first video under: {in_vid1}")
            return False
        in_vid2 = pathlib.Path(in_args.input[1])
        if not in_vid2.is_file():
            log_error(f"could not find second video under: {in_vid2}")
            return False
        if in_args.num_frames < 2 or in_args.num_frames > 100:
            log_error(f"number of frames per phase should be in the range [2, 100] (provided: [{in_args.num_frames}])")
            return False
        for animation_enum in Animations:
            # print(f"{in_args.animation.lower().strip()} <-> {animation_enum.name}")
            if in_args.animation.lower().strip() == animation_enum.name:
                self.animation = animation_enum
                break
        if self.animation is None:
            log_error(f"animation provided [{in_args.animation}] not recognized, please use one of the "
                      f"following animations:")
            log_info(self.get_animation_help())
            return False
        return True

    def _extract_phase1_images(self, in_num_frames, in_vid_1):
        duration_ms = int(math.ceil(1000 * (in_num_frames + 2) / self.fps))
        cmd = ["ffmpeg", "-hide_banner", "-sseof", f"-{duration_ms}ms", "-i", str(in_vid_1),
               str(self.vid1_raw_images_folder / "%04d.png")]
        self._exec_command(cmd, "command used for extracting images from video num 1:")
        for img_f in self.vid1_raw_images_folder.glob("*.png"):
            self.phase1_images.append(img_f)
        self.phase1_images.sort()
        if len(self.phase1_images) < in_num_frames:
            log_error(f"could not extract [{in_num_frames}] images from the first video "
                      f"({len(self.phase1_images)} extracted)")
            return False
        if len(self.phase1_images) > in_num_frames:
            self.phase1_images = self.phase1_images[-in_num_frames:]
        return True

    def _extract_phase2_images(self, in_num_frames, in_vid_2):
        duration_ms = int(math.ceil(1000 * (in_num_frames + 2) / self.fps))
        cmd = ["ffmpeg", "-hide_banner", "-to", f"{duration_ms}ms", "-i", str(in_vid_2),
               str(self.vid2_raw_images_folder / "%04d.png")]
        self._exec_command(cmd, "command used for extracting images from video num 2:")
        for img_f in self.vid2_raw_images_folder.glob("*.png"):
            self.phase2_images.append(img_f)
        self.phase2_images.sort()
        if len(self.phase2_images) < in_num_frames:
            log_error(f"could not extract [{in_num_frames}] images from the second video "
                      f"({len(self.phase2_images)} extracted)")
            return False
        if len(self.phase2_images) > in_num_frames:
            self.phase2_images = self.phase2_images[:in_num_frames]
        return True

    @staticmethod
    def _exec_command(in_cmd, in_presentation):
        log_debug("")
        log_debug(in_presentation)
        log_debug("")
        log_debug(" ".join(in_cmd))
        res = subprocess.run(in_cmd, capture_output=True, text=True)
        log_debug("")
        log_debug("")
        log_debug("stdout:")
        log_debug("")
        log_debug(res.stdout)
        log_debug("")
        log_debug("stderr:")
        log_debug("")
        log_debug(res.stderr)
        log_debug("")
        log_debug("")

    # TODO: fps extraction
    def _get_fps_from_video(self):
        self.fps = 30

    def get_duration_msg(self):
        end_time = datetime.datetime.now()
        t_delta = end_time - self.start_time
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

    def _suggest_output(self):  # TODO
        self.output = pathlib.Path().cwd() / "vt1"

    @staticmethod
    def _setup_logging(debug, log_file_path):
        init_logger = logging.getLogger(__package__)
        if debug:
            init_logger.setLevel(logging.DEBUG)
        else:
            init_logger.setLevel(logging.INFO)
        i_formatter = logging.Formatter('%(message)s')
        ch = logging.StreamHandler()
        ch.setFormatter(i_formatter)
        init_logger.addHandler(ch)
        if debug:
            handler = logging.FileHandler(str(log_file_path), encoding='utf8')
            n_formatter = logging.Formatter('[%(levelname)s] [%(asctime)s] - %(message)s', "%H:%M:%S")
            handler.setFormatter(n_formatter)
            handler.setLevel(logging.DEBUG)
            init_logger.addHandler(handler)


if __name__ == "__main__":
    all_animation_names = ", ".join([animation_enum.name for animation_enum in Animations])
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='make a transition animation between two videos, using the last part '
                                                 'of the first video, and the first part of the second video')
    parser.add_argument('-i', '--input', help='input videos, must be two', type=str,  nargs='+', metavar='\b',
                        default=INPUT_VIDEOS)
    parser.add_argument('-n', '--num_frames', help='the number of frames used for each animation phase, '
                                                   'most animations consists of two phases',
                        type=int, default=NUM_FRAMES, metavar='\b')
    parser.add_argument('-a', '--animation', help=f'possible animations (use -a help to show more info): '
                                                  f'{all_animation_names} ',
                        type=str, default=ANIMATION, metavar='\b')
    parser.add_argument('-o', '--output', help='the name of the output (determined automatically if left empty), '
                                               'FPS is copied from the first video.',
                        type=str, default=OUTPUT, metavar='\b')
    parser.add_argument('-r', '--max_rotation', help=f'rotation (in degree) value at the midpoint of the animation, '
                                                     f'possible range {list(_LIMITS["rotation"])}',
                        type=int, default=MAX_ROTATION, metavar='\b')
    parser.add_argument('-d', '--max_distortion', help=f'lens distortion value at the midpoint of the animation'
                                                       f'(in percentage), possible range {list(_LIMITS["distortion"])}',
                        type=float, default=MAX_DISTORTION, metavar='\b')
    parser.add_argument('-b', '--max_blur', help=f'gaussian blur value at the midpoint of the animation, '
                                                 f'(in percentage), possible range {list(_LIMITS["blur"])}',
                        type=float, default=MAX_BLUR, metavar='\b')
    parser.add_argument('-s', '--max_brightness', help=f'brightness value at the midpoint of the animation, '
                                                       f'(in percentage), possible range {list(_LIMITS["brightness"])}',
                        type=float, default=MAX_BRIGHTNESS, metavar='\b')
    parser.add_argument('-z', '--max_zoom', help=f'zoom value at the midpoint of the animation, '
                                                 f'(in percentage), possible range {list(_LIMITS["zoom"])}',
                        type=float, default=MAX_ZOOM, metavar='\b')
    parser.add_argument('-g', '--debug', help='this will show more info, will create a logs file, '
                                              'and will create a folder which contains animation images',
                        type=bool, default=DEBUG, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-t', '--art', help='Display ASCII art', type=bool,
                        default=ART, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-m', '--remove', help='delete original videos after a successful animation creation',
                        type=bool, default=REMOVE_ORIGINAL, metavar='\b', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    if args.animation.lower() == "help":
        print(DataHandler.get_animation_help())
        exit(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        dh = DataHandler()
        if not dh.verify_arguments(args, tmp_path):
            exit(1)

        actions_determinator = AnimationActions(args.max_zoom, args.max_brightness, args.max_rotation, args.max_blur,
                                                args.max_distortion, args.num_frames)

        phase1_actions, phase2_actions = actions_determinator.get_actions_values(dh.animation)

        # quit()
        final_phase_folder = AnimationImages.make_transition(dh.tmp_path, dh.phase1_images, dh.phase2_images,
                                                             phase1_actions, phase2_actions, args.debug)

        if not dh.final_images_to_video(final_phase_folder):
            exit(1)
        log_info("")
        log_info((f" Transition finished. Duration = {dh.get_duration_msg()} ".center(80, "=")))
        log_info("")
        end_print(args.art)
    exit(0)

    home = pathlib.Path().home()
    for i in [1, 2, 3, 4]:
        image = Image.open(str(home / f'pic{i}_a.jpg'))
        # result_image = AnimationImages.distortion_effect(image, 0.7)
        result_image = AnimationImages.brightness_effect(image, 1.7)
        # result_image = AnimationImages.blur_effect(image, 0.2)
        # result_image = AnimationImages.rotation_effect(image, 45)
        # result_image = AnimationImages.mirror_image_effect(image, FramesActions.MirrorDirection.right_3)
        # result_image = AnimationImages.zoom_effect(image, 0.7)

        # result_image = AnimationImages.mirror_image_effect(image, FramesActions.MirrorDirection.all_directions_1)
        # result_image = AnimationImages.rotation_effect(result_image, 60)
        # result_image = AnimationImages.crop_effect(result_image, (1, 1), image.size)

        print(f"finished {i}")
        result_image.save(str(home / f'pic{i}_b.jpg'))
