#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from datetime import datetime
import pathlib
import yt_dlp


URL = ""  # "https://www.youtube.com/watch?v=es4x5R-rV9s"
TIME_LAPSE = ["", ""]  # ["00:00:30", "00:01:00"]
DEBUG = False
OUTPUT = ""
VIDEO_ONLY = False
AUDIO_ONLY = False
ALLOW_4K_VIDEO = False
ART = True


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
            except ValueError as ve:
                raise ValueError("ERROR: while parsing time interval: ", ve)
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


def download_video_audio(in_url, in_t_interval, in_output, in_debug, in_dlp_format):

    res_path = in_output
    if pathlib.Path(in_output).suffix == "":
        res_path += ".%(ext)s"

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
    print("downloading video/audio ...")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download(in_url)

        opts = {
            **ydl.params,
            "external_downloader": "native",
            "external_downloader_args": {},
            "writesubtitles": True,
            # if you also want automatically generated captions/subtitles
            "writeautomaticsub": True,
            # so we only get the captions and don't download the (whole) video again
            "skip_download": True,
        }
        ydl.params = opts
        ydl.download(in_url)


def get_video_name(in_url, in_t_interval, in_dlp_format, in_ext, in_debug):
    ydl_opts = {"quiet": not in_debug, "simulate": True, "forceurl": True, "format": in_dlp_format}
    print("getting video info for naming ...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        vid_info_raw = ydl.extract_info(in_url, download=False)
        vid_info = ydl.sanitize_info(vid_info_raw)

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
    for ext in ["*.mp4", "*.mkv", "*.webm", "*.m4a", "*.mp3", "*.mov", "*.avi", "*.m4v"]:
        for f in pathlib.Path.cwd().glob(ext):
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
        vid_time = f'_{in_t_interval.start.strftime("%H.%M.%S")}'

    return f"{num}{main_name}{v_id}{vid_time}{in_ext}"


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


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Downloads video or part of a video using yt-dlp and ffmpeg')
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
    parser.add_argument('-A', '--art', help='Display ASCII art', type=str2bool,
                        default=ART, metavar='\b')
    args = parser.parse_args()

    intro_print(args.art)

    if shutil.which("ffmpeg") is None:
        print(f"ERROR: 'ffmpeg' is not installed, please install it before use")
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
    if len(url) == 0:
        url = get_url_text()
    output_path = args.output
    if output_path == "":
        output_path = get_video_name(url, t_interval, dlp_format, extension, args.debug)

    download_video_audio(url, t_interval, output_path,args.debug, dlp_format)

    if not args.debug:
        print("")
        print(f"finished downloading video: {url}")
        t_interval.print_interval_str()
        print(f'video name: {output_path}')
        print("")
        print(("video download finished. Duration = {} ".format(pretty_time_delta(datetime.now() - exec_start_time))))
        print("")

    end_print(args.art)


if __name__ == "__main__":
    main()
