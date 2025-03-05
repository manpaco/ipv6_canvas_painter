#!/usr/bin/env python3

import os
import re
import sys
import time
import argparse
import platform
from PIL import Image
from PIL import ImageColor

# Version
VERSION = '0.1.0'

# VPS IPv6 address (first 64 bits)
# Example: 2602:f75c:c0::XXXX:YYYY:RRGG:BBAA
# canvas.openbased.com
BASE_IP = '2602:f75c:c0::'
DELAY = 0.2

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

    def __str__(self):
        return f'\'{self.source}\' {self.width}x{self.height} with ' \
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

    def get_pixel(self, x, y):
        return self.img.getpixel((x, y))

    # Set bitmap size using the parent method and then resize the actual image
    # with the calculated values
    def set_size(self, width, height):
        super().set_size(width, height)
        self.img = self.img.resize((self.width, self.height))

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
    return x < ORIGIN, y < ORIGIN, x + width > MAX, y + height > MAX


def exceeds(x, y, width, height):
    return x < ORIGIN or y < ORIGIN or x + width > MAX or y + height > MAX


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
parser.add_argument('-b', '--base-ip', default=BASE_IP,
                    help=f'the first 64 bits of the IPv6 address. '
                    f'default: {BASE_IP} (str)')
parser.add_argument('-f', '--fill', action='store_true',
                    help='use the specified color to fill the area, instead '
                    'of painting an image.')
parser.add_argument('-r', '--reverse', action='store_true',
                    help='paint the area in reverse order')
parser.add_argument('-s', '--skip-transparent', action='store_true',
                    help='skip completely transparent pixels')
parser.add_argument('--overflow', action='store_true',
                    help='the area will be cropped if it exceds the '
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
    width, height = source.get_size()
    if width < MIN_SIZE or height < MIN_SIZE:
        print(f'Error: the image must have at least {MIN_SIZE} pixel')
        sys.exit(1)
    if width > MAX_SIZE or height > MAX_SIZE:
        print('Error: the image size must be less than or equal to '
              f'{MAX_SIZE}x{MAX_SIZE}')
        sys.exit(1)

# Save the size of the source
width, height = source.get_size()

# Check the center
if args.cx != UNDEFINED:
    args.x = args.cx - round(width / 2)
if args.cy != UNDEFINED:
    args.y = args.cy - round(height / 2)

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
virt_width = stop_width - start_x
virt_height = stop_height - start_y
virt_x = args.x + start_x
virt_y = args.y + start_y
pixels = (virt_width) * (virt_height)
more_str = ''
if exceeds_var:
    if args.overflow:
        more_str = ' (overflow)'
    if args.push:
        more_str = ' (push)'
print(f'Area: {virt_width}x{virt_height} with {pixels} pixels{more_str} in '
      f'({virt_x},{virt_y})')

# Ping command
ping = 'ping -6 -c 1'
if platform.system() == 'Windows':
    ping = 'ping /6 /n 1'

# Redirect output
redirection = ' > /dev/null'
if platform.system() == 'Windows':
    redirection = ' > NUL'

# Reverse ranges if needed
range_x = range(start_x, stop_width)
range_y = range(start_y, stop_height)
if args.reverse:
    range_x = reversed(range_x)
    range_y = reversed(range_y)
painted = 0
# Paint the source
for y in range_y:
    # Contrary to C/C++, it doesn't matter if you change the value of the loop
    # variable because on the next iteration it will be assigned the next
    # element from the list.
    newy = args.y + y
    for x in range_x:
        newx = args.x + x
        r, g, b, a = source.get_pixel(x, y)
        if args.skip_transparent and a == 0:
            continue
        address = f'{args.base_ip}{newx:04x}:{newy:04x}:' \
                  f'{r:02x}{g:02x}:{b:02x}{a:02x}'
        command = f'{ping} {address}{redirection}'
        if args.verbose:
            print(command)
        if not args.dry_run:
            os.system(command)
        painted += 1
        print(f'Painted pixels: {painted}/{pixels}', end='\r')
        time.sleep(args.delay)

# Print the final message
print('\nDone!')
