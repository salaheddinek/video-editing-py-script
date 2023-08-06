#!/usr/bin/env python3
import argparse
import shutil
import tempfile
import subprocess
from datetime import datetime
import pathlib
import os
import yt_dlp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


URL = ""  # "https://www.youtube.com/watch?v=es4x5R-rV9s"
TIME_LAPSE = ["", ""]  # ["00:00:30", "00:01:00"]
DEBUG = False
OUTPUT = ""
VIDEO_ONLY = False
AUDIO_ONLY = False
ALLOW_4K_VIDEO = False
ART = True
ADD_REFERENCE = True
REFERENCE_CORNER = "top-left"  # choices = ["top-left", "top-right", "bottom-left", "bottom-right"]
REFERENCE_OPACITY = 0.5
REFERENCE_COLOR = "250,250,250"


# internal parameters
_GENERIC_EXT = ".%(ext)s"  # extension of the downloaded video (only if no reference is added)
_EXTENSIONS = ['webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 'yuv', 'rm',
               'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 'svi', '3gp', '3g2',
               'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b'
               # audio files
               "wav", "aiff", "mp3", "aac", "ogg", "wma", "flac", "aac", "ape", "opus"]
_ANTI_ALIASING = False  # activate antialiasing
_BOUNDING_BOX = (0.7, 0.03)  # the bounding box of the reference text (font size estimated automatically)
_APPLY_SHADOW = True  # add a small drop shadow for reference text for more visibility
_SHADOW_TRANSPARENCY_MULTIPLIER = 0.4  # shadow opacity compared to text opacity
_SHADOW_WIDTH = 3  # width of shadow in pixels
_MAX_NUM_CHARACTERS = 120  # if reference is too long then more character are replace by '...'
_FONT_PATH = "DejaVuSans"  # font path or font name in case using Linux
_MERGED_VIDEO_EXTENSION = ".mp4"  # video extension if reference text is added
_MERGED_VIDEO_CODEC = "h264"  # video codec if reference text is added


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = '''
        Yb    dP 88 8888b.  888888  dP"Yb      8888b.  Yb        dP 88b 88
         Yb  dP  88  8I  Yb 88__   dP   Yb      8I  Yb  Yb  db  dP  88Yb88
          YbdP   88  8I  dY 88""   Yb   dP      8I  dY   YbdPYbdP   88 Y88 .o.
           YP    88 8888Y"  888888  YbodP      8888Y"     YP  YP    88  Y8 `"'
    '''
    if in_art:
        print(intro)
    print((" starting to download the video ".center(80, "=")))
    print("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.
    ______     d88ooo  888_dPY8   88   8     ______
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX
             88bdPPP   Y8P   Y8   88oop'
    """

    print((" Video download finished ".center(80, "=")))
    if in_art:
        print(end)


class TimeInterval:
    def __init__(self, in_timestamps):
        self.provided = False
        if len(in_timestamps) != 2:
            raise ValueError(f"--time_lapse should have 2 timestamps, {len(in_timestamps)} are given")
        if in_timestamps[0] == "" and in_timestamps[1] == "":
            return

        formatted_timestamps = []
        for t in in_timestamps:
            t = t.replace("::", ":")
            t = t.replace(".", ":")
            try:
                formatted_timestamps += [datetime.strptime(t, '%H:%M:%S')]
            except ValueError as vae:
                raise ValueError("ERROR: while parsing time interval: ", vae)
        self.start = min(formatted_timestamps)
        self.end = max(formatted_timestamps)
        self.provided = True

    def start_in_seconds(self):
        return int((self.start - datetime.strptime("0:00:00", '%H:%M:%S')).total_seconds())

    def end_in_seconds(self):
        return int((self.end - datetime.strptime("0:00:00", '%H:%M:%S')).total_seconds())

    def print_interval_str(self):
        if not self.provided:
            return
        msg = f'video timestamps: {self.start.strftime("%H:%M:%S")} ({self.start_in_seconds()}s) -> '
        msg += f'{self.end.strftime("%H:%M:%S")} ({self.end_in_seconds()}s)'
        print(msg)


class TextPainter():
    """paint a text image"""
    def __init__(self, vid_info: dict, opacity: float, corner: str, color:tuple):
        self.text = ""
        self.resolution = (1920, 1080)
        self._get_reference_text_and_resolution(vid_info)
        self.resolution_original = self.resolution  
        self.opacity = opacity
        self.justify = "left"
        if "right" in corner.lower():
            self.justify = "right"
        self.is_top = True
        if "bottom" in corner.lower():
            self.is_top = False
        self.text_bbox = (int(round(_BOUNDING_BOX[0] * self.resolution[0])), 
                          int(round(_BOUNDING_BOX[1] * self.resolution[1])))
        if _ANTI_ALIASING:
            self.text_bbox = (2 * self.text_bbox[0], 2 * self.text_bbox[1])
            self.resolution = (2 * self.resolution_original [0], 2 * self.resolution_original [1])  
            
        self.num_dilations = 1
        self.color = (color[0], color[1], color[2], 255)
        self.shadow_color = (255 - color[0], 
                             255 - color[1], 
                             255 - color[2], 
                             int(round(255 * _SHADOW_TRANSPARENCY_MULTIPLIER)))

        self.font = self._get_font_path()
        self.font_size = None
        self._choose_font_size()


    def _get_reference_text_and_resolution(self, vid_info: dict):
        if "webpage_url_domain" in vid_info:
            self.text += vid_info["webpage_url_domain"].split(".")[0].lower().strip() + ": "
        else:
            raise ValueError("could not get video information")
        
        if "channel" in vid_info:
            self.text += vid_info["channel"] + " - "
        elif "uploader" in vid_info:
            self.text += vid_info["uploader"] + " - "

        
        if "title" in vid_info:
            self.text += vid_info["title"]
        elif "id" in vid_info:
            self.text += "id: " + vid_info["id"]
        else:
            raise ValueError("could not get video information")
        
        if len(self.text) > _MAX_NUM_CHARACTERS:
            self.text  = self.text[:_MAX_NUM_CHARACTERS] + " ..."

        if "width" in vid_info and "height" in vid_info: 
            self.resolution = (vid_info["width"], vid_info["height"])
        else:
            print("WARNING: could not get resolution from video info")


    @staticmethod
    def _get_font_path():  # only for linux right now
        font_name = _FONT_PATH
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


    def get_image(self):
        img = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
        pil_font = ImageFont.truetype(self.font, self.font_size)
        draw = ImageDraw.Draw(img)
        anchor = self.justify[0] + "a"

        pos = [1, 1]
        if self.justify == "right":
            pos[0] = self.resolution[0] - 1

        if not self.is_top:
            anchor = self.justify[0] +  "d"
            pos[1] = self.resolution[1] - 1

        draw.multiline_text(pos, self.text, self.color, font=pil_font, anchor=anchor, align=self.justify)

        if _APPLY_SHADOW:
            shadow = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
            draw = ImageDraw.Draw(shadow)
            draw.multiline_text(pos, self.text, self.shadow_color, font=pil_font, anchor=anchor, align=self.justify)
            shadow = shadow.filter(ImageFilter.BoxBlur(_SHADOW_WIDTH))
            img = Image.alpha_composite(shadow, img)

            alpha = img.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(self.opacity)
            img.putalpha(alpha)

        if _ANTI_ALIASING:
            img = img.resize(self.resolution_original, resample=Image.Resampling.LANCZOS)
        
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
            if f_size >= self.text_bbox[0]:
                overflow = True
            # print(f"bbox = [{bbox}] , f_size = {f_size}")
        f_size -= 1
        self.font_size = f_size
        print(f"estimated font size: {self.font_size}")



def get_time_interval(parsed_time: str):
    out = TimeInterval(parsed_time)
    return out


def get_url_text():
    msg = "Please enter the video url:"
    if shutil.which("zenity") is not None:
        res = subprocess.run(["zenity", "--entry", "--title", 'input', "--text", msg],
                             stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    elif shutil.which("kdialog") is not None:
        res = subprocess.run(["kdialog", "--title", "Input", "--inputbox", msg],
                             stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    else:
        res = input(msg)
    # print("=>" + res)
    return res


def search_for_output(in_output: str):
    out_path = pathlib.Path(in_output)
    if out_path.suffix[1:].lower() in _EXTENSIONS:
        return out_path

    for itr_file in out_path.parent.glob("*"):
        if itr_file.stem.startswith(out_path.name):
            return itr_file
    return pathlib.Path("")


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def download_video_audio(in_url, in_t_interval, in_output, in_debug, in_dlp_format):

    res_path = in_output
    if pathlib.Path(in_output).suffix == "":
        res_path += _GENERIC_EXT

    def set_download_ranges(info_dict, self):
        duration_opt = [{
            'start_time': in_t_interval.start_in_seconds(),
            'end_time': in_t_interval.end_in_seconds()
        }]
        return duration_opt

    opts = {
        "external_downloader": "ffmpeg",
        "force_keyframes_at_cuts": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "quiet": not in_debug,
        "outtmpl": res_path,
        "format": in_dlp_format,
    }
    if in_t_interval.provided:
        opts["download_ranges"] = set_download_ranges
    print("downloading media ...")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download(in_url)
        out_path = search_for_output(in_output)
        if out_path.is_file():
            return out_path

        opts = {
            **ydl.params,
            "external_downloader": "native",
            "external_downloader_args": {},
            "writesubtitles": False,
            # if you also want automatically generated captions/subtitles
            "writeautomaticsub": False,
            # so we only get the captions and don't download the (whole) video again
            "skip_download": True,
        }
        ydl.params = opts
        ydl.download(in_url)
        return search_for_output(in_output)


def get_video_name(vid_info, in_t_interval, in_ext):
    v_id = ""
    if "id" in vid_info:
        v_id = "_" + vid_info["id"]

    main_name = "_vid"
    if "webpage_url_domain" in vid_info:
        website = vid_info["webpage_url_domain"].split(".")[0].lower().strip()
        if website == "youtube":
            main_name = "_you"
        elif "pin" in website:
            main_name = "_pin"
        elif "vimeo" in website:
            main_name = "_vim"

    files = []
    for ext in _EXTENSIONS:
        for f in pathlib.Path.cwd().glob("*." + ext):
            files += [f]
    num = 1
    previous_num = 0
    while previous_num != num:
        previous_num = num
        for f in files:
            if f.name.startswith(f"{num}_"):
                num += 1

    vid_time = ""
    if in_t_interval.provided:
        vid_time = f'_{in_t_interval.start.strftime("%Hh%Mm%Ss")}'

    return f"{num}{main_name}{v_id}{vid_time}{in_ext}"

def merge_video_with_reference_image(tmp_vid_path, tmp_reference_path, output_path, debug):
    log_level = "quiet"
    if debug:
        log_level = "info"

    cmd = f'ffmpeg -y -hide_banner -loglevel {log_level} -i "{str(tmp_vid_path)}" -i "{str(tmp_reference_path)}" '
    cmd += f'-filter_complex "[0:v][1:v] overlay=0:0" -c:v {_MERGED_VIDEO_CODEC} -c:a copy "{str(output_path)}"'
    # print(cmd)
    os.system(cmd)


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
    if v.lower() in ('yes', 'true', 't', 'y', 'on', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', 'off', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected, possible values: yes, y, true, 1, no, n, false, 0.')


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


def main():
    corner_choices = ["top-left", "top-right", "bottom-left", "bottom-right"]
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Downloads video or part of a video using yt-dlp and ffmpeg, '
                                                 'also add the reference to the video  source')
    parser.add_argument('-u', '--url', type=str, help='The video url', metavar='\b', default=URL)
    parser.add_argument('-t', '--time_interval', help='time interval of the video part, two timestamps needed: '
                                                      'start and stop, accepted format: hh:mm:ss or  hh.mm.ss',
                        type=str, nargs=2, metavar='\b', default=TIME_LAPSE)
    parser.add_argument('-o', '--output', help='output video path. (without extension)', type=str, metavar='\b',
                        default=OUTPUT)
    parser.add_argument('-v', '--video_only', help='download the video without the audio', type=str2bool,
                        default=VIDEO_ONLY, metavar='\b')
    parser.add_argument('-a', '--audio_only', help='download the audio without the video', type=str2bool,
                        default=AUDIO_ONLY, metavar='\b')
    parser.add_argument('-d', '--debug', help='show debug info about the video URL', type=str2bool,
                        default=DEBUG, metavar='\b')
    parser.add_argument('-l', '--allow_4k', help='allow the download of videos with resolution higher then FullHD',
                        type=str2bool, default=ALLOW_4K_VIDEO, metavar='\b')
    parser.add_argument('-r', '--reference', help='add the reference of download source in a video corner',
                        type=str2bool, metavar='\b', default=ADD_REFERENCE)
    parser.add_argument('-n', '--corner', help='the corner where to put the reference: ' + str(corner_choices),
                        type=str, choices=corner_choices, metavar='\b', default=REFERENCE_CORNER)
    parser.add_argument('-c', '--color', help='reference text font color (HEX and RGB are accepted)', type=str,  
                        default=REFERENCE_COLOR, metavar='\b')
    parser.add_argument('-O', '--opacity', help='the opacity of the reference text [0, 1]',
                        type=float, choices=corner_choices, metavar='\b', default=REFERENCE_OPACITY)
    parser.add_argument('-A', '--art', help='Display ASCII art', type=str2bool,
                        default=ART, metavar='\b')
    args = parser.parse_args()

    intro_print(args.art)

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    t_interval = get_time_interval(args.time_interval)

    exec_start_time = datetime.now()

    if args.video_only and args.audio_only:
        raise ValueError("ERROR: you chose both 'video_only' and 'audio_only' modes, only one can be chosen")

    extension = ""
    if args.audio_only:
        extension = ".mp3"
        dlp_format = "bestaudio/best"
    elif args.video_only:
        extension = ".mp4"
        if args.allow_4k:
            dlp_format = "bestvideo/best"
        else:
            dlp_format = "bestvideo[height<=?1080]/best"
    else:
        if args.allow_4k:
            dlp_format = "bestvideo+bestaudio/best"
        else:
            dlp_format = "bestvideo[height<=?1080]+bestaudio/best"

    url = args.url
    ref_color = tuple(parse_color(args.color))
    if 0.0 > args.opacity or args.opacity > 1.0:
        raise ValueError("Opacity should be between 0 and 1.")
    if len(url) == 0:
        url = get_url_text()

    ydl_opts = {"quiet": not args.debug, "simulate": True, "forceurl": True, "format": dlp_format}
    print("getting video info ...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        vid_info_raw = ydl.extract_info(url, download=False)
        vid_info = ydl.sanitize_info(vid_info_raw)

    output_path = args.output
    if output_path == "":
        output_path = get_video_name(vid_info, t_interval, extension)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)

        if args.reference and not args.audio_only:
            tmp_vid = tmp_path / pathlib.Path(output_path).name
            tmp_res_path = download_video_audio(url, t_interval, str(tmp_vid), args.debug, dlp_format)
            if not tmp_res_path.is_file():
                print("ERROR: could not download file: " + str(tmp_res_path))

            print("creating the reference image ...")
            ref_painter = TextPainter(vid_info, args.opacity, args.corner, ref_color)
            img = ref_painter.get_image()
            img_path = tmp_path / "vid_ref.png"
            img.save(str(img_path))
            
            print("merging video and reference image ...")
            res_path = pathlib.Path(output_path).parent / (pathlib.Path(tmp_res_path).stem + _MERGED_VIDEO_EXTENSION)
            merge_video_with_reference_image(tmp_res_path, img_path, res_path, args.debug)

        else:
            res_path = download_video_audio(url, t_interval, output_path, args.debug, dlp_format)

        if not res_path.is_file():
            print("ERROR: could not download file: " + str(res_path))
        else:
            print("")
            print(f"finished downloading media from: {url}")
            t_interval.print_interval_str()
            print("size: " + sizeof_fmt(res_path.stat().st_size))
            print(f'file path: {res_path}')
            print("")
            print("media download finished. Duration = " + pretty_time_delta(datetime.now() - exec_start_time))
            print("")

    end_print(args.art)


if __name__ == "__main__":
    main()
