#!/usr/bin/env python3
__package__ = "vid_compress"
from datetime import datetime
import shutil
import argparse
import os
import pathlib


INPUT = []
FFMPEG_CODEC = "h264"  # more info in CODEC_HELP_MSG
VID_EXTENSION = ".mp4"
SCALE = -1
FFMPEG_VERBOSE = "quiet"
FPS = -1
KEEP_ORIGINAL = False
ART = True
REMOVE_AUDIO = False
REMOVE_VIDEO = False


CODEC_HELP_MSG = """
Codecs are responsible for compressing and decompressing video when it is created and played back,
They are different from video containers (file types like: .mp4, .webm, etc),
in general multiple a codec can be used in multiple containers.

Not every device can view every codec, and quality can vary depending on the codec,
Here is a list of famous codecs that can be used with this program:

 * h264: codec name 'AVC(H.264)'. The most famous. Supported by all devices and browsers. Must pay royalty if you \
sell your videos  (Container support: .mp4, .mov, .avi, .mkv) 

 * libx265: codec name 'HEVC(H.265)', Better compression compared to H.264 but slower to encode. Supported by all \
browsers a PCs but not all phones. Must pay royalty if you sell your videos  (Container support: .mp4, .mov, .avi, .mkv) 

 * vp8: codec name 'VP8'. Developed by google. Similar to H.264 in terms of file size and computational time. \
Supported but all browser and most devices. Royalty free. (Container support: .webm) 

 * vp9: codec name 'VP9'. Also developed by google. Similar to H.265 in terms of file size and computational time.\
60% of the file size of H.264 but 50% more compression time. Supported by all browsers and most devices. Royalty free.
(Container support: .mp4, .webm) 

 * av1: codec name 'AV1', The most efficient in term of file size, but the longest for computational time. \
Amazon, Netflix, Google, Microsoft, Cisco, and Mozilla formed the Alliance (2020) for Open Media to create this \
open-source and royalty-free alternative. Adoption is coming slowly, and may make it faster to encode videos using it.

 * copy: just copies the original video codec.

More info can be found here: https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Video_codecs.
More codecs can be found by executing 'ffmpeg -encoders' command line.
"""


def intro_print(in_art):
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = """
    Yb    dP          dP""b8  dP"Yb  8b    d8 88""Yb 88""Yb 888888 .dP"Y8 .dP"Y8 
     Yb  dP          dP   `" dP   Yb 88b  d88 88__dP 88__dP 88__   `Ybo." `Ybo." 
      YbdP   .o.     Yb      Yb   dP 88YbdP88 88\"""  88"Yb  88""   o.`Y8b o.`Y8b 
       YP    `"'      YboodP  YbodP  88 YY 88 88     88  Yb 888888 8bodP' 8bodP' 
    """
    if in_art:
        print(intro)
    print((" starting compressing video(s) ".center(80, "=")))
    print("")


def end_print(in_art):
    end = """
               ,d8PPPP 888  ,d8   88PPP.            
    ______     d88ooo  888_dPY8   88   8     ______ 
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX 
             88bdPPP   Y8P   Y8   88oop'               
    """
    print((" Compressing finished ".center(80, "=")))
    if in_art:
        print(end)


def create_folder(in_path):
    if not in_path.is_dir():
        in_path.mkdir()
        if not in_path.is_dir():
            print(f"ERROR: could not create output folder: '{in_path}'")
            quit()


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


def print_info(in_args, in_ext):
    printed_scale = f"{in_args.scale}p"
    if in_args.scale <= 0:
        printed_scale = "original_scale"

    printed_fps = f'{in_args.fps}'
    if in_args.fps <= 0:
        printed_fps = "original_fps"

    print(f"Parameters:  "
          f"\n * fps:{printed_fps} , scale:{printed_scale}, codec:{in_args.codec} , verbose:{in_args.verbose}"
          f"\n * extension:{in_ext} , keep_originals:{in_args.keep} , remove_audio:{in_args.rm_audio}, "
          f"remove_video:{in_args.rm_video}")
    print("")


def parse_input_files(in_args, in_ext):
    res = []
    if len(in_args.input) == 0:
        for pp in pathlib.Path().cwd().glob("*" + in_ext):
            res += [pp]
    else:
        for p_str in in_args.input:
            res += [pathlib.Path(p_str)]
    if len(res) == 0:
        print(f"ERROR: no video of type '{in_ext}' have been detected in current dir: {pathlib.Path().cwd()}")
        quit()
    return sorted(res)


def compress_one_video(in_input, in_output, in_fps, in_scale, in_verbose, in_codec, in_rm_v, in_rm_a):
    scale_cmd = f'-vf "scale={in_scale}:{in_scale}:force_original_aspect_ratio=increase"'
    codec_cmd = f'-c:v {in_codec}'
    fps_cmd = f'-crf {in_fps}'
    list_of_containers = [".mp4", ".webm", ".mkv", ".mov", ".avi"]
    if in_scale <= 0:
        scale_cmd = ""
    rm_cmd = ""
    if in_rm_a:
        rm_cmd = "-an"
    if in_rm_v:
        rm_cmd = "-vn -c:a libmp3lame"
        list_of_containers = [".mp3", ".m4a", ".wav"]
        scale_cmd, codec_cmd, fps_cmd = "", "", ""
    if in_fps <= 0:
        fps_cmd = ""
    out_size = 0

    for cnt in list_of_containers:
        out_vid = in_output / (vid_path.stem + cnt)
        cmd = f'ffmpeg -i "{in_input}" {scale_cmd} {codec_cmd} -hide_banner ' \
              f'-loglevel {in_verbose} {fps_cmd} {rm_cmd} -y "{out_vid}"'
        # print(cmd + "\n\n")
        os.system(cmd)
        out_size = out_vid.stat().st_size
        if out_size > 10:
            break
        else:
            out_vid.unlink()

    return in_input.stat().st_size, out_size


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
                                     description='Compresses videos using ffmpeg, also provides multiple options '
                                                 'in order change the resulting videos like dimension change or '
                                                 'sound removal.')
    parser.add_argument('-i', '--input', help='input video(s), if unspecified then all video in current directory '
                                              'are processed', type=str,  nargs='+', metavar='\b', default=INPUT)
    parser.add_argument('-f', '--fps', help='frame per second of the output video (if negative then keep original)',
                        type=int, default=FPS, metavar='\b')
    parser.add_argument('-s', '--scale', help='scale of the result videos, if negative then keep original size',
                        type=int, default=SCALE, metavar='\b')
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: "error", "warning" or "info"', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-e', '--extension', help='video types to be converted (if input is not specified)',
                        type=str, default=VID_EXTENSION, metavar='\b')
    parser.add_argument('-c', '--codec', help='codec used by ffmpeg, some possible value: h264, vp9, etc '
                                              '(type "--codec help" for more info)',
                        type=str, default=FFMPEG_CODEC, metavar='\b')
    parser.add_argument('-a', '--art', help='Display ASCII art', type=str2bool,  default=ART, metavar='\b')
    parser.add_argument('-k', '--keep', help='keep original videos', type=str2bool, default=KEEP_ORIGINAL, metavar='\b')
    parser.add_argument('-r', '--rm_video', help='remove the video stream and only keep audio', type=str2bool,
                        default=REMOVE_VIDEO, metavar='\b')
    parser.add_argument('-d', '--rm_audio', help='remove the audio and only keep video', type=str2bool,
                        default=REMOVE_AUDIO, metavar='\b')

    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    start_time = datetime.now()

    if "help" in args.codec.lower():
        print(CODEC_HELP_MSG)
        quit()

    if args.rm_video and args.rm_audio:
        print("ERROR: you chose to remove both audio and video, only one can be chosen (--help)")
        quit()

    extension = args.extension
    if not extension.startswith("."):
        extension = "." + extension

    intro_print(args.art)

    print_info(args, extension)

    path = pathlib.Path().cwd()
    vid_paths = parse_input_files(args, extension)

    # create output folder
    output_path = pathlib.Path(path) / f"{__package__}_results"
    create_folder(output_path)
    backup_path = output_path / "initial_videos"
    if not args.keep:
        create_folder(backup_path)

    # start loop
    total_before, total_after = 0, 0
    for i, vid_path in enumerate(vid_paths):
        s_idx = f'{i + 1:^3d}/{len(vid_paths):^3d}'
        if not vid_path.is_file():
            print(f" {s_idx} =>  ERROR: file not found: {vid_path}")
            continue
        b, a = compress_one_video(vid_path, output_path, args.fps, args.scale, args.verbose,
                                  args.codec, args.rm_video, args.rm_audio)
        total_before += b
        total_after += a
        if a == 0:
            print(f"f {s_idx} => {vid_path.name}: ERROR: ffmpeg failed (run '-v info' for debugging)")
        else:
            print(f" {s_idx} => {vid_path.name}, finished:  before={sizeof_fmt(b)} -> after={sizeof_fmt(a)}"
                  f" ({(b - a) * 100 / b :.0f}% efficiency)")
        if not args.keep:
            os.rename(str(vid_path), str(backup_path / vid_path.name))

    end_time = datetime.now()

    if len(vid_paths) != 1:
        print("")
        print(f"compression: total size before: {sizeof_fmt(total_before)} -> after: {sizeof_fmt(total_after)} "
              f"({(total_before - total_after) * 100 / total_before :.0f}% efficiency)")
    print("")
    print((f" Compressing finished. Duration = {pretty_time_delta(end_time - start_time)} ".center(80, "=")))
    print("")

    end_print(args.art)
