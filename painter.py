#!/usr/bin/env python3

import os
import sys
import time
import argparse
import platform
from PIL import Image

# VPS IPv6 address (first 64 bits)
# Example: 2602:f75c:c0::XXXX:YYYY:RRGG:BBAA
# canvas.openbased.com
base_ip = '2602:f75c:c0::'
max = 65535
version = '0.1.0'

# Parse arguments
parser = argparse.ArgumentParser(description='Draw an image by sending ICMP '
                                 'packets (AKA pings) to an IPv6 address')
parser.add_argument('image', help='the image to draw')
parser.add_argument('-x', type=int, default=0,
                    help='the x coordinate of the canvas to start drawing at. '
                    'default: 0 (int)')
parser.add_argument('-y', type=int, default=0,
                    help='the y coordinate of the canvas to start drawing at. '
                    'default: 0 (int)')
parser.add_argument('-c', '--coordinates', type=str, default=None,
                    help='read canvas coordinates from a file. '
                    'content_format: X,Y', metavar='FILE')
parser.add_argument('-d', '--delay', type=float, default=1,
                    help='the delay between each pixel in seconds. default: 1 '
                    '(float)')
parser.add_argument('-b', '--base-ip', default=base_ip,
                    help=f'the first 64 bits of the IPv6 address to draw to. '
                    f'default: {base_ip} (str)')
parser.add_argument('-r', '--reverse', action='store_true',
                    help='draw the image in reverse order')
parser.add_argument('--verbose', action='store_true',
                    help='print the ping command before executing')
parser.add_argument('--version', action='version',
                    version=f'%(prog)s {version}')
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

# Open the image
try:
    img = Image.open(args.image)
except FileNotFoundError:
    print(f'Error: {args.image} not found')
    sys.exit(1)

# Convert the image to RGBA
img = img.convert('RGBA')

# Size of the image
width, height = img.size
if width < 1 or height < 1:
    print('Error: the image must have at least 1 pixel')
    sys.exit(1)
pixels = width * height

# Verify canvas boundaries
exceeds_x = args.x + width - 1 > max
exceeds_y = args.y + height - 1 > max
if exceeds_x or exceeds_y:
    print('Error: you are trying to draw outside the canvas')
    if exceeds_x:
        print(f'Suggested x: {max - width + 1}')
    if exceeds_y:
        print(f'Suggested y: {max - height + 1}')
    sys.exit(1)

# Ping command
ping = 'ping -6 -c 1'
if platform.system() == 'Windows':
    ping = 'ping /6 /n 1'

# Redirect output
redirection = ' > /dev/null'
if platform.system() == 'Windows':
    redirection = ' > NUL'

drawn = 0
# Draw the image
for x in range(width):
    # Contrary to C/C++, it doesn't matter if you change the value of the loop
    # variable because on the next iteration it will be assigned the next
    # element from the list.
    if args.reverse:
        x = width - x - 1
    newx = args.x + x
    for y in range(height):
        if args.reverse:
            y = height - y - 1
        newy = args.y + y
        r, g, b, a = img.getpixel((x, y))
        address = f'{args.base_ip}{newx:04x}:{newy:04x}:' \
                  f'{r:02x}{g:02x}:{b:02x}{a:02x}'
        command = f'{ping} {address}{redirection}'
        if args.verbose:
            print(command)
        os.system(command)
        drawn += 1
        print(f'Drawn pixels: {drawn}/{pixels}', end='\r')
        time.sleep(args.delay)

img.close()
print('\nDone!')
