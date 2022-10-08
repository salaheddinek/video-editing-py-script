#!/usr/bin/python3
import os
import tempfile
import shutil
import pathlib
import argparse
from datetime import datetime
from colorama import Fore, Style


ART = True
FFMPEG_VERBOSE = "quiet"
STACK_TOP = 1
STACK_RIGHT = 1
STACK_BOTTOM = 1
STACK_LEFT = 1


def intro_print():
    """ Taken from https://patorjk.com/software/taag using 4MAX font"""
    intro = """
    Yb    dP            db    88""Yb 88""Yb    db    Yb  dP .dP"Y8 
     Yb  dP            dPYb   88__dP 88__dP   dPYb    YbdP  `Ybo." 
      YbdP   .o.      dP__Yb  88"Yb  88"Yb   dP__Yb    8P   o.`Y8b         
       YP    `"'     dP\"\"\"\"Yb 88  Yb 88  Yb dP\"\"\"\"Yb  dP    8bodP'  
    """

    lines = intro.split("\n")
    mid_p = 18
    for line in lines:
        print(f"{Fore.RED}{line[3:mid_p]}{Fore.LIGHTYELLOW_EX}{line[mid_p+2:]}{Style.RESET_ALL}")


def end_print():
    end = """
               ,d8PPPP 888  ,d8   88PPP.            
    ______     d88ooo  888_dPY8   88   8     ______ 
    XXXXXX   ,88'      8888' 88   88   8     XXXXXX 
             88bdPPP   Y8P   Y8   88oop'               
    """
    lines = end.split("\n")
    p1, p2 = 10, 45
    for line in lines:
        print(f"{' ' * 10}{Fore.MAGENTA}{line[3:p1]}{Fore.CYAN}{line[p1:p2]}"
              f"{Fore.MAGENTA} {line[p2:]}{Style.RESET_ALL}")


def construct_video_array_line(raw_vid, in_right, in_left, in_tmp_dir, in_line_output, in_verbose):
    extension = pathlib.Path(raw_vid).suffix
    h_vid = os.path.join(in_tmp_dir, f"h_vid{extension}")
    cmd_h_flip = f"ffmpeg -i \"{raw_vid}\" -vf hflip -c:a copy -loglevel {in_verbose} \"{h_vid}\""
    # print(cmd_h_flip)
    os.system(cmd_h_flip)
    print("finished creating horizontally  flipped video")
    suffix = "[0:v]"
    for i in range(in_left):
        suffix = f"[{(i + 1) % 2}:v]" + suffix
    for i in range(in_right):
        suffix = suffix + f"[{(i + 1) % 2}:v]"

    
    cmd_h_stack = f"ffmpeg -y -i \"{raw_vid}\" -i \"{h_vid}\"  -loglevel {in_verbose}  -filter_complex" \
                  f" \"{suffix}hstack=inputs={1 + in_left + in_right}[v]\" -map \"[v]\" -map 0:a \"{in_line_output}\""
    # print(cmd_h_stack)
    os.system(cmd_h_stack)
    if not pathlib.Path(in_line_output).is_file():
        os.system(cmd_h_stack.replace("-map 0:a", "", 1))
    print("finished appending videos horizontally")


def construct_video_array_column(in_line_vid_path, in_top, in_bottom, in_tmp_dir, in_output,  in_verbose):
    extension = pathlib.Path(in_line_vid_path).suffix
    v_vid = os.path.join(in_tmp_dir, f"v_vid{extension}")
    cmd_v_flip = f"ffmpeg -i \"{in_line_vid_path}\" -vf vflip -c:a copy -loglevel {in_verbose} \"{v_vid}\""
    os.system(cmd_v_flip)
    print("finished creating vertically flipped video")
    suffix = "[0:v]"
    for i in range(in_top):
        suffix = f"[{(i + 1) % 2}:v]" + suffix
    for i in range(in_bottom):
        suffix = suffix + f"[{(i + 1) % 2}:v]"

    cmd_v_stack = f"ffmpeg -y -i \"{in_line_vid_path}\" -i \"{v_vid}\"  -loglevel {in_verbose}  -filter_complex" \
                  f" \"{suffix}vstack=inputs={1 + in_top + in_bottom}[v]\" -map \"[v]\" -map 0:a \"{in_output}\""
    # print(cmd_v_stack)
    os.system(cmd_v_stack)
    if not pathlib.Path(in_output).is_file():
        os.system(cmd_v_stack.replace("-map 0:a", "", 1))
    print("finished appending videos vertically")


def set_up_output_path(input_path, output_path, extension):
    if output_path == "":
        return input_path + "_result" + extension

    if pathlib.Path(output_path).stem == "*":
        return os.path.join(pathlib.Path(output_path).parent, pathlib.Path(input_path).name + extension)

    if pathlib.Path(output_path).suffix == "":
        return output_path + extension

    return output_path


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


if __name__ == '__main__':
    # use case: mv in.mp4 p.mp4; mirror_vids.py -i p.mp4 -e1 -o expanded/1
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Create array of video, could be horizontally or vertically or both, '
                                                 'stacked videos are flipped. '
                                                 'Useful to perform video transition animation')
    parser.add_argument('-i', '--input', help='input video', type=str, metavar='\b', required=True)
    parser.add_argument('-v', '--verbose', help='ffmpeg verbose level: error, warning or info', type=str,
                        default=FFMPEG_VERBOSE, metavar='\b')
    parser.add_argument('-t', '--top', help='number of videos to stack on top',
                        type=int, default=STACK_TOP, metavar='\b')
    parser.add_argument('-r', '--right', help='number of videos to stack to the right',
                        type=int, default=STACK_RIGHT, metavar='\b')
    parser.add_argument('-b', '--bottom', help='number of videos to stack to the bottom',
                        type=int, default=STACK_BOTTOM, metavar='\b')
    parser.add_argument('-l', '--left', help='number of videos to stack to the left',
                        type=int, default=STACK_LEFT, metavar='\b')
    parser.add_argument('-e', '--expand', help='If different to zero, then expand in all direction with the specified '
                                               'value', type=int, default=0, metavar='\b')
    parser.add_argument('-o', '--output', help='output video path. If not provided, then it would be created next to '
                                               'the input video',  type=str, metavar='\b', default="")
    parser.add_argument('-a', '--art', help='Display ASCII art', type=bool,
                        default=ART, metavar='\b', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: 'ffmpeg' is not installed, please install it before use")
        quit()

    input_vid = args.input
    in_path, ext = os.path.splitext(input_vid)
    output_vid = set_up_output_path(in_path, args.output, ext)

    verbose = args.verbose
    top = args.top
    right = args.right
    bottom = args.bottom
    left = args.left
    if args.expand != 0:
        top, right, left, bottom = args.expand, args.expand, args.expand, args.expand

    start_time = datetime.now()

    if args.art:
        intro_print()
        # end_print()
        # quit()
    else:
        print((" starting video arrays processing ".center(80, "=")))

    if top == 0 and right == 0 and bottom == 0 and left == 0:
        exit(0)

    with tempfile.TemporaryDirectory() as tmp_dir:

        if top != 0 or bottom != 0:
            transition_vid = os.path.join(tmp_dir, f"h_line_vid{ext}")
        else:
            transition_vid = output_vid

        if right != 0 or left != 0:
            construct_video_array_line(input_vid, right, left, tmp_dir, transition_vid, verbose)
        else:
            transition_vid = input_vid

        if top != 0 or bottom != 0:
            construct_video_array_column(transition_vid, top, bottom, tmp_dir, output_vid, verbose)

    end_time = datetime.now()
    print("")
    print(("video array creation finished. Duration = {} ".format(pretty_time_delta(end_time - start_time))))
    print("")

    if args.art:
        end_print()
