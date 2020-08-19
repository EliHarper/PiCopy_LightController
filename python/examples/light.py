#!/usr/bin/env python3

# Built from direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.
from neopixel import *
import animations
import argparse
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

def fastWipe(strip, color=DARK_PIXEL):
    """Wipe color REAL QUICK across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)

    strip.show()


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

# Personal Additions: #

# Helpers:
class Delta:
    def __init__(self, range, rate, increase=True):
        self.range = range
        self.rate = rate
        self.increase = increase


def convert_to_rgb(colors):
    tupleys = []
    for hex_color in colors:
        hex_color = hex_color.lstrip('#')
        tupleys.append(tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)))

    return tupleys

# Action functions:
# Administrative:
def create_kafka_consumer():
    return KafkaConsumer(
        'applyScene',
        bootstrap_servers=[config('KAFKA_URL')],
        value_deserializer=lambda x: loads(x.decode('utf-8')),
        api_version=(0,10,1)
    )


def make_strip(brightness):
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, int(brightness), LED_CHANNEL)
    return strip


def animation_handler(strip, colors, animation):
    global stop_animation
    while not stop_animation:
        switcher = {
            "Projectile": fire_projectiles,
            "Breathe": breathe,
            "Twinkle": twinkle,
            "Fade": fade_between,
            "Meiosis": meiosis
        }
        switcher[animation](strip, colors)


def handle_ending_animation(strip, message):
    global stop_animation
    # Short-circuit in the event of a "turn off" message:
    if message['functionCall'] == "off":
        if strip is not None:
            stop_animation = True
            scene.join()
            fastWipe(strip, Color(0,0,0))
            stop_animation = False
            # Returning False tells the main loop to just wait for the next message
            #   instead of handling it further as if it were a scene
            return False
    elif message['functionCall'] == 'update_brightness':
        print("UPDATING BRIGHTNESS TO: {}".format(message['value']))
        strip.setBrightness(int(message['value']))
        strip.show()
        return False
    else:
        try:
            # Check if the changed-to scene is the same as the last - if not, tell the thread to end.
            if prev_message['_id']['$oid'] == message['_id']['$oid']:
                # Don't bother with re-applying the same scene:
                return False
            else:
                if prev_message['animated']:
                    # Tell animated function to end, then wait for it to do so before continuing.
                    stop_animation = True
                    scene.join()
                    stop_animation = False

                return True
        # If animation_id is unset (first animation since app start), initialize stop_animation to False:
        except NameError:
            stop_animation = False
            return True


# Scenes:
def paint_with_colors(strip, colors):
    # Accept color as hex
    print('Setting solid color to: {}'.format(colors))

    if type(colors[0]) == str:
        # Extracting ints from RgbColor object, which stores them as strings:
        rgb_tuples = convert_to_rgb(colors)
    else:
        rgb_tuples = colors

    range_per_color = strip.numPixels() / len(rgb_tuples)
    range_per_color = int(range_per_color)
    rgb_tuple_index = 0

    for i in range(strip.numPixels()):
        # Make the strip show even(ish) amounts of each color, with remainder applied to last color
        if i % range_per_color == 0 and rgb_tuple_index < len(rgb_tuples):
            red, green, blue = rgb_tuples[rgb_tuple_index]
            rgb_tuple_index += 1
            # No idea why, but this function accepts in format GRB..
        strip.setPixelColor(i, Color(green, red, blue))
        strip.show()


def fire_projectiles(strip, colors, projectile_size=8):
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


def breathe(strip, colors):
    global stop_animation
    paint_with_colors(strip, colors)

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


def twinkle(strip, colors, pct_lit=.3):
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
        print('next: {}'.format(next))
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


def fade_between(strip, colors):
    # Figure a percent to change between colors, then populate an array with
    #   each intermediate color for the length of the full cycle:
    speed = 15
    intermediate_colors = calculate_intermediates(colors)
    print('fade_between')

    while not stop_animation:
        for color in intermediate_colors:
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(1/speed)


def recenter_cell(strip, recenter_left, color, drift_factor):
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


def shift_cells(strip, colors, starting_points, absolute_destination):
    if len(starting_points) % 2 == 1:
        drift_factor = 1
    else:
        drift_factor = -1

    # First calculate number on side:
    num_on_side = len(starting_points) // 2
    if drift_factor == -1:
        num_on_side = num_on_side - 1

    print('Total points: {}; {} of which are on this side.'.format(len(starting_points), num_on_side))

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


def drift_to_centerpoint(strip, colors, starting_points):
    if len(starting_points) % 2 == 1:
        drift_factor = 1
    else:
        drift_factor = -1

    centerpoint = int(strip.numPixels() // 2)
    # At this point, the central cell will have r = 15 and will split at 7 and 8:
    denominator = len(starting_points) + 1
    relative_destination = (centerpoint // denominator) * drift_factor
    absolute_destination = centerpoint + relative_destination

    # Write split logic here. Centerpoint goes dark first, then begin shifting to dest:
    strip.setPixelColor(centerpoint, DARK_PIXEL)
    strip.show()

    shift_cells(strip, colors, starting_points, absolute_destination)

    recenter_left = absolute_destination > centerpoint

    red, green, blue = colors[0]
    center_color = Color(green, red, blue)

    recenter_cell(strip, recenter_left, center_color, drift_factor)


def exec_growth_phase(strip, colors, starting_points, phase):
    # Call and set the 2 lights outside of the current cells
    #   each time, then show once all pixels have been set:
    print('starting_points: {}'.format(starting_points))
    for point_idx, point in enumerate(starting_points):
        # Gonna want to set the pixels that are at point +
        upper_pixel = point + phase
        lower_pixel = point - phase

        print('point_idx: {}'.format(point_idx))
        print('Color at point_idx {}: {}'.format(point_idx, colors[point_idx]))
        red, green, blue = colors[point_idx]
        current_color = Color(green, red, blue)

        strip.setPixelColor(upper_pixel, current_color)
        strip.setPixelColor(lower_pixel, current_color)
    strip.show()
    time.sleep(1)


def grow_cells(strip, colors, starting_points):
    telephase_radius = 15 # Only for the first; each len(starting_points) tr -= 2
    # Revise; this will send a negative number for the first phase
    for phase in range(1,telephase_radius,2):
        exec_growth_phase(strip, colors, starting_points, phase)


def get_starting_points(strip, colors):
    starting_points = []
    for i in range(len(colors)):
        point = (strip.numPixels() // len(colors)) * i
        starting_points.append(point)
    return starting_points


def meiosis(strip, colors):
    # Make 1 large ball of a color, then split it as it grows, changing color each time
    centerpoint = strip.numPixels() // 2

    if type(colors[0]) == str:
        # Extracting ints from RgbColor object, which stores them as strings:
        rgb_tuples = convert_to_rgb(colors)
    else:
        rgb_tuples = colors

    print('Converted rgb_tuples: {}, Centerpoint: {}'.format(rgb_tuples, centerpoint))
    red, green, blue = rgb_tuples[0]
    starting_points = get_starting_points(strip, colors)

    while not stop_animation:
        strip.setPixelColor(centerpoint, Color(green, red, blue))
        # iteration is a 1-based index of # times cell has split
        grow_cells(strip, rgb_tuples, starting_points)
        drift_to_centerpoint(strip, colors, starting_points)
        fastWipe(strip)



def run():
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')

    args = parser.parse_args()

    print('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    consumer = create_kafka_consumer()

    await_msgs = True
    strip = None

    global prev_message
    global scene
    global stop_animation

    while await_msgs:
        try:
            print('while')
            for message in consumer:
                message = message.value
                print(message)
                print(message['functionCall'])

                if not handle_ending_animation(strip, message):
                    break

                if strip is None:
                    strip = make_strip(message['defaultBrightness'])
                    strip.begin()
                else:
                    strip.setBrightness(int(message['defaultBrightness']))

                if message['animated']:
                    scene = threading.Thread(target = animation_handler, args=(strip, message['colors'], message['animation']))
                else:
                    scene = threading.Thread(target = paint_with_colors, args=(strip, message['colors']))

                scene.start()
                prev_message = message


        except KeyboardInterrupt:
            if args.clear:
                fastWipe(strip, Color(0, 0, 0))
            sys.exit(0)
        except Exception as e:
            print(e)
            exc_info = sys.exc_info()
            # Display the *original* exception
            traceback.print_exception(*exc_info)
            del exc_info
            if args.clear:
                fastWipe(strip, Color(0, 0, 0))
            sys.exit(0)



if __name__ == "__main__":
    run()