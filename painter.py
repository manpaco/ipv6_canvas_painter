#!/usr/bin/env python3

import os
import re
import sys
import time
import argparse
import platform
from PIL import Image
from PIL import ImageColor

# VPS IPv6 address (first 64 bits)
# Example: 2602:f75c:c0::XXXX:YYYY:RRGG:BBAA
# canvas.openbased.com
base_ip = '2602:f75c:c0::'
magic_number = 8
max = 65536
max_size = round(max / magic_number)
version = '0.1.0'
# RRGGBBAA regex with optional alpha channel
color_regex = r'^([0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?)$'
bmp_mode = 'RGBA'


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
    # if width and height are != 1 --> use both values without using aspect
    # if one of them is == -1 --> use aspect ratio to calculate to other one
    # Before run verifications
    def set_size(self, width, height):
        use_width = False
        use_height = False
        has_zeros = self.width == 0 or self.height == 0
        if width != -1:
            if width < 1:
                print('Error: width must be greater than or equal to 1')
                sys.exit(1)
            if width > max_size:
                print(f'Error: width must be less than or equal to {max_size}')
                sys.exit(1)
            use_width = True
        if height != -1:
            if height < 1:
                print('Error: height must be greater than or equal to 1')
                sys.exit(1)
            if height > max_size:
                print('Error: height must be less than or equal '
                      f'to {max_size}')
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

    # To override
    def close(self):
        pass

    def __str__(self):
        return f'{self.source} ({self.width}x{self.height})'


# Bitmap class to store: image
class Bitmap(Element):
    def __init__(self, source):
        super().__init__(source)
        try:
            self.img = Image.open(source)
        except FileNotFoundError:
            print(f'Error: {source} not found')
            sys.exit(1)
        self.img = self.img.convert(bmp_mode)
        # Initializing element size (do not use slef.set_size...)
        self.width, self.height = self.img.size
        if self.width < 1 or self.height < 1:
            print('Error: the image must have at least 1 pixel')
            sys.exit(1)

    def get_pixel(self, x, y):
        return self.img.getpixel((x, y))

    # Set bitmap size using the parent method and then resize the actual image
    # with the calculated values
    def set_size(self, width, height):
        super().set_size(width, height)
        self.img = self.img.resize((self.width, self.height))

    def close(self):
        self.img.close()

    def __del__(self):
        self.close()


# Filling class to store: filling color
class Filling(Element):
    def __init__(self, source):
        super().__init__(source)
        if not re.match(color_regex, source):
            print('Error: invalid color format')
            sys.exit(1)
        self.set_color(source)

    # If the filling has no alpha channel then return an extra value
    def get_pixel(self, x, y):
        if len(self.color) < 4:
            return self.color[0], self.color[1], self.color[2], 0
        else:
            return self.color

    def set_color(self, color):
        self.color = ImageColor.getrgb(f'#{color}')


# Parse arguments
parser = argparse.ArgumentParser(description='Draw on a canvas by sending '
                                 'ICMP packets (AKA pings) to an IPv6 address',
                                 epilog='When using --width and --height, or '
                                 '--x2 and --y2 arguments you can specify one '
                                 'of them and leave the script to calculate '
                                 'the other one using the image aspect ratio. '
                                 'If you specify both, the image will be '
                                 'resized without keeping the aspect ratio. '
                                 'If you specify -1 as value for '
                                 'any of them, the script will not take it '
                                 'into account (as if it was not specified). '
                                 'When using the --fill option, you should '
                                 'specify both --width and --height, or --x2 '
                                 'and --y2 arguments.')
parser.add_argument('source', metavar='image|color',
                    help='the image or color to draw. Use the --fill option '
                    'to fill with a color, but if --fill is not used then '
                    'this argument must be an image file. The color must be '
                    'in hexadecimal format, alpha channel is optional. '
                    'color_format: RRGGBB[AA] (str)')
parser.add_argument('-x', type=int, default=0,
                    help='the x coordinate of the canvas to start drawing at. '
                    'default: 0 (int)')
parser.add_argument('-y', type=int, default=0,
                    help='the y coordinate of the canvas to start drawing at. '
                    'default: 0 (int)')
parser.add_argument('--x2', type=int, default=-1,
                    help='the x coordinate of the canvas to stop drawing at. '
                    'default: -1 (int)')
parser.add_argument('--y2', type=int, default=-1,
                    help='the y coordinate of the canvas to stop drawing at. '
                    'default: -1 (int)')
parser.add_argument('--width', type=int, default=-1,
                    help='the width of the area to draw. default: -1 (int)')
parser.add_argument('--height', type=int, default=-1,
                    help='the height of the area to draw. default: -1 (int)')
parser.add_argument('-f', '--fill', action='store_true',
                    help='use the specified color to fill the area, instead '
                    'of drawing an image')
parser.add_argument('-c', '--coordinates', default=None,
                    help='read canvas coordinates from a file. '
                    'content_format: X,Y', metavar='FILE')
parser.add_argument('-d', '--delay', type=float, default=1,
                    help='the delay between each pixel in seconds. default: 1 '
                    '(float)')
parser.add_argument('-b', '--base-ip', default=base_ip,
                    help=f'the first 64 bits of the IPv6 address to draw to. '
                    f'default: {base_ip} (str)')
parser.add_argument('-r', '--reverse', action='store_true',
                    help='draw the area in reverse order')
parser.add_argument('-s', '--skip-transparent', action='store_true',
                    help='skip transparent pixels')
parser.add_argument('--push', action='store_true',
                    help='allow drawing despite exceeding the canvas, '
                    'the draw area will be pushed to the left and/or top')
parser.add_argument('--overflow', action='store_true',
                    help='allow drawing despite exceeding the canvas, '
                    'the draw area will be cropped')
parser.add_argument('--dry-run', action='store_true',
                    help='run but not draw in the canvas, do not send '
                    'ICMP packets')
parser.add_argument('--verbose', action='store_true',
                    help='print the ping command before executing')
parser.add_argument('--version', action='version',
                    version=f'%(prog)s v{version}')
args = parser.parse_args()

# Verify arguments
if args.delay < 0:
    print('Error: delay must be greater than or equal to 0')
    sys.exit(1)
if args.coordinates:
    if args.x != 0 or args.y != 0:
        print('Error: -x and -y arguments are not allowed with -c argument')
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
if args.x < 0 or args.y < 0:
    print('Error: x and y must be greater than or equal to 0')
    sys.exit(1)
if args.x >= max or args.y >= max:
    print(f'Error: x and y must be less than {max}')
    sys.exit(1)
if args.x2 != -1 or args.y2 != -1:
    if args.width != -1 or args.height != -1:
        print('Error: -w and -h arguments are not allowed with --x2 and --y2 '
              'arguments')
        sys.exit(1)
    if args.x2 != -1:
        if args.x2 < 0:
            print('Error: x2 must be greater than or equal to 0')
            sys.exit(1)
        if args.x2 < args.x:
            print('Error: x2 must be greater than or equal to x')
            sys.exit(1)
        if args.x2 >= max:
            print(f'Error: x2 must be less than {max}')
            sys.exit(1)
        args.width = args.x2 - args.x + 1
    if args.y2 != -1:
        if args.y2 < 0:
            print('Error: y2 must be greater than or equal to 0')
            sys.exit(1)
        if args.y2 < args.y:
            print('Error: y2 must be greater than or equal to y')
            sys.exit(1)
        if args.y2 >= max:
            print(f'Error: y2 must be less than {max}')
            sys.exit(1)
        args.height = args.y2 - args.y + 1
if args.fill and (args.width == -1 or args.height == -1):
    print('Error: --fill option requires --width and --height, or '
          '--x2 and --y2 arguments')
    sys.exit(1)
if args.overflow and args.push:
    print('Error: --overflow and --push arguments are mutually exclusive')
    sys.exit(1)

# Create the source
if args.fill:
    source = Filling(args.source)
else:
    source = Bitmap(args.source)
    width, height = source.get_size()
    if width > max_size or height > max_size:
        print('Error: image size must be less than or equal to '
              f'{max_size}x{max_size}')
        sys.exit(1)

# Set the size of the source
source.set_size(args.width, args.height)
width, height = source.get_size()

# Verify canvas boundaries
exceeds_x = args.x + width > max
exceeds_y = args.y + height > max
if exceeds_x or exceeds_y:
    if not args.overflow and not args.push:
        print('Error: you are trying to draw outside the canvas')
        print('Use --overflow or --push to allow drawing')
        sys.exit(1)
    if args.overflow:
        if exceeds_x:
            width = max - args.x
        if exceeds_y:
            height = max - args.y
    if args.push:
        if exceeds_x:
            args.x = max - width
        if exceeds_y:
            args.y = max - height

# Show information about the area
print(f'Coordinates: {args.x},{args.y}')
pixels = width * height
print(f'Area size: {width}x{height} with {pixels} pixels')

# Ping command
ping = 'ping -6 -c 1'
if platform.system() == 'Windows':
    ping = 'ping /6 /n 1'

# Redirect output
redirection = ' > /dev/null'
if platform.system() == 'Windows':
    redirection = ' > NUL'

drawn = 0
# Draw the source
for y in range(height):
    # Contrary to C/C++, it doesn't matter if you change the value of the loop
    # variable because on the next iteration it will be assigned the next
    # element from the list.
    if args.reverse:
        y = height - y - 1
    newy = args.y + y
    for x in range(width):
        if args.reverse:
            x = width - x - 1
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

# Close the source
if not args.fill:
    source.close()

# Print the final message
print('\nDone!')
