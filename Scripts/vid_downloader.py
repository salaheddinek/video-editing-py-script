#!/usr/bin/python3
import argparse
import shutil
import subprocess
import os
from datetime import datetime
import pathlib


URL = ""
TIME_LAPSE = ""  # "00:00:30 00:01:00"
DEBUG = False
OUTPUT = ""
VIDEO_ONLY = False
AUDIO_ONLY = False
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


def get_start_and_end_time(parsed_time: str):
    if len(parsed_time) != 2:
        raise Exception(f"--time_lapse should have 2 timestamps, {len(parsed_time)} are given")
    out = []
    for t in parsed_time:
        t = t.replace("::", ":")
        t = t.replace(".", ":")
        try:
            out += [datetime.strptime(t, '%H:%M:%S')]
        except ValueError as ve:
            print("ERROR: ", ve)
            exit(1)
    return sorted(out)


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


def download_partial_video(in_url, in_timestamps, in_output, in_debug, in_video_only, in_audio_only):
    res1 = subprocess.run(["youtube-dl", "--get-url", "--youtube-skip-dash-manifest", "-f",
                           "bestvideo[height<=?1080]+bestaudio/best", in_url],
                          stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]

    url_2 = res1.split("\n")
    print(url_2)
    if len(url_2) != 2:
        raise ValueError("ERROR: the command  'youtube-dl --get-url' should produce 2 urls")
    start_t = f'{in_timestamps[0].strftime("%H:%M:%S")}.00'
    end_t = f'{in_timestamps[1].strftime("%H:%M:%S")}.00'
    res = "ffmpeg -hide_banner"
    if not in_audio_only:
        res += f" -ss {start_t} -to {end_t} -i '{url_2[0]}'"
    if not in_video_only:
        res += f" -ss {start_t} -to {end_t} -i '{url_2[1]}'"
    res += f" {in_output}.mp4"
    if in_debug:
        print("exec command: \n")
        print(res)
    else:
        os.system(res)


def get_video_name(in_url, in_timestamps):
    v_id = "_" + subprocess.run(["youtube-dl", "--get-id", f"{url}"],
                                stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
    if "error" in v_id.lower():
        v_id = ""
    main_name = "_vid"
    if "youtube" in in_url.lower() or "youtu.be" in in_url.lower():
        main_name = "_you"
    elif "pin.it" in in_url.lower() or "pinterest" in in_url.lower():
        main_name = "_pin"
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
    if in_timestamps:
        two_timestamps = get_start_and_end_time(args.time_lapse)
        vid_time = f'_{two_timestamps[0].strftime("%H.%M.%S")}'

    return f"{num}{main_name}{v_id}{vid_time}"


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Downloads video or part of a video using youtube-dl and ffmpeg')
    parser.add_argument('-u', '--url', type=str, help='The video url', metavar='\b', default=URL)
    parser.add_argument('-t', '--time_lapse', help='two timestamps: beginning and ending, accepted format: hh:mm:ss or'
                                                   ' hh.mm.ss', type=str, nargs='+', metavar='\b', default=TIME_LAPSE)
    parser.add_argument('-o', '--output', help='output video path. (without extension)', type=str, metavar='\b',
                        default=OUTPUT)
    parser.add_argument('-v', '--video_only', help='download the video without the audio', type=bool,
                        default=VIDEO_ONLY, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-s', '--audio_only', help='download the audio without the video', type=bool,
                        default=AUDIO_ONLY, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-d', '--debug', help='show debug info about the video URL', type=bool,
                        default=DEBUG, metavar='\b', action=argparse.BooleanOptionalAction)
    parser.add_argument('-a', '--art', help='Display ASCII art', type=bool,
                        default=ART, metavar='\b', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    intro_print(args.art)

    for program in ["ffmpeg", "youtube-dl"]:
        if shutil.which(program) is None:
            print(f"ERROR: '{program}' is not installed, please install it before use")
            quit()

    exec_start_time = datetime.now()
    if args.video_only and args.audio_only:
        print("ERROR: you chose both 'video_only' and 'audio_only' modes, only one can be chosen")
        quit()

    url = args.url
    if len(url) == 0:
        url = get_url_text()
    output_path = args.output
    if output_path == "":
        output_path = get_video_name(url, args.time_lapse)

    if args.debug:
        os.system(f"youtube-dl -F {url}")
    if args.time_lapse != "":
        timestamps = get_start_and_end_time(args.time_lapse)
        print(f"start downloading video: {url}")
        print(f'video timestampss: {timestamps[0].strftime("%H:%M:%S")} -> {timestamps[1].strftime("%H:%M:%S")}\n\n')
        download_partial_video(url, timestamps, output_path, args.debug, args.video_only, args.audio_only)
    else:
        if args.video_only:
            cmd = f"youtube-dl -f 'bestvideo[height<=?1080]/best' --output '{output_path}.%(ext)s' {url}"
        elif args.audio_only:
            cmd = f"youtube-dl -f 'bestaudio/best' --output '{output_path}.%(ext)s' {url}"
        else:
            cmd = f"youtube-dl -f 'bestvideo[height<=?1080]+bestaudio/best' --output '{output_path}.%(ext)s' {url}"

        if args.debug:
            print("exec command: \n")
            print(cmd)
        else:
            os.system(cmd)

    if not args.debug:
        print("")
        print(f"finished downloading video: {url}")
        if args.time_lapse != "":
            timestamps = get_start_and_end_time(args.time_lapse)
            print(f'video timestamps: {timestamps[0].strftime("%H:%M:%S")} -> {timestamps[1].strftime("%H:%M:%S")}')
        print(f'video name: {output_path}')
        print("")
        print(("video download finished. Duration = {} ".format(pretty_time_delta(datetime.now() - exec_start_time))))
        print("")

    end_print(args.art)
