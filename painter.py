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

# Canvas constants
MAGIC_NUMBER = 8
UNDEFINED = -1
ORIGIN = 0
MAX = 0x10000
MIN_SIZE = 1
MAX_SIZE = round(MAX / MAGIC_NUMBER)

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
        return f'{self.source} ({self.width}x{self.height}) with ' \
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
        if not re.match(COLOR_REGEX, source):
            print('Error: invalid color format')
            sys.exit(1)
        self.set_color(source)
        self.set_size(width, height)

    # If the filling has no alpha channel then return an extra value
    def get_pixel(self, x, y):
        if len(self.color) < 4:
            return self.color[0], self.color[1], self.color[2], MAX_COLOR
        else:
            return self.color

    def set_color(self, color):
        self.color = ImageColor.getrgb(f'#{color}')

    def __str__(self):
        return 'Filling: #' + super().__str__()


def exceeds_values(x, y, width, height):
    return x < 0, y < 0, x + width > MAX, y + height > MAX


def exceeds(x, y, width, height):
    return x < 0 or y < 0 or x + width > MAX or y + height > MAX


# Parse arguments
parser = argparse.ArgumentParser(description='Draw on a canvas by sending '
                                 'ICMP packets (AKA pings) to an IPv6 '
                                 'address.',
                                 epilog='IMPORTANT: '
                                 'When using --width and --height, or '
                                 '--x2 and --y2 options you can specify one '
                                 'of them and leave the script to calculate '
                                 'the other one using the image aspect ratio. '
                                 'If you specify both, the image will be '
                                 'resized without keeping the aspect ratio. '
                                 f'If you specify {UNDEFINED} as value for '
                                 'any of them the script will not take it '
                                 'into account, as if you hadn\'t specified '
                                 'it.'
                                 )
parser.add_argument('source', metavar='image|color',
                    help='the image or color to draw. Use the --fill option '
                    'to fill with a color, but if it\'s not used then this '
                    'argument must be an image file. The color must be in '
                    'hexadecimal format; alpha channel is optional. '
                    'color_format: RRGGBB[AA] (str)')
parser.add_argument('-c', '--coordinates', default=None,
                    help='read canvas coordinates from a file. '
                    'content_format: X,Y', metavar='FILE')
parser.add_argument('-x', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to start drawing at. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('-y', type=int, default=UNDEFINED,
                    help='similat to -x. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--cx', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to place the center '
                    'of the image, or filling area. Overrrides -x option. '
                    'You can\'t use it together with --x2 and --y2 options.'
                    f' default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--cy', type=int, default=UNDEFINED,
                    help='similar to --cx.'
                    f' default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--x2', type=int, default=UNDEFINED,
                    help='the x coordinate of the canvas to stop drawing at. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--y2', type=int, default=UNDEFINED,
                    help='similar to --x2. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--width', type=int, default=UNDEFINED,
                    help='the width of the area to draw. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('--height', type=int, default=UNDEFINED,
                    help='similar to --width. '
                    f'default: {UNDEFINED} (UNDEFINED)')
parser.add_argument('-f', '--fill', action='store_true',
                    help='use the specified color to fill the area, instead '
                    'of drawing an image. You must specify both --width and '
                    '--height, or --x2 and --y2 options')
parser.add_argument('-d', '--delay', type=float, default=1,
                    help='the delay between each pixel in seconds. default: 1 '
                    '(float)')
parser.add_argument('-b', '--base-ip', default=BASE_IP,
                    help=f'the first 64 bits of the IPv6 address to draw to. '
                    f'default: {BASE_IP} (str)')
parser.add_argument('-r', '--reverse', action='store_true',
                    help='draw the area in reverse order')
parser.add_argument('-s', '--skip-transparent', action='store_true',
                    help='skip completely transparent pixels')
parser.add_argument('--overflow', action='store_true',
                    help='the draw area will be cropped if it exceds the '
                    'boundaries')
parser.add_argument('--push', action='store_true',
                    help='the draw area will be pushed into the canvas if it '
                    'exceeds the boundaries')
parser.add_argument('--dry-run', action='store_true',
                    help='run but don\'t send ICMP packets. '
                    'Useful to test commands')
parser.add_argument('--verbose', action='store_true',
                    help='print the ping command before executing')
parser.add_argument('--version', action='version',
                    version=f'%(prog)s v{VERSION}')
args = parser.parse_args()

# Verify arguments
if args.coordinates:
    if (args.x != UNDEFINED or args.y != UNDEFINED
            or args.cx != UNDEFINED or args.cy != UNDEFINED):
        print('Error: the --coordinates option can\'t be used together with '
              '-x, -y, --cx, and --cy options')
        sys.exit(1)
    try:
        with open(args.coordinates) as f:
            args.x, args.y = map(int, f.readline().split(','))
    except FileNotFoundError:
        print(f'Error: {args.coordinates} not found')
        sys.exit(1)
    except ValueError:
        print(f'Error: {args.coordinates} must contain two integers separated '
              'by a comma.\nExample: 123,456')
        sys.exit(1)
if args.x != UNDEFINED:
    if args.cx != UNDEFINED:
        print('Error: the -x option can\'t be used together with the '
              '--cx option')
        sys.exit(1)
    if args.x < ORIGIN:
        print('Error: X must be greater than or equal to 0')
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
        print('Error: Y must be greater than or equal to 0')
        sys.exit(1)
    if args.y >= MAX:
        print(f'Error: Y must be less than {MAX}')
        sys.exit(1)
else:
    args.y = ORIGIN
if args.cx != UNDEFINED:
    if args.cx < ORIGIN:
        print('Error: CX must be greater than or equal to 0')
        sys.exit(1)
    if args.cx >= MAX:
        print(f'Error: CX must be less than {MAX}')
        sys.exit(1)
if args.cy != UNDEFINED:
    if args.cy < ORIGIN:
        print('Error: CY must be greater than or equal to 0')
        sys.exit(1)
    if args.cy >= MAX:
        print(f'Error: CY must be less than {MAX}')
        sys.exit(1)
if args.x2 != UNDEFINED:
    if args.width != UNDEFINED:
        print('Error: the --x2 option can\'t be usued together with the '
              '--width option')
        sys.exit(1)
    if args.x2 < ORIGIN:
        print('Error: X2 must be greater than or equal to 0')
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
    if args.y2 < 0:
        print('Error: Y2 must be greater than or equal to 0')
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
if args.fill and (args.width == UNDEFINED or args.height == UNDEFINED):
    print('Error: the --fill option requires --width and --height, or '
          '--x2 and --y2 options')
    sys.exit(1)
if args.delay < 0:
    print('Error: DELAY must be greater than or equal to 0')
    sys.exit(1)
if args.overflow and args.push:
    print('Error: the --overflow and --push options are mutually exclusive')
    sys.exit(1)

# Create the source
if args.fill:
    source = Filling(args.source, args.width, args.height)
    print(source)
else:
    source = Bitmap(args.source)
    print(source)
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
start_x = 0
start_y = 0
stop_width = width
stop_height = height
if exceeds_var:
    if not args.overflow and not args.push:
        print('Error: you are trying to draw outside the canvas')
        print('Use --overflow or --push to allow drawing')
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
            args.x = 0
        if exceeds_y:
            args.y = 0
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
print(f'Coordinates: {virt_x},{virt_y}')
pixels = (virt_width) * (virt_height)
more = ''
if exceeds_var:
    if args.overflow:
        more = ' (overflow)'
    if args.push:
        more = ' (push)'
print(f'Area size: {virt_width}x{virt_height} with {pixels} pixels{more}')

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
drawn = 0
# Draw the source
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
        drawn += 1
        print(f'Drawn pixels: {drawn}/{pixels}', end='\r')
        time.sleep(args.delay)

# Print the final message
print('\nDone!')
