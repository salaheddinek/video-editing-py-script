import math
import pathlib
from PIL import Image, ImageOps


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
    s = 0.7
    z = 1.0
    a = False
    home = pathlib.Path().home()
    for i in [1, 2, 3]:
        image = Image.open(str(home / f'pic{i}_a.jpg'))
        if i == 1:
            PincushionDeformation(s, z, a).print_debug_info(image)
        result_image = ImageOps.deform(image, PincushionDeformation(s, z, a))
        print(f"finished {i}")
        result_image.save(str(home / f'pic{i}_b.jpg'))
