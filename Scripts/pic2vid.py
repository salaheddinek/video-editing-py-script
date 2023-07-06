#!/usr/bin/env python3
__package__ = "pic2vid"
from PIL import Image
import pathlib
from datetime import datetime
import argparse
import os
import tempfile
import shutil


DURATION_SECONDS = 3
CODEC = "h264"
IMG_EXTENSION = ".png"
FPS = 15
FFMPEG_VERBOSE = "quiet"
OUTPUT = f"{__package__}_result"


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


def get_image_size(in_img_paths):
    first_size = (0, 0)
    for idx, img_path in enumerate(in_img_paths):
        progress(idx, len(in_img_paths), "verifying images")
        with Image.open(str(img_path)) as im:
            cur_size = im.size
            if idx == 0:
                first_size = cur_size
            else:
                if first_size != cur_size:
                    raise ValueError(f"\nERROR: not all images have the same size, "
                                     f"{in_img_paths[0].name} -> ({first_size[0]}, {first_size[1]}) , "
                                     f"{img_path.name} -> ({cur_size[0]}, {cur_size[1]})")
    return first_size


def copy_images(in_images, in_new_path):
    for i in range(len(in_images)):
        shutil.copy(str(in_images[i]), str(in_new_path / f"{i:05d}{in_images[i].suffix}"))


def process_tmp_images(in_tmp_path, in_ext, in_fps, int_duration, in_codec, in_num_images, in_output, in_verbose):
    images_speed = (float(in_num_images) / int_duration)
    vid_ext = ".mp4"
    if "png" in in_codec.lower():
        vid_ext = ".mov"
    cmd = f'ffmpeg -y -framerate {images_speed} -i { in_tmp_path / f"%05d{in_ext}"} -hide_banner -loglevel {in_verbose}'
    cmd += f' -vcodec {in_codec} -r {in_fps} {in_output}{vid_ext}'
    # print(cmd)
    print("running the merging command ...")
    os.system(cmd)
    return pathlib.Path(f"{in_output}{vid_ext}")


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
                                     description='Search for images in the current directory and convert them to video,'
                                                 ' all images must have the same dimensions. the number of images shown'
                                                 ' per second is calculated using the provided duration')
    parser.add_argument('-f', '--fps', help='frame per second of the output video', type=int,
                        default=FPS, metavar='\b')
    parser.add_argument('-c', '--codec', help='codec used by ffmpeg, some possible value: h264, png'
                                              '(useful for transparency)', type=str, default=CODEC, metavar='\b')
    parser.add_argument('-d', '--duration', help='the length of the video in seconds', type=int,
                        default=DURATION_SECONDS, metavar='\b')
    parser.add_argument('-e', '--extension', help='image types to be converted',
                        type=str, default=IMG_EXTENSION, metavar='\b')
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: error, warning or info', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-o', '--output', help='output video name/path (without extension)',
                        type=str, default=OUTPUT, metavar='\b')
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    start_time = datetime.now()
    path = pathlib.Path().cwd()

    extension = args.extension
    if not extension.startswith("."):
        extension = "." + extension

    img_names = []
    for im_p in path.glob("*" + extension):
        img_names += [im_p]
    img_names.sort()
    if len(img_names) == 0:
        print("no image of type '{}' have been detected in the current folder '{}'".format(extension, path))
        quit()
    print("")
    print(f" {__package__} ".center(80, "="))
    print("")
    print(f"working directory: {path}")
    print(f"number of '{extension}' images detected: {len(img_names)}")

    size = get_image_size(img_names)
    print(f"detected image size {size}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        copy_images(img_names, tmp_path)

        out_path = process_tmp_images(tmp_path, extension, args.fps, args.duration, args.codec,
                                      len(img_names), args.output, args.verbose)
        if out_path.is_file():
            print(f"merging images successful, output video path: {out_path}")
        else:
            print(f"ERROR: could not merge images into video: {out_path}")

    end_time = datetime.now()
    print("")
    print((" Converting finished. Duration = {} ".format(pretty_time_delta(end_time - start_time)).center(80, "=")))
    print("")
