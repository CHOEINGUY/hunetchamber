#!/bin/bash
sudo chmod 666 /dev/cu.usbmodem101
.venv/bin/python3 -m mpremote connect /dev/cu.usbmodem101 exec "import network; print(dir(network))"
