#!/usr/bin/env python3
__package__ = "vid2gif"

import os
from datetime import datetime
import time
import argparse
import pathlib
import shutil
import subprocess


INPUT = []
VIDEO_FORMAT = ".mp4"
FPS = 15
GIF_WIDTH = 500
SHOW_FFMPEG_VERBOSE = False
MODE = "sierra2"  #
MODES_NAMES = ["direct", "bayer", "sierra2", "sierra2_4a", "new", "magick", "magick_optimize"]
ART = True


MODES_HELP = """

The methods used for converting videos to GIFs are presented bellow (all of these need ffmpeg to be installed):

 * direct: uses ffmpeg directly without any optimization (lowest quality, smallest file size).
 
 * bayer: uses ffmpeg paletteuse optimization method using 'bayer' algorithm. 
 
 * sierra2: uses ffmpeg paletteuse optimization method using 'sierra2' algorithm. 
  
 * sierra2_4a: uses ffmpeg paletteuse optimization method using 'sierra2_4a' algorithm.
 
 * new: uses ffmpeg paletteuse optimization method by calculating a palette for each frame (good quality, but big 
 file size)
 
 * magick: uses ffmpeg with ImageMagick convert method.
 
 * magick_optimize: same as previous but with color optimization (slightly less quality and file size)
 
 * all: produce a GIF with each method presented here 
"""


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = """
        Yb    dP 88 8888b.      oP"Yb.      dP""b8 88 888888 
         Yb  dP  88  8I  Yb     "' dP'     dP   `" 88 88__   
          YbdP   88  8I  dY       dP'      Yb  "88 88 88""   
           YP    88 8888Y"      .d8888      YboodP 88 88    
    """
    if in_art:
        print(intro)
    print((" starting converting video(s) ".center(80, "=")))
    print("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.            
    ______     d88ooo  888_dPY8   88   8     ______ 
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX 
             88bdPPP   Y8P   Y8   88oop'               
    """
    print((" Vid2gif finished ".center(80, "=")))
    if in_art:
        print(end)


def parse_input_files(in_args, in_ext):
    res = []
    if len(in_args.input) == 0:
        for pp in pathlib.Path().cwd().glob("*" + in_ext):
            res += [pp]
    else:
        for p_str in in_args.input:
            res += [pathlib.Path(p_str)]
    return sorted(res)


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


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def check_if_image_magick_installed():
    if shutil.which("convert") is None:
        return False
    res1 = subprocess.run(["convert", "--version"], stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1].lower()
    if "imagemagick" in res1 or "image magick" in res1:
        return True
    return False


def convert_video(i_in_path, i_out_path, i_fps, i_width, i_verbose, i_mode):
    if not i_in_path:
        return 0, 0, f"could not found: {i_in_path}"
    init_size = i_in_path.stat().st_size
    choice = MODES_NAMES[i_mode]
    verbose_cmd = "-hide_banner -loglevel info "
    if not i_verbose:
        verbose_cmd = "-loglevel quiet"
    fps_cmd = f"fps={i_fps}"
    scale_cmd = f'scale={i_width}:{i_width}:force_original_aspect_ratio=increase:flags=lanczos'
    out_gif = i_out_path / f"{i_in_path.stem}_{choice}.gif"
    if "magick" in choice:
        if not check_if_image_magick_installed():
            return init_size, 0, "'ImageMagick' in not installed, this mode could not be used"
    if choice == "direct":
        flt = f'"{fps_cmd},{scale_cmd}"'
    elif choice == "new":
        flt = f'"[0:v] {fps_cmd},{scale_cmd},split [a][b];[a] palettegen=stats_mode=single [p];[b][p] paletteuse=new=1"'
    elif choice == "magick":
        flt = f'"{fps_cmd},{scale_cmd}" -f image2pipe -vcodec ppm - | convert -delay {round(100 / i_fps)} -loop 0 - '
    elif choice == "magick_optimize":
        flt = f'"{fps_cmd},{scale_cmd}" -f image2pipe -vcodec ppm - |' \
              f' convert -delay {round(100 / i_fps)} -loop 0 -layers Optimize - '
    else:
        flt = f'"[0:v] {fps_cmd},{scale_cmd},split [a][b];[a] palettegen [p];[b][p] paletteuse=dither={choice}"'

    cmd = f'ffmpeg -i "{i_in_path}" {verbose_cmd} -y -filter_complex {flt} "{out_gif}"'
    if i_verbose:
        print("command line:\n\n" + cmd + "\n\n")
    os.system(cmd)
    if not out_gif.is_file():
        return init_size, 0, "ffmpeg failed to produce GIF file (using '-v' may help debugging)"
    return init_size, out_gif.stat().st_size, ""


def get_mode_index(in_mode):
    if 'help' == in_mode.lower().strip():
        print(MODES_HELP)
        quit()
    if 'all' == in_mode.lower().strip():
        return 100, 'all methods'
    for m_idx, m in enumerate(MODES_NAMES):
        if m == in_mode.lower().strip():
            return m_idx, m
    print(f"WARNING: mode '{in_mode}' is not recognized, '{MODE}' is used instead")
    for m_idx, m in enumerate(MODES_NAMES):
        if m == MODE:
            return m_idx, MODE
    return 100, MODE


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
    modes_print = "'" + "', '".join(MODES_NAMES + ['all']) + "'"
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Converts videos to GIFs. Multiple optimization option are provided')
    parser.add_argument('-i', '--input', help='input video files, if not specified then all files are processed',
                        type=str, nargs='+', metavar='\b', default=INPUT)
    parser.add_argument('-f', '--fps', help='frame per second of the output GIFs', type=int,
                        default=FPS, metavar='\b')
    parser.add_argument('-s', '--size', help='size of the smallest side of the resulting gif ( = min(height, width) )',
                        type=int, default=GIF_WIDTH, metavar='\b')
    parser.add_argument('-m', '--mode', help=f"gif conversion methods: {modes_print} ('--mode help' for more info)",
                        type=str, default=MODE, metavar='\b')
    parser.add_argument('-t', '--video_type', help="type of videos that will be processed (if no input is provided)",
                        type=str, default=VIDEO_FORMAT, metavar='\b')
    parser.add_argument('-v', '--ffmpeg_verbose', help="if True then show ffmpeg full verbose", type=str2bool,
                        default=SHOW_FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-a', '--art', help='Display ASCII art', type=str2bool, default=ART, metavar='\b')
    args = parser.parse_args()
    mode_idx, mode_print = get_mode_index(args.mode)

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    intro_print(args.art)

    path = pathlib.Path().cwd()
    output_path = path / f"{__package__}_f{args.fps}_w{args.size}"
    if not output_path.is_dir():
        output_path.mkdir()

    start_time = datetime.now()
    extension = args.video_type
    if not extension.startswith("."):
        extension = "." + extension
    video_paths = parse_input_files(args, extension)

    print(f"Converting {len(video_paths)} video of '{args.video_type}' type to GIFs")
    print(f"Parameters: FPS: {args.fps}, gif_size: {args.size}, optimization_mode: {mode_print}\n")

    # print
    vid_modes = []
    if mode_idx == 100:
        for p in video_paths:
            for j, mode in enumerate(MODES_NAMES):
                vid_modes += [(p, j)]
    else:
        for p in video_paths:
            vid_modes += [(p, mode_idx)]

    total_before, total_after = 0, 0
    for i, vid_mode in enumerate(vid_modes):
        s_idx = f'{i + 1:^3d}/{len(vid_modes):^3d}'
        if args.ffmpeg_verbose:
            msg = f" {s_idx} => Converting video: {vid_mode[0].name} , mode [{MODES_NAMES[vid_mode[1]]}] ..."
            print("")
            print("".center(80, "="))
            print(msg.center(80, "="))
            print("".center(80, "="))
            print("")
            time.sleep(0.05)
        b, a, err = convert_video(vid_mode[0], output_path, args.fps, args.size, args.ffmpeg_verbose, vid_mode[1])
        total_before += b
        total_after += a
        if err != "":
            print(f" {s_idx} => mode:[{MODES_NAMES[vid_mode[1]].center(15, '_')}]: ERROR: {err}")
        else:
            print(f" {s_idx} => mode:[{MODES_NAMES[vid_mode[1]].center(15, '_')}]: {vid_mode[0].name}, "
                  f"finished: vid={sizeof_fmt(b)} -> gif={sizeof_fmt(a)}")

    if len(video_paths) != 1:
        print("")
        print(f"conversion   total size: before = {sizeof_fmt(total_before)} -> after = {sizeof_fmt(total_after)}")

    end_time = datetime.now()
    print("")
    print((f" Converting finished. Duration = {pretty_time_delta(end_time - start_time)} ".center(80, "=")))
    print("")
    end_print(args.art)
