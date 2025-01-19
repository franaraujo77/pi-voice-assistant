#!/usr/bin/env python3
"""Controls the LEDs and sounds on the ReSpeaker 2mic HAT."""
import argparse
import asyncio
import logging
import time
import subprocess
import os
from functools import partial
from math import ceil
from typing import Tuple

import gpiozero
import spidev
from wyoming.asr import Transcript
from wyoming.event import Event
from wyoming.satellite import (
    RunSatellite,
    SatelliteConnected,
    SatelliteDisconnected,
    StreamingStarted,
    StreamingStopped,
)
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.vad import VoiceStarted
from wyoming.wake import Detection

_LOGGER = logging.getLogger()

NUM_LEDS = 3
LEDS_GPIO = 12
RGB_MAP = {
    "rgb": [3, 2, 1],
    "rbg": [3, 1, 2],
    "grb": [2, 3, 1],
    "gbr": [2, 1, 3],
    "brg": [1, 3, 2],
    "bgr": [1, 2, 3],
}

async def play_sound(sound_file: str):
    """Play a sound file using aplay."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'aplay',
            '-D',
            'plughw:CARD=seeed2micvoicec,DEV=0',
            sound_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
    except Exception as e:
        _LOGGER.error(f"Error playing sound: {e}")

async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument(
        "--led-brightness",
        type=int,
        choices=range(1, 32),
        default=31,
        help="LED brightness (integer from 1 to 31)",
    )
    parser.add_argument(
        "--sounds-dir",
        type=str,
        default="/home/dihan/sounds",
        help="Directory containing sound files",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    # Create sounds directory if it doesn't exist
    os.makedirs(args.sounds_dir, exist_ok=True)

    _LOGGER.info("Ready")

    # Turn on power to LEDs but keep them off
    led_power = gpiozero.LED(LEDS_GPIO, active_high=False)
    led_power.on()

    leds = APA102(num_led=NUM_LEDS, global_brightness=args.led_brightness)
    # Initialize LEDs to off
    for i in range(NUM_LEDS):
        leds.set_pixel(i, 0, 0, 0)
    leds.show()

    # Start server
    server = AsyncServer.from_uri(args.uri)

    try:
        await server.run(partial(LEDsEventHandler, args, leds))
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure LEDs are off when shutting down
        for i in range(NUM_LEDS):
            leds.set_pixel(i, 0, 0, 0)
        leds.show()
        leds.cleanup()
        led_power.off()


# -----------------------------------------------------------------------------

_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_RED = (255, 0, 0)
_YELLOW = (255, 255, 0)
_BLUE = (0, 0, 255)
_GREEN = (0, 255, 0)

class LEDsEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        cli_args: argparse.Namespace,
        leds: "APA102",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.client_id = str(time.monotonic_ns())
        self.leds = leds
        self.is_processing = False
        self.sounds_dir = cli_args.sounds_dir
        self.error_task = None  # To store the error handling task
        
        # Initialize LEDs to off
        self.color(_BLACK)
        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        """Handle event from satellite."""
        _LOGGER.debug(event)

        # Cancel any existing error task
        if self.error_task and not self.error_task.done():
            self.error_task.cancel()

        if Detection.is_type(event.type):
            # Blue for wake word detection and play chime
            self.color(_BLUE)
            self.is_processing = True
            await play_sound(os.path.join(self.sounds_dir, "aha.wav"))
        elif event.type == "error" and event.data.get("code") == "stt-no-text-recognized":
            # Handle no text recognized error
            self.error_task = asyncio.create_task(self.handle_no_text_error())
        elif StreamingStarted.is_type(event.type) and self.is_processing:
            # Yellow while streaming/processing if wake word was detected
            self.color(_YELLOW)
        elif event.type == "synthesize":
            # When TTS synthesis starts, schedule turning off the LED
            asyncio.create_task(self.turn_off_after_delay())
        elif RunSatellite.is_type(event.type):
            self.is_processing = False
            self.color(_BLACK)
        elif SatelliteConnected.is_type(event.type):
            # Quick green flash for connection
            for _ in range(2):
                self.color(_GREEN)
                await asyncio.sleep(0.2)
                self.color(_BLACK)
                await asyncio.sleep(0.2)
        elif SatelliteDisconnected.is_type(event.type):
            # Brief red flash for disconnection
            self.color(_RED)
            await asyncio.sleep(0.5)
            self.color(_BLACK)
            self.is_processing = False

        return True

    async def handle_no_text_error(self):
        """Handle the no text recognized error with red light for 5 seconds."""
        try:
            self.color(_RED)
            await asyncio.sleep(5)
            self.color(_BLACK)
            self.is_processing = False
        except asyncio.CancelledError:
            # If this task is cancelled, ensure LEDs are in correct state
            if self.is_processing:
                self.color(_YELLOW)
            else:
                self.color(_BLACK)

    async def turn_off_after_delay(self):
        """Turn off LEDs after a short delay."""
        await asyncio.sleep(5)  # Wait for TTS to start playing
        self.is_processing = False
        self.color(_BLACK)

    def color(self, rgb: Tuple[int, int, int]) -> None:
        """Set color of all LEDs."""
        for i in range(NUM_LEDS):
            self.leds.set_pixel(i, rgb[0], rgb[1], rgb[2])
        self.leds.show()

class APA102:
    """
    Driver for APA102 LEDS (aka "DotStar").
    (c) Martin Erzberger 2016-2017
    """

    # Constants
    MAX_BRIGHTNESS = 0b11111  # Safeguard: Set to a value appropriate for your setup
    LED_START = 0b11100000  # Three "1" bits, followed by 5 brightness bits

    def __init__(
        self,
        num_led,
        global_brightness,
        order="rgb",
        bus=0,
        device=1,
        max_speed_hz=8000000,
    ):
        self.num_led = num_led  # The number of LEDs in the Strip
        order = order.lower()
        self.rgb = RGB_MAP.get(order, RGB_MAP["rgb"])
        # Limit the brightness to the maximum if it's set higher
        if global_brightness > self.MAX_BRIGHTNESS:
            self.global_brightness = self.MAX_BRIGHTNESS
        else:
            self.global_brightness = global_brightness
        _LOGGER.debug("LED brightness: %d", self.global_brightness)

        self.leds = [self.LED_START, 0, 0, 0] * self.num_led  # Pixel buffer
        self.spi = spidev.SpiDev()  # Init the SPI device
        self.spi.open(bus, device)  # Open SPI port 0, slave device (CS) 1
        # Up the speed a bit, so that the LEDs are painted faster
        if max_speed_hz:
            self.spi.max_speed_hz = max_speed_hz

    def clock_start_frame(self):
        """Sends a start frame to the LED strip."""
        self.spi.xfer2([0] * 4)  # Start frame, 32 zero bits

    def clock_end_frame(self):
        """Sends an end frame to the LED strip."""
        self.spi.xfer2([0xFF] * 4)

    def set_pixel(self, led_num, red, green, blue, bright_percent=100):
        """Sets the color of one pixel in the LED stripe."""
        if led_num < 0:
            return  # Pixel is invisible, so ignore
        if led_num >= self.num_led:
            return  # again, invisible

        brightness = int(ceil(bright_percent * self.global_brightness / 100.0))
        ledstart = (brightness & 0b00011111) | self.LED_START

        start_index = 4 * led_num
        self.leds[start_index] = ledstart
        self.leds[start_index + self.rgb[0]] = red
        self.leds[start_index + self.rgb[1]] = green
        self.leds[start_index + self.rgb[2]] = blue

    def show(self):
        """Sends the content of the pixel buffer to the strip."""
        self.clock_start_frame()
        data = list(self.leds)
        while data:
            self.spi.xfer2(data[:32])
            data = data[32:]
        self.clock_end_frame()

    def cleanup(self):
        """Release the SPI device; Call this method at the end"""
        self.spi.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass