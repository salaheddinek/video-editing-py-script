__package__ = "vid_transition"

import math
import pathlib
import enum
import logging
from PIL import Image, ImageOps, ImageEnhance


def log_debug(msg):
    logger = logging.getLogger(__package__)
    logger.debug(msg)


def log_info(msg):
    logger = logging.getLogger(__package__)
    logger.info(msg)


def log_warning(msg):
    logger = logging.getLogger(__package__)
    logger.info("WARNING: " + msg)


def log_error(msg):
    logger = logging.getLogger(__package__)
    logger.error("ERROR: " + msg)


def setup_logging(debug, log_file_path):
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
        if log_file_path.is_file():
            log_file_path.unlink()

        handler = logging.FileHandler(str(log_file_path), encoding='utf8')
        n_formatter = logging.Formatter('[%(levelname)s] [%(asctime)s] - %(message)s', "%H:%M:%S")
        handler.setFormatter(n_formatter)
        handler.setLevel(logging.DEBUG)
        init_logger.addHandler(handler)


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
        num_f = self.half_animation_num_frames
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
        if 5 < self.max_rotation <= 90:
            fa_rot = FramesActions(FramesActions.Type.rotation)
            mul = 1
            if not clockwise:
                mul = -1
            # [fa_rot.values.append(0) for _ in range(num_frames_30p)]
            self._polynomial(fa_rot, 0, mul * self.max_rotation, num_frames)
            self.phase1_actions.append(fa_rot)
        else:
            log_warning(f"max rotation should be between 5 and 90 degrees (provided value: {self.max_rotation})")
        # --- crop ---
        fa_crop = FramesActions(FramesActions.Type.crop)
        for _ in range(num_frames):
            fa_crop.values.append((1, 1, 2, 2))
        self.phase1_actions.append(fa_crop)
        # --- blur ---
        if 0.05 < self.max_blur <= 1:
            fa_blur = FramesActions(FramesActions.Type.blur)
            [fa_blur.values.append(0) for _ in range(num_frames_30p)]
            self._polynomial(fa_blur, 0, self.max_blur, num_frames_70p)
            self.phase1_actions.append(fa_blur)
        else:
            log_warning(f"max blur should be between 5% and 100% (provided value: {self.max_blur:.1%})")
        # --- distortion ---
        if 0.3 < self.max_distortion <= 1:
            fa_distortion = FramesActions(FramesActions.Type.distortion)
            self._linear(fa_distortion, 0, self.max_distortion, num_frames_70p)
            [fa_distortion.values.append(self.max_distortion) for _ in range(num_frames_30p)]
            self.phase1_actions.append(fa_distortion)
        else:
            log_warning(f"max distortion should be between 25% and 100% (provided value: {self.max_distortion:.1%})")

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
        if 5 < self.max_rotation <= 90:
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
            fa_crop.values.append((1, 1, 2, 2))
        self.phase2_actions.append(fa_crop)
        # --- blur ---
        if 0.05 < self.max_blur <= 1:
            fa_blur = FramesActions(FramesActions.Type.blur)
            self._polynomial(fa_blur, self.max_blur, 0, num_frames_70p)
            [fa_blur.values.append(0) for _ in range(num_frames_30p)]
            self.phase2_actions.append(fa_blur)
        # --- distortion ---
        if 0.3 < self.max_distortion <= 1:
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
                    log_debug(f"mirroring frames, type: [{action.action_type.name}]")
                    log_debug(f"* values: [{action.values[0].name}] - num frames: [{len(action.values)}]")
                elif action.action_type == FramesActions.Type.zoom:
                    log_debug(f"zoom effect, max value: [{self.max_zoom:.1%}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.crop:
                    log_debug(f"crop effect")
                    cropped = [f"({v[0]:g}, {v[1]:g}, {v[2]:g}, {v[2]:g})" for v in action.values]
                    log_debug(f"* values: {format_list(cropped, 's')}")
                elif action.action_type == FramesActions.Type.rotation:
                    log_debug(f"rotation effect, max value (in degrees): [{self.max_rotation:.1f}]")
                    log_debug(f"* values (degree): {format_list(action.values, '.1f')}")
                elif action.action_type == FramesActions.Type.blur:
                    log_debug(f"blur effect, max value: [{self.max_blur:.1%}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.distortion:
                    log_debug(f"len pincushion distortion effect, max value: [{self.max_distortion:.1%}]")
                    log_debug(f"* values: {format_list(action.values, '.1%')}")
                elif action.action_type == FramesActions.Type.brightness:
                    log_debug(f"brightness effect, max value: [{self.max_brightness:.1%}]")
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
        print(f"correction radius => {self.correction_radius}")
        if self.auto_zoom:
            r = math.sqrt(min(self.half_height, self.half_width) ** 2) / self.correction_radius
            self.zoom = r / math.atan(r)

    def print_debug_info(self, img):
        self.determine_parameters(img)
        w, h = img.size
        print(" lens distortion debug info ".center(80, '='))
        print(f"input image size: [w:{w}, h:{h}]")
        if not self.auto_zoom:
            print(f"strength: [{self.strength:.0%}] , automatic zoom: [Off] , provided zoom: [{self.zoom:.0%}]")
        else:
            print(f"strength: [{self.strength:.0%}] , automatic zoom: [On] , calculated zoom: [{self.zoom:.0%}]")
        print("corner points displacement:")
        points = {"top-left": (0, 0), "top-center": (self.half_width, 0), "top-right": (w, 0),
                  "left": (0, self.half_height), "right": (w, self.half_height),
                  "bottom-left": (0, h), "bottom-center": (self.half_width, h), "bottom-right": (w, h)}
        for key, value in points.items():
            res = self.transform(value[0], value[1])
            print(f"* {key:<13s} [x:{res[0]:<6.1f}, y:{res[1]:<6.1f}] => [{value[0]:<4.0f}, {value[1]:<4.0f}]")
        print("")

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


if __name__ == "__main__":

    log_test_path = pathlib.Path().home() / f"{__package__}.log"
    setup_logging(True, log_test_path)

    aa = AnimationActions(1.2, 1.2, 45, 0.2, 0.7, 10)
    res1, res2 = aa.get_actions_values(Animations.rotation)
    quit()

    s = 0.7
    z = 1.0
    a = False
    home = pathlib.Path().home()
    for i in [1, 2, 3]:
        image = Image.open(str(home / f'pic{i}_a.jpg'))
        if i == 1:
            PincushionDeformation(s, z, a).print_debug_info(image)
        result_image = ImageOps.deform(image, PincushionDeformation(s, z, a))
        enhancer = ImageEnhance.Brightness(result_image)
        result_image = enhancer.enhance(1.6)
        print(f"finished {i}")
        result_image.save(str(home / f'pic{i}_b.jpg'))
