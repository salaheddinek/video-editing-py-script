#!/usr/bin/env python3
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
MERGE_PHASES = False


# variable that cannot be changed by arg-parser
_OUTPUT_VIDEO_TYPE = ".mp4"
_OUTPUT_VIDEO_CODEC = "h264"
_LIMITS = {"rotation": (5, 90), "brightness": (0.0, 2.0), "blur": (0.005, 1.0),
           "distortion": (0.3, 1.0), "zoom": (1.2, 2.0)}
_ANIMATION_HELP = f"""  
This program supports multiple types of animation. The arguments 'max_blur', 'max_distortion' and 'max_brightness' \
affect all these types. Whereas, 'max_rotation' and 'max_zoom' only affect [rotation] and [zoom] animations \
respectively. Here is the list of supported animations and the number of frames needed for each (assuming that the \
argument 'num_frames' is kept at {NUM_FRAMES}):

 * [rotation]: clockwise rotation, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [rotation_inv]: anti-clockwise rotation, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [zoom_in]: zooms inwards, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [zoom_out]: zooms outwards, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [translation]: translation from left to right, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [translation_inv]: translation from right to left, has 2 phases and needs {NUM_FRAMES*2} frames.
 * [long_translation]: translation from left to right, has 3 phases and needs {NUM_FRAMES*3} frames ({NUM_FRAMES} from \
the first video, and {NUM_FRAMES*2} from the second one). 
 * [long_translation_inv]: translation from right to left, has 3 phases and needs {NUM_FRAMES*3} frames.        
"""


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
    intro = '''
    Yb    dP 88 8888b.      888888 88""Yb    db    88b 88 .dP"Y8 88 888888 
     Yb  dP  88  8I  Yb       88   88__dP   dPYb   88Yb88 `Ybo." 88   88   
      YbdP   88  8I  dY       88   88"Yb   dP__Yb  88 Y88 o.`Y8b 88   88   
       YP    88 8888Y"        88   88  Yb dP""""Yb 88  Y8 8bodP' 88   88   
    '''
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
            self._get_rotation_actions(clockwise=True)
        elif animation_type == Animations.rotation_inv:
            self._get_rotation_actions(clockwise=False)
        elif animation_type == Animations.translation:
            self._get_translation_actions(left2right=True)
        elif animation_type == Animations.translation_inv:
            self._get_translation_actions(left2right=False)
        elif animation_type == Animations.zoom_in:
            self._get_zoom_actions(inward_direction=True)
        elif animation_type == Animations.zoom_out:
            self._get_zoom_actions(inward_direction=False)
        elif animation_type == Animations.long_translation:
            self._get_long_translation_actions(left2right=True)
        elif animation_type == Animations.long_translation_inv:
            self._get_long_translation_actions(left2right=False)

        self._print_info(animation_type)
        return self.phase1_actions, self.phase2_actions

    def _get_long_translation_actions(self, left2right=True):
        num_frames1 = self.half_animation_num_frames
        num_frames1_30p = int(round(num_frames1 * 0.3, 0))
        num_frames1_50p = int(round(num_frames1 * 0.5, 0))
        num_frames2 = 2 * self.half_animation_num_frames
        num_frames2_30p = int(round(num_frames2 * 0.3, 0))
        # --- mirror frames ---
        direction1, direction2 = FramesActions.MirrorDirection.right_1, FramesActions.MirrorDirection.left_3
        if not left2right:
            direction1, direction2 = FramesActions.MirrorDirection.left_1, FramesActions.MirrorDirection.right_3
        fa_mirror1 = FramesActions(FramesActions.Type.mirror)
        [fa_mirror1.values.append(direction1) for _ in range(num_frames1)]
        self.phase1_actions.append(fa_mirror1)
        fa_mirror2 = FramesActions(FramesActions.Type.mirror)
        [fa_mirror2.values.append(direction2) for _ in range(num_frames2)]
        self.phase2_actions.append(fa_mirror2)

        # --- crop ---
        crop_1_values, crop_2_values = (0, 1), (0, 2, 3)
        if not left2right:
            crop_1_values, crop_2_values = (1, 0), (3, 2, 0)
        fa_crop1 = FramesActions(FramesActions.Type.crop)
        self._polynomial(fa_crop1, crop_1_values[0], crop_1_values[1], num_frames1)
        fa_crop1.values = [(v, 0) for v in fa_crop1.values]
        self.phase1_actions.append(fa_crop1)

        fa_crop2 = FramesActions(FramesActions.Type.crop)
        # self._linear(fa_crop2, crop_2_values[0], crop_2_values[1], num_frames1)
        self._polynomial_inv(fa_crop2, crop_2_values[0], crop_2_values[2], 2 * num_frames1)
        fa_crop2.values = [(v, 0) for v in fa_crop2.values]
        self.phase2_actions.append(fa_crop2)

        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            fa_br1, fa_br2 = FramesActions(FramesActions.Type.brightness), FramesActions(FramesActions.Type.brightness)
            self._polynomial(fa_br1, 1.0, self.max_brightness, num_frames1)
            fa_br2.values = [self.max_brightness for _ in range(num_frames1)]
            self._polynomial_inv(fa_br2, self.max_brightness, 1.0, num_frames1)
            self.phase1_actions.append(fa_br1)
            self.phase2_actions.append(fa_br2)
        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            fa_bl1, fa_bl2 = FramesActions(FramesActions.Type.blur), FramesActions(FramesActions.Type.blur)
            fa_bl1.values = [0 for _ in range(num_frames1_30p)]
            self._polynomial(fa_bl1, 0.0, self.max_blur, num_frames1 - num_frames1_30p)
            self._polynomial(fa_bl2, self.max_blur, 0.0, num_frames2)
            self.phase1_actions.append(fa_bl1)
            self.phase2_actions.append(fa_bl2)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            fa_ds1, fa_ds2 = FramesActions(FramesActions.Type.distortion), FramesActions(FramesActions.Type.distortion)
            self._polynomial(fa_ds1, 0.0, self.max_distortion, num_frames1 - num_frames1_50p)
            fa_ds1.values += [self.max_distortion for _ in range(num_frames1_50p)]
            fa_ds2.values = [self.max_distortion for _ in range(num_frames1 + num_frames1_50p)]
            self._polynomial(fa_ds2, self.max_distortion, 0.0, num_frames1 - num_frames1_50p)
            self.phase1_actions.append(fa_ds1)
            self.phase2_actions.append(fa_ds2)

    def _get_zoom_actions(self, inward_direction=True):
        num_frames = self.half_animation_num_frames
        num_frames_30p = int(round(num_frames * 0.3, 0))
        num_frames_50p = int(round(num_frames * 0.5, 0))
        # --- mirror frames ---
        for phase_fas in [self.phase1_actions, self.phase2_actions]:
            fa_mirror = FramesActions(FramesActions.Type.mirror)
            for _ in range(num_frames):
                fa_mirror.values.append(FramesActions.MirrorDirection.all_directions_1)
            phase_fas.append(fa_mirror)
        # --- zoom ---
        zoom_1v, zoom_2v = self.max_zoom, 1 / self.max_zoom
        if not inward_direction:
            zoom_1v, zoom_2v = zoom_2v, zoom_1v
        if _LIMITS["zoom"][0] <= self.max_zoom <= _LIMITS["zoom"][1]:
            fa_zoom1, fa_zoom2 = FramesActions(FramesActions.Type.zoom), FramesActions(FramesActions.Type.zoom)
            self._polynomial(fa_zoom1, 1.0, zoom_1v, num_frames)
            self.phase1_actions.append(fa_zoom1)
            self._polynomial_inv(fa_zoom2, zoom_2v, 1.0, num_frames)
            self.phase2_actions.append(fa_zoom2)
        # --- crop ---
        for phase_fas in [self.phase1_actions, self.phase2_actions]:
            fa_crop = FramesActions(FramesActions.Type.crop)
            for _ in range(num_frames):
                fa_crop.values.append((1, 1))
            phase_fas.append(fa_crop)
        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            self._symmetric_action_value(self._linear, FramesActions.Type.brightness, 1,
                                         self.max_brightness, num_frames)

        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            self._symmetric_action_value(self._polynomial, FramesActions.Type.blur, 0,
                                         self.max_blur, num_frames, num_f_a_duplicates=num_frames_30p)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            self._symmetric_action_value(self._polynomial_inv, FramesActions.Type.distortion, 0,
                                         self.max_distortion, num_frames, num_f_b_duplicates=num_frames_50p)

    def _get_translation_actions(self, left2right=True):
        num_frames = self.half_animation_num_frames
        num_frames_30p = int(round(num_frames * 0.3, 0))
        num_frames_50p = int(round(num_frames * 0.5, 0))
        # --- mirror frames ---
        direction1, direction2 = FramesActions.MirrorDirection.right_1, FramesActions.MirrorDirection.left_1
        if not left2right:
            direction1, direction2 = direction2, direction1
        fa_mirror1 = FramesActions(FramesActions.Type.mirror)
        [fa_mirror1.values.append(direction1) for _ in range(num_frames)]
        self.phase1_actions.append(fa_mirror1)
        fa_mirror2 = FramesActions(FramesActions.Type.mirror)
        [fa_mirror2.values.append(direction2) for _ in range(num_frames)]
        self.phase2_actions.append(fa_mirror2)

        # --- crop ---
        crop_f_a, crop_f_b = 0, 1
        if not left2right:
            crop_f_a, crop_f_b = 1, 0
        fa_crop1 = FramesActions(FramesActions.Type.crop)
        self._polynomial(fa_crop1, crop_f_a, crop_f_b, num_frames)
        fa_crop1.values = [(v, 0) for v in fa_crop1.values]
        self.phase1_actions.append(fa_crop1)
        fa_crop2 = FramesActions(FramesActions.Type.crop)
        self._polynomial_inv(fa_crop2, crop_f_a, crop_f_b, num_frames)
        fa_crop2.values = [(v, 0) for v in fa_crop2.values]
        self.phase2_actions.append(fa_crop2)

        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            self._symmetric_action_value(self._linear, FramesActions.Type.brightness, 1,
                                         self.max_brightness, num_frames)
        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            self._symmetric_action_value(self._polynomial, FramesActions.Type.blur, 0,
                                         self.max_blur, num_frames, num_f_a_duplicates=num_frames_30p)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            self._symmetric_action_value(self._polynomial_inv, FramesActions.Type.distortion, 0,
                                         self.max_distortion, num_frames, num_f_b_duplicates=num_frames_50p)

    def _get_rotation_actions(self, clockwise=True):
        num_frames = self.half_animation_num_frames
        num_frames_30p = int(round(num_frames * 0.3, 0))
        num_frames_50p = int(round(num_frames * 0.5, 0))
        # --- mirror frames ---
        for phase_fas in [self.phase1_actions, self.phase2_actions]:
            fa_mirror = FramesActions(FramesActions.Type.mirror)
            for _ in range(num_frames):
                fa_mirror.values.append(FramesActions.MirrorDirection.all_directions_1)
            phase_fas.append(fa_mirror)
        # --- rotation ---
        if _LIMITS["rotation"][0] < self.max_rotation <= _LIMITS["rotation"][1]:
            mul = 1 if clockwise else -1
            fa1_rot, fa2_rot = FramesActions(FramesActions.Type.rotation), FramesActions(FramesActions.Type.rotation)
            self._polynomial(fa1_rot, 0, - mul * self.max_rotation, num_frames)
            self._polynomial_inv(fa2_rot, mul * self.max_rotation, 0, num_frames)
            self.phase1_actions.append(fa1_rot)
            self.phase2_actions.append(fa2_rot)

        # --- crop ---
        for phase_fas in [self.phase1_actions, self.phase2_actions]:
            fa_crop = FramesActions(FramesActions.Type.crop)
            for _ in range(num_frames):
                fa_crop.values.append((1, 1))
            phase_fas.append(fa_crop)
        # --- brightness ---
        if _LIMITS["brightness"][0] <= self.max_brightness <= _LIMITS["brightness"][1] and self.max_brightness != 1:
            self._symmetric_action_value(self._linear, FramesActions.Type.brightness, 1,
                                         self.max_brightness, num_frames)
        # --- blur ---
        if _LIMITS["blur"][0] < self.max_blur <= _LIMITS["blur"][1]:
            self._symmetric_action_value(self._polynomial, FramesActions.Type.blur, 0,
                                         self.max_blur, num_frames, num_f_a_duplicates=num_frames_30p)
        # --- distortion ---
        if _LIMITS["distortion"][0] < self.max_distortion <= _LIMITS["distortion"][1]:
            self._symmetric_action_value(self._polynomial_inv, FramesActions.Type.distortion, 0,
                                         self.max_distortion, num_frames, num_f_b_duplicates=num_frames_50p)

    def _symmetric_action_value(self, func, action_type, f_a, f_b, length,
                                num_f_a_duplicates=0, num_f_b_duplicates=0, phase2_multiplier=1):
        p2m = phase2_multiplier
        phase1_fa = FramesActions(action_type)
        phase2_fa = FramesActions(action_type)
        [phase1_fa.values.append(f_a) for _ in range(num_f_a_duplicates)]
        [phase2_fa.values.append(f_b * p2m) for _ in range(num_f_b_duplicates)]
        func(phase1_fa, f_a, f_b, length - num_f_a_duplicates - num_f_b_duplicates)
        if phase1_fa.function == FramesActions.Function.linear:
            self._linear(phase2_fa, f_b * p2m, f_a * p2m, length - num_f_a_duplicates - num_f_b_duplicates)
        elif phase1_fa.function == FramesActions.Function.polynomial:
            self._polynomial_inv(phase2_fa, f_b * p2m, f_a * p2m, length - num_f_a_duplicates - num_f_b_duplicates)
        elif phase1_fa.function == FramesActions.Function.polynomial_inv:
            self._polynomial(phase2_fa, f_b * p2m, f_a * p2m, length - num_f_a_duplicates - num_f_b_duplicates)
        else:
            log_error("this should never happens")
        [phase1_fa.values.append(f_b) for _ in range(num_f_b_duplicates)]
        [phase2_fa.values.append(f_a * p2m) for _ in range(num_f_a_duplicates)]
        self.phase1_actions.append(phase1_fa)
        self.phase2_actions.append(phase2_fa)

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
    def _polynomial(frame_action, f_a, f_b, length, strength=3.0):
        xa, xb = 0, length - 1
        c1 = (f_b - f_a) / ((xb - xa) ** strength)
        c2 = f_a
        for xi in range(length):
            frame_action.values.append(c1 * ((xi - xa) ** strength) + c2)
        frame_action.function = FramesActions.Function.polynomial

    @staticmethod
    def _polynomial_inv(frame_action, f_a, f_b, length, strength=3.0):
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
        peak_distortion_msg = []
        peak_distortion_value = 0.0
        peak_distortion_img = None
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
                        if value > peak_distortion_value:
                            peak_distortion_msg = AnimationImages.PincushionDeformation(value, 1.0).get_debug_info(img)
                            peak_distortion_value = value
                            peak_distortion_img = img_path
                    elif action.action_type == FramesActions.Type.brightness:
                        img = AnimationImages.brightness_effect(img, value)
                    if debug or action_idx == len(actions) - 1:
                        img.save(str(img_save_folder / img_path.name))

                log_debug("")
        if peak_distortion_img is not None:
            log_debug(f"peak distortion effect: value [{peak_distortion_value}:.1%], img path: [{peak_distortion_img}]")
            for line in peak_distortion_msg:
                log_debug(line)
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
        try:
            return new_img.resize((w, h), Image.Resampling.BICUBIC)
        except AttributeError:
            return new_img.resize((w, h), Image.BICUBIC)

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
        self.input_vid1 = None
        self.input_vid2 = None
        self.phase1_vid = None
        self.phase2_vid = None
        self.merged_vid = None
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
            self._suggest_output(in_args.output)
        if in_args.debug:
            self.tmp_path = self.output.parent / (self.output.stem + "_debug")
            if self.tmp_path.is_dir():
                shutil.rmtree(str(self.tmp_path))
            self.tmp_path.mkdir()

        self._setup_logging(in_args.debug, self.tmp_path / f"{__package__}.log")
        intro_print(in_args.art)
        if not self._verify_critical_info(in_args):
            return False

        self.phase1_vid = self.output.parent / (self.output.stem + "_phase1" + _OUTPUT_VIDEO_TYPE)
        self.phase2_vid = self.output.parent / (self.output.stem + "_phase2" + _OUTPUT_VIDEO_TYPE)
        self.merged_vid = self.output.parent / (self.output.stem + "_merged" + _OUTPUT_VIDEO_TYPE)
        log_info(f"first input video: {self.input_vid1}")
        log_info(f"second input video: {self.input_vid2}")
        if in_args.merge:
            log_debug(f"transition phase1 video: {self.phase1_vid}")
            log_debug(f"transition phase2 video: {self.phase2_vid}")
            log_info(f"output transition merged video: {self.merged_vid}")
        else:
            log_info(f"output transition phase1 video: {self.phase1_vid}")
            log_info(f"output transition phase2 video: {self.phase2_vid}")
        self._get_fps_from_video()
        log_info(f"frames per second (FPS): {self.fps}")

        self.vid1_raw_images_folder = self.tmp_path / "1_phase1_raw"
        self.vid2_raw_images_folder = self.tmp_path / "1_phase2_raw"
        self.vid1_raw_images_folder.mkdir()
        log_debug(f"created vid1_raw_images_folder: {self.vid1_raw_images_folder}")
        self.vid2_raw_images_folder.mkdir()
        log_debug(f"created vid2_raw_images_folder: {self.vid2_raw_images_folder}")
        if not self._extract_phase1_images(in_args.num_frames):
            return False
        num_frames_for_vid2 = in_args.num_frames
        if self.animation == Animations.long_translation or self.animation == Animations.long_translation_inv:
            num_frames_for_vid2 = 2 * in_args.num_frames
        if not self._extract_phase2_images(num_frames_for_vid2):
            return False
        log_info(f"number of frames for phase1: [{len(self.phase1_images)}], for phase2: [{len(self.phase2_images)}]")
        return True

    def final_images_to_video(self, res_folders):
        output_videos = [self.phase1_vid, self.phase2_vid]
        fps = str(self.fps)
        for idx in range(2):
            log_info(f"merging phase_{idx} images into a video ...")
            img_names = [f.stem for f in res_folders[idx].glob("*.png")]
            img_names.sort()
            start_idx = f"{max(int(img_names[0]) - 1, 0):04d}"
            cmd = ["ffmpeg", "-hide_banner", "-start_number", start_idx, "-framerate", fps, "-y", "-r", fps,  "-i",
                   str(res_folders[idx] / "%04d.png"), "-r", fps, "-vcodec", _OUTPUT_VIDEO_CODEC,
                   str(output_videos[idx])]
            self._exec_command(cmd, f"command used for merging phase_{idx} images into a video ...")
            if not output_videos[idx].is_file():
                log_error(f"ffmpeg failed to convert images to: {output_videos[idx]}")
                return False
        return True

    def _verify_critical_info(self, in_args):
        if shutil.which("ffmpeg") is None:
            log_error("'ffmpeg' is not installed, please install it before use")
            return False
        if len(in_args.input) < 2 or len(in_args.input) > 2:
            log_error(f"2 input videos needed, [{len(in_args.input)}] provided")
            return False
        self.input_vid1 = pathlib.Path(in_args.input[0])
        if not self.input_vid1.is_file():
            log_error(f"could not find first video under: {self.input_vid1}")
            return False
        self.input_vid2 = pathlib.Path(in_args.input[1])
        if not self.input_vid2.is_file():
            log_error(f"could not find second video under: {self.input_vid2}")
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
            log_info(_ANIMATION_HELP)
            return False
        return True

    def _extract_phase1_images(self, in_num_frames):
        duration_ms = int(math.ceil(1000 * (in_num_frames + 2) / self.fps))
        cmd = ["ffmpeg", "-hide_banner", "-sseof", f"-{duration_ms}ms", "-i", str(self.input_vid1),
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

    def _extract_phase2_images(self, in_num_frames):
        duration_ms = int(math.ceil(1000 * (in_num_frames + 2) / self.fps))
        cmd = ["ffmpeg", "-hide_banner", "-to", f"{duration_ms}ms", "-i", str(self.input_vid2),
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
        return res.stdout, res.stderr

    def _get_fps_from_video(self):
        cmd = ["ffmpeg", "-hide_banner", "-i", str(self.input_vid1)]
        stdout, stderr = self._exec_command(cmd, "command used for extracting FPS")
        res = (stdout.lower() + " " + stderr.lower()).split(" ")
        log_debug("searching for FPS value in ffmpeg video information")
        for fps_word in ["fps", "fps,"]:
            for idx, word in enumerate(res):
                if word == fps_word:
                    try:
                        self.fps = int(res[idx - 1])
                        log_debug(f"FPS extracted from video [{self.fps}]")
                        return
                    except ValueError:
                        log_debug(f"failed extract FPS, value [{res[idx - 1]}], error :[{ValueError}]")

        log_warning(f"cloud not retrieve FPS value from video (using ffmpeg): {self.input_vid1}")
        log_warning("falling back to FPS value of [30]")
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

    def _suggest_output(self, in_output):
        # self.output = pathlib.Path().cwd() / "vt_debug"
        # return
        if in_output != "":
            out_path = pathlib.Path(in_output)
            self.output = out_path.parent / out_path.stem
            return
        cur_dir = pathlib.Path().cwd()
        video_files = [f.name for f in cur_dir.glob("*" + _OUTPUT_VIDEO_TYPE)]
        num = 1
        previous_num = 0
        while previous_num != num:
            previous_num = num
            for vn in video_files:
                if vn.startswith(f"vt{num}_"):
                    num += 1
        self.output = cur_dir / f"vt{num}"

    def merge_video_chunks(self):  # TODO implement
        log_info("merging the two phases video chunks into one transition video")
        cmd = ["ffmpeg", "-hide_banner", "-i", str(self.phase1_vid), "-i",  str(self.phase2_vid),
               "-filter_complex", "[0:v] [1:v] concat=n=2:v=1 [v]", "-map", "[v]", str(self.merged_vid)]
        self._exec_command(cmd, f"command used for merging phase video chunks into the output video ...")

        if not self.merged_vid.is_file():
            log_error(f"ffmpeg failed to merge video phases into: {self.merged_vid}")
            return False

        log_debug(f"remove output video phase1: {self.phase1_vid}")
        self.phase1_vid.unlink(missing_ok=True)
        log_debug(f"remove output video phase2: {self.phase2_vid}")
        self.phase2_vid.unlink(missing_ok=True)
        return True

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
                        type=str2bool, default=DEBUG, metavar='\b')
    parser.add_argument('-t', '--art', help='Display ASCII art', type=str2bool, default=ART, metavar='\b')
    parser.add_argument('-e', '--remove', help='delete original videos after a successful animation creation',
                        type=str2bool, default=REMOVE_ORIGINAL, metavar='\b')
    parser.add_argument('-m', '--merge', help='merge both phases video chunks into one transition video',
                        type=str2bool, default=MERGE_PHASES, metavar='\b')
    args = parser.parse_args()

    if args.animation.lower() == "help":
        print(_ANIMATION_HELP)
        exit(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        dh = DataHandler()
        if not dh.verify_arguments(args, tmp_path):
            exit(1)

        actions_determinator = AnimationActions(args.max_zoom, args.max_brightness, args.max_rotation, args.max_blur,
                                                args.max_distortion, args.num_frames)

        phase1_actions, phase2_actions = actions_determinator.get_actions_values(dh.animation)

        final_phase_folder = AnimationImages.make_transition(dh.tmp_path, dh.phase1_images, dh.phase2_images,
                                                             phase1_actions, phase2_actions, args.debug)

        if not dh.final_images_to_video(final_phase_folder):
            exit(1)
        if args.merge:
            if not dh.merge_video_chunks():
                exit(1)
            log_info(f"output transition video: {dh.merged_vid}")
        else:
            log_info(f"output transition phase1 video: {dh.phase1_vid}")
            log_info(f"output transition phase2 video: {dh.phase2_vid}")
        if args.remove:
            log_debug(f"remove original video1: {dh.input_vid1}")
            dh.input_vid1.unlink()
            log_debug(f"remove original video2: {dh.input_vid2}")
            dh.input_vid2.unlink()
        log_info("")
        log_info((f" Transition finished. Duration = {dh.get_duration_msg()} ".center(80, "=")))
        log_info("")
        end_print(args.art)
    exit(0)
