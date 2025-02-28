#!/usr/bin/env python

import os
import sys
import time
import argparse
import platform
from PIL import Image

# OpenBased Canvas IPv6 address
# canvas.openbased.com
baseip = '2602:f75c:c0::'
max = 65535

# Parse arguments
parser = argparse.ArgumentParser(description='Draw an image by sending ICMP packets (AKA pings) to an IPv6 address')
parser.add_argument('image', help='The image to draw')
parser.add_argument('-x', type=int, default=0, help='the x coordinate to start drawing at. default: 0 (int)')
parser.add_argument('-y', type=int, default=0, help='the y coordinate to start drawing at. default: 0 (int)')
parser.add_argument('-d', '--delay', type=float, default=1, help='the delay between each pixel in seconds. default: 1 (float)')
parser.add_argument('-b', '--baseip', default=baseip, help=f'the base IPv6 address to draw to. format: {{BASEIP}}XXXX:YYYY:RRGG:BBAA. default: {baseip} (str)')
parser.add_argument('-r', '--reverse', action='store_true', help='draw the image in reverse order')
parser.add_argument('--verbose', action='store_true', help='print the ping command before executing')
args = parser.parse_args()

if args.delay < 0:
    print('Error: delay must be greater than or equal to 0')
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
pixels = width * height

if args.x + width > max or args.y + height > max:
    print('Error: you are trying to draw outside the canvas')
    if args.x + width > max:
        print(f'Suggested x: {max - width}')
    if args.y + height > max:
        print(f'Suggested y: {max - height}')
    sys.exit(1)

drawn = 0
# Draw the image
for x in range(width):
    if args.reverse:
        x = width - x - 1
    newx = args.x + x
    for y in range(height):
        if args.reverse:
            y = height - y - 1
        newy = args.y + y
        r, g, b, a = img.getpixel((x, y))
        address = f'{args.baseip}{newx:04x}:{newy:04x}:{r:02x}{g:02x}:{b:02x}{a:02x}'
        command = 'ping -6 -c 1'
        if platform.system() == 'Windows':
            command = 'ping /6 /n 1'
        redirection = ' > /dev/null'
        if platform.system() == 'Windows':
            redirection = ' > NUL'
        command = f'{command} {address}{redirection}'
        if args.verbose:
            print(command)
        os.system(command)
        drawn += 1
        print(f'Drawn pixels: {drawn}/{pixels}', end='\r')
        time.sleep(args.delay)
