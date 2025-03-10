# IPv6 Canvas Painter

Overengineered solution to paint images or fill areas on a canvas through IPv6 addresses.

## How to run?

Clone the repository:

    git clone https://github.com/manpaco/ipv6_canvas_painter.git && cd ipv6_canvas_painter

Create a virtual environment:

    python3 -m venv venv

Activate the virtual environment:

    source venv/bin/activate

Install the requirements:

    pip install -r requirements.txt

Run the tool:

    ./painter.py -x 38700 -y 45600 -d 0.1 images/Flag_of_Argentina.png

...or configure the [wrapper script](/wrapper).

## How to get help?

Execute the following command:

    ./painter.py -h

## More info

Please visit [this repository](https://gitlab.com/zipdox/ipv6-canvas) to get detailed information about the canvas web app.
