#!/usr/bin/env python3
# NeoPixel library lights
# Author: Eli Harper, to some extent.
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import argparse
from neopixel import *
import random
import requests
import time

# LED strip configuration:
LED_COUNT      = 300     # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53


class ColorBurst:
    def __init__(self, center, hue, hueVariance, particleCount, maxVelocity, maxDrag, minFadeTime, maxFadeTime):
        self.center = center
        self.hue = hue
        self.hueVariance = hueVariance
        self.maxVelocity = maxVelocity
        self.maxDrag = maxDrag
        self.minFadeTime = minFadeTime
        self.maxFadeTime = maxFadeTime

        self.rng = random.Random()
        self.particles = [ColorParticle(wheel(hue + int(self.rng.uniform(-hueVariance, hueVariance))), self.rng.uniform(minFadeTime, maxFadeTime), center, self.rng.uniform(-maxVelocity, maxVelocity),
            0, self.rng.uniform(0, maxDrag)) for i in range(particleCount)]

    def __repr__(self):
        return "{},{},{},{}".format(self.center, self.color, self.maxVelocity, self.fadeTime)

    # returns array of (index,color)
    def simulate(self, t):
        return [p.simulate(t) for p in self.particles]


# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i+j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)


        
def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def colorBursts(strip, wait_ms=10):
    """Some colorbursty shit that will probably not work well"""
    for i in range(256):
        center = random.randint(0, strip.numPixels())
        colorBegin = random.randint(0, 256)
        for j in range(256):
            strip.setPixelColor((center + j)%strip.numPixels(), wheel((colorBegin+5*j)%256))
            strip.setPixelColor((center - j)%strip.numPixels(), wheel((colorBegin+5*j)%256))
            strip.show()
            time.sleep(wait_ms/1000)
            

def runBurst(strip, wait_ms=10):
    print ('Press Ctrl-C to quit.')
    t = 0
    colorBurst = None
    colorBurst2 = None
    # colorParticle = ColorParticle(wheel(0), 30*2, strip.numPixels()/2, 2, 0, 0.05)
    while True:
        if t%40 == 0:
            colorBurst = ColorBurst(random.randint(0,strip.numPixels()-1), random.randint(0,255), 20, random.randint(20,35), 3, 0.05, 30/3, 30*1)
        if t == 0 or t%40 == 30:
            colorBurst2 = ColorBurst(random.randint(0,strip.numPixels()-1), random.randint(0,255), 20, random.randint(20,35), 3, 0.05, 30/3, 30*1)
        colors = [0]*strip.numPixels()
        setArrayValues(colors, colorBurst.simulate(t%40), False)
        setArrayValues(colors, colorBurst2.simulate((t-30)%40), False)
        # setArrayValues(colors, [colorParticle.simulate(t)], True)
        showColors(pixels, colors)

        t+= 1
        time.sleep(wait_ms/1000)        
                

                
# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    print ('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    try:

        while True:
            print('Color burst')
            runBurst(strip)
            ### print ('Color wipe animations.')
            ### colorWipe(strip, Color(255, 0, 0))  # Red wipe
            ### colorWipe(strip, Color(0, 255, 0))  # Blue wipe
            ### colorWipe(strip, Color(0, 0, 255))  # Green wipe
            ### print ('Theater chase animations.')
            ### theaterChase(strip, Color(127, 127, 127))  # White theater chase
            ### theaterChase(strip, Color(127,   0,   0))  # Red theater chase
            ### theaterChase(strip, Color(  0,   0, 127))  # Blue theater chase
            ### print ('Rainbow animations.')
            ### rainbow(strip)
            ### rainbowCycle(strip)
            ### theaterChaseRainbow(strip)

    except KeyboardInterrupt:
        if args.clear:
            colorWipe(strip, Color(0,0,0), 10)
