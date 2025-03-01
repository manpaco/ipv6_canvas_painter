# Paint wrapper

Automate your painting process with symlinks and crontab.

## How it works?

The wrapper needs to be installed in a directory that contains two components: `to_paint` directory and `tool_dir` symlink.

### `to_paint` directory

This directory contains symlinked image files that are going to be painted.

### `tool_dir` symlink

This symlink points to the directory that contains the painting tool, e.g. `painter.py`.

### The trick

The pointed image file must have in the same directory a file with the same name and the extension `.xy`. This special file contains the canvas coordinates to start painting.

Finaly the tool is called with the pointed image file and the `.xy` file as arguments.

## Crontab

The wrapper can be called by a cron job to automate the painting process. For example, the following cron job paints every Tuesday at 3:00 AM:

```bash
0 3 * * 2 /path/to/wrapper.sh
```
