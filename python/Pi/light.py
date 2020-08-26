#!/usr/bin/env python3

# Built from direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.
from neopixel import *
from .message import SceneMessage, AdministrativeMessage

import animations
import argparse
import logging
import threading
import time
import sys

sys.path.insert(0, "/home/pi/.local/lib/python3.7/site-packages")
from kafka import KafkaConsumer
from json import loads
from decouple import config
from random import seed, randint
import traceback



# LED strip configuration:
LED_COUNT      = 300     # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

DARK_PIXEL = Color(0,0,0)


LOGGER_NAME = 'light_logger'
LOG_LOCATION = 'log/light.log'

UPDATE_BRIGHTNESS = 'update_brightness'
OFF = 'off'


def fastWipe(color=DARK_PIXEL):
    global strip

    """Wipe color REAL QUICK across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)

    strip.show()


# Define functions which animate LEDs in various ways.
def colorWipe(color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    global strip

    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    global strip

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
    global strip

    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def rainbow(wait_ms=20, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    global strip

    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i+j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def rainbowCycle(wait_ms=20, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    global strip

    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    global strip

    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

# Personal Additions: #

# Helpers:
class Delta:
    def __init__(self, range, rate, increase=True):
        self.range = range
        self.rate = rate
        self.increase = increase


def convert_to_rgb(colors: list):
    tupleys = []
    for hex_color in colors:
        hex_color = hex_color.lstrip('#')
        tupleys.append(tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)))

    return tupleys

# Action functions:
# Administrative:
def configure_logger(name: str, filepath: str, logLevel: int) -> logging.Logger:
    logger = logging.getLogger(name)
    handler = logging.FileHandler(filepath)

    logger.addHandler(handler)
    logger.setLevel(logLevel)

    return logger


def make_strip(brightness):
    global strip

    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, int(brightness), LED_CHANNEL)
    return strip


def message_handler(message):
    global scene
    global strip
    global prev_message

    try:
        # First check if the message requires termination of the previous scene:
        if handle_ending_animation(message):
            return
        # Ensure that the strip has been initialized; if so, apply the new brightness,
        #   otherwise, create the strip first:
        if strip is not None:
            if type(message) == SceneMessage:
                strip.setBrightness(int(message.defaultBrightness))
    except (UnboundLocalError, NameError) as e:
        # These errors will occur when the strip has not been initialized;
        #   i.e. the first time a scene is applied.
        strip = make_strip(message.defaultBrightness)
        strip.begin()

    
    try:
        if message.animated:
            scene = threading.Thread(target=animation_handler, args=(message.colors, message.animation))
    except KeyError as ke:
        # Serialization & deserialization into proto Objects and back will remove
        logger.debug('KeyError: {}'.format(ke))
        scene = threading.Thread(target=paint_with_colors, args=(colors))

    scene.start()
    
    prev_message = message


def animation_handler(colors, animation):
    global stop_animation

    logger.info('Received animation {} in animation_handler'.format(animation))

    while not stop_animation:
        switcher = {
            "Projectile": fire_projectiles,
            "Breathe": breathe,
            "Twinkle": twinkle,
            "Fade": fade_between,
            "Meiosis": meiosis
        }
        switcher[animation](colors)


def handle_ending_animation(message):
    # import pdb; pdb.set_trace()
    global stop_animation
    global strip

    # Short-circuit in the event of a "turn off" message:
    if message.functionCall == OFF:
        if strip is not None:
            logger.info('Hit \'off\' fucntionCall')
            stop_animation = True
            scene.join()
            fastWipe()
            logger.info('Lights wiped; they should now be in their \"off\" state.')
            stop_animation = False
            # Returning False tells the main loop to just wait for the next message
            #   instead of handling it further as if it were a scene
            return True

    elif message.functionCall == UPDATE_BRIGHTNESS :
        logger.info("UPDATING BRIGHTNESS TO: {}".format(message.value))
        strip.setBrightness(int(message.value))
        strip.show()
        return True

    else:
        try:
            # Check if the changed-to scene is the same as the last - if not, tell the thread to end.
            if prev_message.Id == message.Id:
                # Don't bother with re-applying the same scene:
                return True

            else:
                if prev_message.animated:
                    # Tell animated function to end, then wait for it to do so before continuing.
                    stop_animation = True
                    scene.join()
                    stop_animation = False
                return False

        # If animationId is unset (first animation since app start), initialize stop_animation to False:
        except (NameError, KeyError):
            stop_animation = False
            return False

############
# Scenes: #
############
def paint_with_colors(*colors):
    global strip

    # Accept color as hex
    logger.info('Setting solid color to: {}'.format(colors))

    if type(colors[0]) == str:
        # Extracting ints from RgbColor object, which stores them as strings:
        rgb_tuples = convert_to_rgb(colors)
    elif type(colors[0]) == list:
        rgb_tuples = convert_to_rgb(colors[0])
    else:
        rgb_tuples = colors

    range_per_color = strip.numPixels() / len(rgb_tuples)
    range_per_color = int(range_per_color)
    rgb_tuple_index = 0

    logger.info('rgb_tuples: {}, len(rgb_tuples): {}, type(rgb_tuples[0]): {}'.format(rgb_tuples, len(rgb_tuples), type(rgb_tuples[0])))

    for i in range(strip.numPixels()):
        # Make the strip show even(ish) amounts of each color, with remainder applied to last color
        if i % range_per_color == 0 and rgb_tuple_index < len(rgb_tuples):
            red, green, blue = rgb_tuples[rgb_tuple_index]
            rgb_tuple_index += 1
            # No idea why, but this function accepts in format GRB..
        strip.setPixelColor(i, Color(green, red, blue))
        strip.show()


def fire_projectiles(colors, projectile_size=8):
    global strip
    global stop_animation
    rgb_tuples = convert_to_rgb(colors)

    while not stop_animation:
        for tuple in rgb_tuples:
            if stop_animation:
                break
            red, green, blue = tuple
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(green, red, blue))
                strip.show()
                # i => head of projectile
                if i > (projectile_size - 1):
                    strip.setPixelColor(i - projectile_size, Color(0,0,0))


def breathe(colors):
    global stop_animation
    global strip

    paint_with_colors(colors)

    while not stop_animation:
        # Increase brightness from 155 -> 255 (breathe upswing)
        for i in range(1, 128):
            strip.setBrightness(int(i))
            strip.show()
            time.sleep(1/1000)
        # Decrease brightness from 254 -> 156 (breathe downswing)
        for i in range(1, 127):
            strip.setBrightness(int(128-i))
            strip.show()
            time.sleep(1/1000)


def twinkle(colors, pct_lit=.3):
    global strip
    seed(14)

    tupleys = convert_to_rgb(colors)
    pixel_list = list(range(0, strip.numPixels()))
    indices_and_tupleys = dict({})

    for i in range(int(strip.numPixels() * pct_lit)):
        pixel_list_index = randint(0, len(pixel_list) - 1)
        scaled_light_index = pixel_list.pop(pixel_list_index)
        random_color_index = randint(0, len(tupleys) - 1)
        indices_and_tupleys.update({scaled_light_index : tupleys[random_color_index]})

    for pixel, color in indices_and_tupleys.items():
        red, green, blue = color
        strip.setPixelColor(pixel, Color(green, red, blue))
        strip.show()

    while not stop_animation:
        for _ in indices_and_tupleys.keys():
            off_index_of_dict = randint(0, len(indices_and_tupleys.keys()) - 1)
            off_index = list(indices_and_tupleys.keys())[off_index_of_dict]
            on_index = randint(0, len(pixel_list) - 1)
            on_color_index = randint(0, len(tupleys) - 1)
            red, green, blue = tupleys[on_color_index]

            strip.setPixelColor(off_index, Color(0, 0, 0))
            strip.show()
            pixel_list.append(off_index)

            strip.setPixelColor(on_index, Color(green, red, blue))
            strip.show()
            pixel_list.pop(on_index)


def bridge_fade(old, new, delta, idx, numSteps, step):
    """ Because sometimes you just want to make a truly horrific method signature. """
    # Figure if we're adding or subtracting at the color index (idx -> R, G, or B). New is the
    #   transition's target; old is what we're transitioning from.
    amountToChange = (delta // numSteps) * step
    if new[idx] > old[idx]:
        return old[idx] + amountToChange
    else:
        return old[idx] - amountToChange


def calculate_intermediates(colors, seconds=10):
    intermediate_colors = []
    rgb_colors = convert_to_rgb(colors)
    for i, color in enumerate(rgb_colors):
        # Wrap around to first item when on last index so it goes full-circle smoothly:
        next = (i + 1) % (len(rgb_colors))
        nextColor = rgb_colors[next]

        # Calculate the difference in green, red, and blue:
        diffR = abs(color[0] - nextColor[0])
        diffG = abs(color[1] - nextColor[1])
        diffB = abs(color[2] - nextColor[2])

        # Each "step" will be .2 seconds long; make a Color for each step and put in the array:
        numSteps = seconds * 5
        for currentStep in range(numSteps):
            # '//' -> Integer division to get floor; * currentStep to get progress toward next color per half sec:
            newR = bridge_fade(color, nextColor, diffR, 0, numSteps, currentStep)
            newG = bridge_fade(color, nextColor, diffG, 1, numSteps, currentStep)
            newB = bridge_fade(color, nextColor, diffB, 2, numSteps, currentStep)
            intermediate_colors.append(Color(newG, newR, newB))

    return intermediate_colors


def fade_between(colors):
    global strip

    # Figure a percent to change between colors, then populate an array with
    #   each intermediate color for the length of the full cycle:
    speed = 15
    intermediate_colors = calculate_intermediates(colors)

    while not stop_animation:
        for color in intermediate_colors:
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(1/speed)


def recenter_cell(recenter_left, color, drift_factor):
    global strip

    centerpoint = strip.numPixels() // 2
    left_color = color if recenter_left else DARK_PIXEL
    right_color = DARK_PIXEL if recenter_left else color

    left_pixel = centerpoint if recenter_left else (centerpoint - 7)
    right_pixel = (centerpoint - 7) if recenter_left else centerpoint

    for _ in range(4):
        strip.setPixelColor(left_pixel, left_color)
        strip.setPixelColor(right_pixel, right_color)
        right_pixel = right_pixel + drift_factor
        left_pixel = left_pixel + drift_factor
        strip.show()
        time.sleep(1)


def shift_cells(colors, starting_points, absolute_destination):
    global strip

    if len(starting_points) % 2 == 1:
        drift_factor = 1
    else:
        drift_factor = -1

    # First calculate number on side:
    num_on_side = len(starting_points) // 2
    if drift_factor == -1:
        num_on_side = num_on_side - 1

    logger.info('Total points: {}; {} of which are on this side.'.format(len(starting_points), num_on_side))

    centerpoint = strip.numPixels() // 2
    iteration = len(starting_points)
    moving_right = absolute_destination > centerpoint
    red, green, blue = colors[iteration + 1]
    next_color = Color(green, red, blue)
    left_color = DARK_PIXEL if moving_right else Color()
    right_color = Color(colors[iteration + 1]) if moving_right else DARK_PIXEL

    for i in range(centerpoint, absolute_destination):
        l_change = i + 4 if moving_right else i - 4
        r_change = i - 4 if moving_right else i + 4
        strip.setPixelColor(l_change, left_color)
        strip.setPixelColor(r_change, right_color)
        strip.show()
        time.sleep(.75)


def drift_to_centerpoint(colors, starting_points, iteration):
    global strip

    if len(starting_points) % 2 == 1:
        drift_factor = 1
    else:
        drift_factor = -1

    centerpoint = int(strip.numPixels() // 2)
    # At this point, the central cell will have r = 15 and will split at 7 and 8:
    denominator = (iteration // 2) + 1
    relative_destination = (centerpoint // denominator) * drift_factor
    absolute_destination = centerpoint + relative_destination

    # Write split logic here. Centerpoint goes dark first, then begin shifting to dest:
    strip.setPixelColor(centerpoint, DARK_PIXEL)
    strip.show()

    shift_cells(colors, starting_points, absolute_destination, iteration)

    recenter_left = absolute_destination > centerpoint

    red, green, blue = colors[0]
    center_color = Color(green, red, blue)

    recenter_cell(recenter_left, center_color, drift_factor)


def exec_growth_phase(colors, starting_points, phase):
    global strip

    # Call and set the 2 lights outside of the current cells
    #   each time, then show once all pixels have been set:
    logger.info('starting_points: {}'.format(starting_points))
    for point_idx, point in enumerate(starting_points):
        # Gonna want to set the pixels that are at point +
        upper_pixel = point + phase
        lower_pixel = point - phase

        logger.info('point_idx: {}'.format(point_idx))
        logger.info('Color at point_idx {}: {}'.format(point_idx, colors[point_idx]))
        red, green, blue = colors[point_idx]
        current_color = Color(green, red, blue)

        strip.setPixelColor(upper_pixel, current_color)
        strip.setPixelColor(lower_pixel, current_color)
    strip.show()


def grow_cell(colors, starting_points):
    telephase_radius = 15 # Only for the first; each len(starting_points) tr -= 2
    # Revise; this will send a negative number for the first phase
    for phase in range(1,telephase_radius,2):
        exec_growth_phase(colors, starting_points, phase)
        time.sleep(1)


def get_starting_points(colors, num_children):
    # starting_points -> centerpoints of each eventual color.
    #   min: 3; max: 296.    Get these by rounding ideal fractional positions.
    starting_points = []
    # Could make this using numpy's arange.. probably inefficient
    #   BOOKMARK! Figure out how to calculate evenly distributed cells for the current step
    pixels_on_side = strip.numPixels() // 2
    children_on_side = num_children // 2 if num_children >= 2 else 1


    for i in range(num_children):
        point = (strip.numPixels() // len(colors)) * i
        starting_points.append(point)
    return starting_points


def meiosis(colors):
    global strip
    # Make 1 large ball of a color, then split it as it grows, changing color each time
    centerpoint = strip.numPixels() // 2

    if type(colors[0]) == str:
        # Extracting ints from RgbColor object, which stores them as strings:
        rgb_tuples = convert_to_rgb(colors)
    else:
        rgb_tuples = colors

    logger.info('Converted rgb_tuples: {}, Centerpoint: {}'.format(rgb_tuples, centerpoint))
    red, green, blue = rgb_tuples[0]


    while not stop_animation:
        strip.setPixelColor(centerpoint, Color(green, red, blue))

        for iteration in range(1, len(colors)):
            starting_points = get_starting_points(colors, iteration)
            grow_cell(rgb_tuples, starting_points)
            drift_to_centerpoint(colors, starting_points)

        fastWipe()



def run():
    global logger
    global strip
    global scene
    global stop_animation

    # Process arguments:
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create the logger:
    logger = configure_logger(LOGGER_NAME, LOG_LOCATION, logging.DEBUG)
    logger.debug('Press Ctrl-C to quit.')
    if not args.clear:
        logger.debug('Use "-c" argument to clear LEDs on exit')


    await_msgs = True
    strip = None

    try:
        # Serve up the gRPC server & wait for messages to arrive:
        import Pi.executor_server as server
        server.serve()
    except KeyboardInterrupt:
        if args.clear:
            fastWipe()
        sys.exit(0)
    except Exception as e:
        # Log the exception as it is on arrival:
        logger.debug(e)
        exc_info = sys.exc_info()

        # Display the *original* exception in the console:
        traceback.print_exception(*exc_info)
        del exc_info
        # "Turn off" the strip if the -c argument was provided before exiting:
        if args.clear:
            fastWipe()
        sys.exit(0)



if __name__ == "__main__":
    run()