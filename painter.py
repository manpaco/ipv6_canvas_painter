#!/usr/bin/env python3

import os
import re
import sys
import math
import time
import argparse
import platform
import concurrent.futures
from PIL import Image
from PIL import ImageColor

# Version
VERSION = '0.1.0'

# VPS IPv6 address (first 64 bits)
# Example: 2602:f75c:c0::XXXX:YYYY:RRGG:BBAA
# canvas.openbased.com
BASE_ADDR = '2602:f75c:c0::'
DUMMY_ADDR = 'ffff:ffff:ffff:ffff'
IPV6_ADDR_REGEX = (r'^('
                   # 1:2:3:4:5:6:7:8
                   r'([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|'
                   # 1::                              1:2:3:4:5:6:7::
                   r'([0-9a-fA-F]{1,4}:){1,7}:|'
                   # 1::8             1:2:3:4:5:6::8  1:2:3:4:5:6::8
                   r'([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|'
                   # 1::7:8           1:2:3:4:5::7:8  1:2:3:4:5::8
                   r'([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|'
                   # 1::6:7:8         1:2:3:4::6:7:8  1:2:3:4::8
                   r'([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|'
                   # 1::5:6:7:8       1:2:3::5:6:7:8  1:2:3::8
                   r'([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|'
                   # 1::4:5:6:7:8     1:2::4:5:6:7:8  1:2::8
                   r'([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|'
                   # 1::3:4:5:6:7:8   1::3:4:5:6:7:8  1::8
                   r'[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|'
                   # ::2:3:4:5:6:7:8  ::2:3:4:5:6:7:8 ::8       ::
                   r':((:[0-9a-fA-F]{1,4}){1,7}|:)|'
                   # fe80::7:8%eth0   fe80::7:8%1
                   # (link-local IPv6 addresses with zone index)
                   r'fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|'
                   r'::(ffff(:0{1,4}){0,1}:){0,1}'
                   r'((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}'
                   # ::255.255.255.255   ::ffff:255.255.255.255
                   # ::ffff:0:255.255.255.255
                   # (IPv4-mapped IPv6 addresses and IPv4-translated addresses)
                   r'(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|'
                   r'([0-9a-fA-F]{1,4}:){1,4}:'
                   r'((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}'
                   # 2001:db8:3:4::192.0.2.33  64:ff9b::192.0.2.33
                   # (IPv4-Embedded IPv6 Address)
                   r'(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])'
                   r')$')
DELAY = 0.2
MAX_WORKERS = 3

# Canvas constants
MAGIC_NUMBER = 8
UNDEFINED = -1
ORIGIN = 0
MAX = 0x10000
MIN_SIZE = 1
MAX_SIZE = round(MAX / MAGIC_NUMBER)
DEFAULT_TYPE_REGEX = '^[dD]{1}$'
CENTER_TYPE_REGEX = '^[cC]{1}$'
DEFAULT_TYPE = 'D'
CENTER_TYPE = 'C'
NUMBER_REGEX = '^[0-9]+$'

# Colors constants
# RRGGBBAA regex with optional alpha channel
COLOR_REGEX = r'^([0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?)$'
MAX_COLOR = 0xFF
BMP_MODE = 'RGBA'

# Ping command
if platform.system() == 'Windows':
    PING = 'ping /6 /n 1'
else:
    PING = 'ping -6 -c 1'

# Output redirection
if platform.system() == 'Windows':
    REDIRECTION = ' > NUL'
else:
    REDIRECTION = ' > /dev/null'


# Canvas class to store: base_addr and execution options
class Canvas:
    def __init__(self, base_addr, verbose, dry_run):
        if not re.match(IPV6_ADDR_REGEX, base_addr + DUMMY_ADDR):
            print('Error: the BASE_ADDR is not valid')
            sys.exit(1)
        self.base_addr = base_addr
        self.verbose = verbose
        self.dry_run = dry_run

    def paint_pixel(self, x, y,
                    r=MAX_COLOR, g=MAX_COLOR, b=MAX_COLOR, a=MAX_COLOR):
        address = f'{self.base_addr}{x:04x}:{y:04x}:' \
                  f'{r:02x}{g:02x}:{b:02x}{a:02x}'
        command = f'{PING} {address}{REDIRECTION}'
        if self.verbose:
            print(command)
        if not self.dry_run:
            os.system(command)


# Element class to store: source, width, and height
class Element:
    def __init__(self, source):
        self.source = source
        self.width = 0
        self.height = 0

    # To override
    def get_pixel(self, x, y):
        pass

    def get_size(self):
        return self.width, self.height

    # Set element size:
    # - If width and height are != UNDEFINED --> use both values without using
    # aspect ratio
    # - If ONE of them is != UNDEFINED --> use aspect ratio to calculate the
    # other one
    # Before run verifications
    def set_size(self, width, height):
        use_width = False
        use_height = False
        has_zeros = self.width == 0 or self.height == 0
        if width != UNDEFINED:
            if width < MIN_SIZE:
                print('Error: WIDTH must be greater than or equal to '
                      f'{MIN_SIZE}')
                sys.exit(1)
            if width > MAX_SIZE:
                print(f'Error: WIDTH must be less than or equal to {MAX_SIZE}')
                sys.exit(1)
            use_width = True
        if height != UNDEFINED:
            if height < MIN_SIZE:
                print('Error: HEIGHT must be greater than or equal to '
                      f'{MIN_SIZE}')
                sys.exit(1)
            if height > MAX_SIZE:
                print('Error: HEIGHT must be less than or equal '
                      f'to {MAX_SIZE}')
                sys.exit(1)
            use_height = True

        if use_width and use_height:
            self.width = width
            self.height = height
            return
        if use_width and self.width != width and not has_zeros:
            aspect_ratio = self.width / self.height
            self.height = round(width / aspect_ratio)
            self.width = width
            return
        if use_height and self.height != height and not has_zeros:
            aspect_ratio = self.height / self.width
            self.width = round(height / aspect_ratio)
            self.height = height
            return

    def pixels(self):
        return self.width * self.height

    def valid_pixel(self, x, y):
        return x >= 0 and x < self.width and y >= 0 and y < self.height

    def __str__(self):
        return f'{self.source} {self.width}x{self.height} with ' \
               f'{self.pixels()} pixels'


# Bitmap class to store: image
class Bitmap(Element):
    def __init__(self, source):
        super().__init__(source)
        try:
            self.img = Image.open(source)
        except FileNotFoundError:
            print(f'Error: {source} not found')
            self.img = None
            sys.exit(1)
        self.img = self.img.convert(BMP_MODE)
        # Initializing element size (do not use self.set_size... nor
        # super().set_size...)
        self.width, self.height = self.img.size
        self.assert_size(True)

    def get_pixel(self, x, y):
        if not self.valid_pixel(x, y):
            raise ValueError('not a valid image pixel', f'{x}', f'{y}')
        return self.img.getpixel((x, y))

    # Set bitmap size using the parent method and then resize the actual image
    # with the calculated values
    def set_size(self, width, height):
        super().set_size(width, height)
        self.assert_size()
        self.img = self.img.resize((self.width, self.height))

    # Ensure that parameters are valid
    def assert_size(self, init=False):
        if init:
            more_str = ' (opening)'
        else:
            more_str = ' (resizing)'
        if self.width < MIN_SIZE or self.height < MIN_SIZE:
            print(f'Error: the image must have at least {MIN_SIZE} width and '
                  f'height pixels{more_str}')
            sys.exit(1)
        if self.width > MAX_SIZE or self.height > MAX_SIZE:
            print('Error: the image size must be less than or equal to '
                  f'{MAX_SIZE}x{MAX_SIZE}{more_str}')
            sys.exit(1)

    def __str__(self):
        return 'Image: ' + super().__str__()

    def __del__(self):
        if self.img is not None:
            self.img.close()


# Filling class to store: filling color
class Filling(Element):
    def __init__(self, source, width, height):
        super().__init__(source)
        self.set_color(source)
        self.set_size(width, height)

    def get_pixel(self, x, y):
        if not self.valid_pixel(x, y):
            raise ValueError('not a valid filling pixel', f'{x}', f'{y}')
        return self.color

    def set_color(self, color):
        if not re.match(COLOR_REGEX, color):
            print('Error: invalid color format')
            sys.exit(1)
        self.color = ImageColor.getrgb(f'#{color}')
        # If the color has no alpha channel then add an extra value
        if len(self.color) < 4:
            self.color += (MAX_COLOR,)

    def __str__(self):
        return 'Filling: #' + super().__str__()


def exceeds_values(x, y, width, height):
    return (x < ORIGIN, y < ORIGIN, x + width > MAX, y + height > MAX)


def exceeds(x, y, width, height):
    vx, vy, vw, vh = exceeds_values(x, y, width, height)
    return vx or vy or vw or vh


# --------------------------------- ARGUMENTS ---------------------------------

# Parse arguments
parser = argparse.ArgumentParser(description='Paint on a canvas by sending '
                                 'ICMP packets (AKA pings) to an IPv6 '
                                 'address.',
                                 epilog='IMPORTANT: '
                                 'When using --width and --height, or '
                                 '--x2 and --y2 options you can specify one '
                                 'of them and leave the script to calculate '
                                 'the other one using the image aspect ratio. '
                                 'If you specify both, the image will be '
                                 'resized without keeping the aspect ratio.'
                                 )
parser.add_argument('source', metavar='image|color',
                    help='the image or color to paint. Use the --fill option '
                    'to fill with a color, but if you don\'t use that option '
                    'the argument must be an image file. The color must be in '
                    'hexadecimal format; alpha channel is optional. '
                    'color_format: RRGGBB[AA] (str)')
parser.add_argument('-c', '--coordinates', default=None,
                    help='read canvas coordinates from a file: with X, Y, and '
                    'optional TYPE to indicate coordinates type. '
                    f'TYPE values to use: {DEFAULT_TYPE} (default, like -x '
                    f'and -y) or {CENTER_TYPE} (center, like --cx and --cy). '
                    'content_format: X,Y[,TYPE]', metavar='FILE')
parser.add_argument('-x', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to start painting. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('-y', type=int, default=UNDEFINED,
                    help='similat to -x. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--cx', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to place the center. '
                    f' default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--cy', type=int, default=UNDEFINED,
                    help='similar to --cx.'
                    f' default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--x2', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to stop painting. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--y2', type=int, default=UNDEFINED,
                    help='similar to --x2. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--width', type=int, default=UNDEFINED,
                    help='the width of the area to paint. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--height', type=int, default=UNDEFINED,
                    help='similar to --width. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('-d', '--delay', type=float, default=DELAY,
                    help='the delay between each pixel in seconds. '
                    f'default: {DELAY} (float)')
parser.add_argument('-b', '--base-addr', default=BASE_ADDR,
                    help=f'the first 64 bits of the IPv6 address with '
                    'trailing colon (:) '
                    f'default: {BASE_ADDR} (str)')
parser.add_argument('-f', '--fill', action='store_true',
                    help='use the specified color to fill the area, instead '
                    'of painting an image.')
parser.add_argument('-r', '--reverse', action='store_true',
                    help='paint the area in reverse order')
parser.add_argument('-s', '--skip-transparent', action='store_true',
                    help='skip completely transparent pixels')
parser.add_argument('-m', '--multithreading', action='store_true',
                    help='use multithreading to paint the canvas '
                    f'(MAX_WORKERS={MAX_WORKERS})')
parser.add_argument('--overflow', action='store_true',
                    help='the area will be cropped if it exceeds the '
                    'boundaries')
parser.add_argument('--push', action='store_true',
                    help='the area will be pushed into the canvas if it '
                    'exceeds the boundaries')
parser.add_argument('--dry-run', action='store_true',
                    help='run but don\'t send ICMP packets, '
                    'useful for testing')
parser.add_argument('--verbose', action='store_true',
                    help='print the ping command before executing')
parser.add_argument('--version', action='version',
                    version=f'%(prog)s v{VERSION}')
args = parser.parse_args()

# Verify coordinates file
if args.coordinates:
    if (args.x != UNDEFINED or args.y != UNDEFINED
            or args.cx != UNDEFINED or args.cy != UNDEFINED):
        print('Error: the --coordinates option can\'t be used together with '
              '-x, -y, --cx, nor --cy options')
        sys.exit(1)
    file = open(args.coordinates)
    tmp_x = None
    tmp_y = None
    tmp_type = None
    try:
        tmp_x, tmp_y, tmp_type = map(str, file.readline().split(','))
        new_try = False
    except FileNotFoundError:
        print(f'Error: {args.coordinates} not found')
        sys.exit(1)
    except ValueError:
        file.seek(0)
        try:
            tmp_x, tmp_y = map(str, file.readline().split(','))
        except ValueError:
            print(f'Error: {args.coordinates} must contain 2 or 3 values '
                  'separated by commas')
            sys.exit(1)
    if not re.match(NUMBER_REGEX, tmp_x):
        print(f'Error: the first value (X) in {args.coordinates} isn\'t valid '
              '(verify that there are no spaces)')
        sys.exit(1)
    if not re.match(NUMBER_REGEX, tmp_y):
        print(f'Error: the second value (Y) in {args.coordinates} isn\'t '
              'valid (verify that there are no spaces)')
        sys.exit(1)
    if tmp_type is None:
        tmp_type = DEFAULT_TYPE
    if re.match(DEFAULT_TYPE_REGEX, tmp_type):
        args.x = int(tmp_x)
        args.y = int(tmp_y)
    elif re.match(CENTER_TYPE_REGEX, tmp_type):
        args.cx = int(tmp_x)
        args.cy = int(tmp_y)
    else:
        print(f'Error: the third value (TYPE) in {args.coordinates} '
              'isn\'t valid (verify that there are no spaces)')
        sys.exit(1)
    file.close()

# Verify X and Y
if args.x != UNDEFINED:
    if args.cx != UNDEFINED:
        print('Error: the -x option can\'t be used together with the '
              '--cx option')
        sys.exit(1)
    if args.x < ORIGIN:
        print(f'Error: X must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.x >= MAX:
        print(f'Error: X must be less than {MAX}')
        sys.exit(1)
else:
    args.x = ORIGIN
if args.y != UNDEFINED:
    if args.cy != UNDEFINED:
        print('Error: the -y option can\'t be used together with the '
              '--cy option')
        sys.exit(1)
    if args.y < ORIGIN:
        print(f'Error: Y must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.y >= MAX:
        print(f'Error: Y must be less than {MAX}')
        sys.exit(1)
else:
    args.y = ORIGIN

# Verify CX and CY
if args.cx != UNDEFINED:
    if args.cx < ORIGIN:
        print(f'Error: CX must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.cx >= MAX:
        print(f'Error: CX must be less than {MAX}')
        sys.exit(1)
if args.cy != UNDEFINED:
    if args.cy < ORIGIN:
        print(f'Error: CY must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.cy >= MAX:
        print(f'Error: CY must be less than {MAX}')
        sys.exit(1)

# Verify X2 and Y2
if args.x2 != UNDEFINED:
    if args.width != UNDEFINED:
        print('Error: the --x2 option can\'t be usued together with the '
              '--width option')
        sys.exit(1)
    if args.x2 < ORIGIN:
        print(f'Error: X2 must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.x2 >= MAX:
        print(f'Error: X2 must be less than {MAX}')
        sys.exit(1)
    if args.cx != UNDEFINED:
        if args.x2 < args.cx:
            print('Error: X2 must be greater than or equal to CX')
            sys.exit(1)
        args.width = ((args.x2 - args.cx) * 2) + 1
    else:
        if args.x2 < args.x:
            print('Error: X2 must be greater than or equal to X')
            sys.exit(1)
        args.width = args.x2 - args.x + 1
if args.y2 != UNDEFINED:
    if args.height != UNDEFINED:
        print('Error: the --y2 option can\'t be usued together with the '
              '--height option')
        sys.exit(1)
    if args.y2 < ORIGIN:
        print(f'Error: Y2 must be greater than or equal to {ORIGIN}')
        sys.exit(1)
    if args.y2 >= MAX:
        print(f'Error: Y2 must be less than {MAX}')
        sys.exit(1)
    if args.cy != UNDEFINED:
        if args.y2 < args.cy:
            print('Error: Y2 must be greater than or equal to CY')
            sys.exit(1)
        args.height = ((args.y2 - args.cy) * 2) + 1
    else:
        if args.y2 < args.y:
            print('Error: Y2 must be greater than or equal to X')
            sys.exit(1)
        args.height = args.y2 - args.y + 1

# INFO: The WIDTH and HEIGHT arguments are verified in the Element class

# Verify delay
if args.delay < 0:
    print('Error: DELAY must be greater than or equal to 0')
    sys.exit(1)

# Verify fill
if args.fill and (args.width == UNDEFINED or args.height == UNDEFINED):
    print('Error: the --fill option requires --width and --height, or '
          '--x2 and --y2 options')
    sys.exit(1)

# Verify overflow and push
if args.overflow and args.push:
    print('Error: the --overflow and --push options are mutually exclusive')
    sys.exit(1)

# Overrides delay when using multithreading
if args.multithreading:
    args.delay = 0

# ------------------------------- END ARGUMENTS -------------------------------

# Compose coordinates
more_str = ''
tmp_x = args.x
tmp_y = args.y
if args.cx != UNDEFINED or args.cy != UNDEFINED:
    if args.cx != UNDEFINED:
        more_str += f' --> ({CENTER_TYPE},'
        tmp_x = args.cx
    else:
        more_str += f' --> ({DEFAULT_TYPE},'
    if args.cy != UNDEFINED:
        more_str += f'{CENTER_TYPE})'
        tmp_y = args.cy
    else:
        more_str += f'{DEFAULT_TYPE})'
more_str = f' in ({tmp_x},{tmp_y}){more_str}'

# Create the source
if args.fill:
    source = Filling(args.source, args.width, args.height)
    print(str(source) + more_str)
else:
    source = Bitmap(args.source)
    print(str(source) + more_str)
    source.set_size(args.width, args.height)

# Save the size of the source
width, height = source.get_size()

# Check the center
# Use math.tunc instead of round
if args.cx != UNDEFINED:
    args.x = args.cx - math.trunc(width / 2)
if args.cy != UNDEFINED:
    args.y = args.cy - math.trunc(height / 2)

# Verify canvas boundaries
exceeds_x, exceeds_y, exceeds_x2, exceeds_y2 = exceeds_values(args.x, args.y,
                                                              width, height)
exceeds_var = exceeds_x or exceeds_y or exceeds_x2 or exceeds_y2
start_x = ORIGIN
start_y = ORIGIN
stop_width = width
stop_height = height
if exceeds_var:
    if not args.overflow and not args.push:
        print('Error: you are trying to paint outside the canvas')
        print('Use --overflow or --push to allow painting')
        sys.exit(1)
    if args.overflow:
        if exceeds_x:
            start_x -= args.x
        if exceeds_y:
            start_y -= args.y
        if exceeds_x2:
            stop_width = MAX - args.x
        if exceeds_y2:
            stop_height = MAX - args.y
    if args.push:
        if exceeds_x:
            args.x = ORIGIN
        if exceeds_y:
            args.y = ORIGIN
        if exceeds_x2:
            args.x = MAX - stop_width
        if exceeds_y2:
            args.y = MAX - stop_height
        if (exceeds(args.x, args.y, stop_width, stop_height)):
            print('Error: the area continues to exceed the limit values after '
                  'pushing it into the canvas\n'
                  'Check that the constants of the program are correct')
            sys.exit(1)

# Show information about the area
area_width = stop_width - start_x
area_height = stop_height - start_y
area_x = args.x + start_x
area_y = args.y + start_y
pixels = (area_width) * (area_height)
more_str = ''
if exceeds_var:
    if args.overflow:
        more_str = ' (overflow)'
    if args.push:
        more_str = ' (push)'
print(f'Area: {area_width}x{area_height} with {pixels} pixels{more_str} in '
      f'({area_x},{area_y})')

# Create canvas
canvas = Canvas(args.base_addr, args.verbose, args.dry_run)

# Source ranges
range_x = range(start_x, stop_width)
range_y = range(start_y, stop_height)

# Allocate pool executor when needed
if args.multithreading:
    canvas_futures = []
    executor = concurrent.futures.ThreadPoolExecutor(MAX_WORKERS)

# Paint the source
painted = 0
if args.reverse:
    iter_y = reversed(range_y)
else:
    iter_y = iter(range_y)
for y in iter_y:
    # Contrary to C/C++, it doesn't matter if you change the value of the loop
    # variable because on the next iteration it will be assigned the next
    # element from the list.
    canvas_y = args.y + y
    if args.reverse:
        iter_x = reversed(range_x)
    else:
        iter_x = iter(range_x)
    for x in iter_x:
        canvas_x = args.x + x
        r, g, b, a = source.get_pixel(x, y)
        if args.skip_transparent and a == 0:
            continue
        if args.multithreading:
            canvas_futures += [executor.submit(
                canvas.paint_pixel, canvas_x, canvas_y, r, g, b, a)]
            if (len(canvas_futures) % MAX_WORKERS) == 0:
                concurrent.futures.wait(canvas_futures)
                canvas_futures.clear()
        else:
            canvas.paint_pixel(canvas_x, canvas_y, r, g, b, a)
        painted += 1
        print(f'Painted pixels: {painted}/{pixels}', end='\r')
        time.sleep(args.delay)

# Shutdown executor
if args.multithreading:
    executor.shutdown(wait=True)

# Delete source
del source

# Print the final message
print('\nDone!')
