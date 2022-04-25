"""
📷 Pilaroid Photo by µsini - Rémi Sarrailh <remi@usini.eu>
📕 Picamera  - https://picamera.readthedocs.io/en/latest/recipes1.html#overlaying-images-on-the-preview
📕 GPIO Zero - https://gpiozero.readthedocs.io/en/stable/recipe GPIO Zero
📕 QRCode    - https://pypi.org/project/qrcode/

"""

import sys
from PIL import Image
#from isort import file
import picamera
import uuid
import time
import os
import qrcode
from gpiozero import Button
from http import server
import socketserver
import logging
import io
from threading import Condition
from threading import Thread

sys.path.append("../../libraries")
from mqttapi.client import MQTTAPI
from system.manager import System
from converter.video import Video
from converter.panorama import Hugin_Panorama

system = System(update=True)
converter = Video(tmp= system.tempImagesFolder(), dest=system.imagesFolder())
pano = Hugin_Panorama()
resolution = system.getResolution()
resolution_string = system.getResolutionString()
information_n = 0

# Images Overlays
qrcode_toggle = False # Is QRCode enabled
qrcode_overlay = None # QRCode Overlay
mode_overlay = None   # Active Mode Overlay
tmp_o = None

take_picture_now = False
preview = False
pano_state = 0

camera = None
output = None

# Buttons GPIO
gpio_braincraft = [17, 16, 23, 24]
gpio_adafruit_tft_buttons = [17,22,23,27]

# Control mode and timer from web
def callback_mqttapi(topic, message):
    global capture_type
    print("Topic is " + topic)
    if topic == "apps/mode":
        capture_type = message
        print("Change mode to: " + capture_type)
        change_mode()
    if topic == "apps/timer":
        annotate_timed("Timer: " + str(mqttapi.get("apps/timer")))
    if topic == "apps/action":
        if message == "take":
            take_picture()

# Start a thread to display text on screen
def annotate_timed(message):
    global annotate_thread
    annotate_thread = Thread(target= annotate_timed_thread, args=(message,))
    annotate_thread.start()

# Display text on screen for a timed period (threaded)
def annotate_timed_thread(message):
    global camera
    camera.annotate_text = "\n" + message
    time.sleep(3)
    camera.annotate_text = ""

# Display a countdown on screen / stream
def countdown(message, nb):
    for x in range(int(nb), 0, -1):
        camera.annotate_text = "\n" + message + " - " + str(x)
        time.sleep(1)
    camera.annotate_text = ""

# Erase all files in the temp folder
def clean_temp(path):
    if(len(os.listdir(path)) != 0):
            for img in os.listdir(path):
                print("Effacement " + path + img)
                os.remove(path + img)

# Create an overlay of the last image taken for the panorama
def pano_align_overlay(source, alignimage):
    global camera
    previous_pan = Image.open(source)
    previous_pan = previous_pan.resize((320,240))
    previous_pan = previous_pan.crop((280,0,320,240))
    previous_pan.save(alignimage)
    previous_pan_temp = Image.new(mode="RGBA", size=(320,240))
    previous_pan_temp.paste(previous_pan, (0,0))
    previous_pan_temp.save(alignimage)
    overlay_align = create_overlay(alignimage, layer=3,format="RGB", alpha=128)
    return overlay_align

def photo():
    global camera
    countdown("Photo", mqttapi.get("apps/timer")) #FROM MQTT
    filename = "photo" + str(uuid.uuid4())[:8] + ".jpg"
    camera.capture("/media/usb/images/" + filename)
    mqttapi.set("apps/action", "none")

    annotate_timed(filename)
    overlay_preview = create_overlay("/media/usb/images/" + filename, 3)
    time.sleep(3)
    camera.remove_overlay(overlay_preview)

def timelapse(nb=50, speed=0.1):
    global camera, preview, filename

    countdown("Timelapse", mqttapi.get("apps/timer")) #FROM MQTT

    for i in range(0,nb):
        print("TIMELAPSE:" + str(i))
        camera.annotate_text = ""
        camera.capture("/media/usb/tmp/images/timelapse_" + str(i) + ".jpg")
        camera.annotate_text = "\n" + str(i+1) + "/" + str(nb)
        time.sleep(speed)

    mqttapi.set("apps/action", "none")
    camera.annotate_text = "\n" + "Conversion"
    result, filename = converter.timelapse(fps=25,format="mov")
    system.cleanTemp()
    camera.annotate_text = "\n" + "Preview"
    camera.stop_preview()
    os.system("cvlc --quiet --loop /media/usb/images/" + filename + " &")
    print("cvlc --quiet --loop /media/usb/images/" + filename + " &")

    preview = True

def panorama():
    global camera, pano_state, tmp_o
    if pano_state == 0:
        camera.capture("/media/usb/tmp/images/pano_left.jpg")
        tmp_o = pano_align_overlay("/media/usb/tmp/images/pano_left.jpg", "/media/usb/tmp/images/pano_left_temp.png")
        pano_state = 1
    elif pano_state == 1:
        camera.remove_overlay(tmp_o)
        camera.capture("/media/usb/tmp/images/pano_center.jpg")
        tmp_o = pano_align_overlay("/media/usb/tmp/images/pano_center.jpg", "/media/usb/tmp/images/pano_center_temp.png")
        pano_state = 2
    elif pano_state == 2:
        camera.remove_overlay(tmp_o)
        camera.capture("/media/usb/tmp/images/pano_right.jpg")
        mqttapi.set("apps/action", "none")

        print("JOIN IMAGES")
        camera.annotate_text = "\n Conversion"
        filename = "/media/usb/images/pano" + str(uuid.uuid4())[:8] + ".jpg"
        pano.advanced_workflow(filename)
        #os.system('/usr/bin/nona -o '+filename+' -m JPEG "/media/usb/apps/libraries/converter/pto/3images.pto" "/media/usb/tmp/images/pano_left.jpg" "/media/usb/tmp/images/pano_center.jpg" "/media/usb/tmp/images/pano_right.jpg"')
        overlay_preview = create_overlay(filename, 3)
        time.sleep(3)
        camera.remove_overlay(overlay_preview)
        camera.annotate_text = "\n" + filename
        system.cleanTemp()
        time.sleep(3)
        camera.annotate_text = ""
        pano_state = 0

filename = ""
# Take a picture / timelapse or panorama
def take_picture():
    global camera,capture_type, filename, preview

    if preview:
        preview = False
        pid = system.getPID("vlc")
        if pid != "null":
            os.system("kill -9 " + system.getPID("vlc"))
            print("kill -9 " + system.getPID("vlc"))
        camera.start_preview()
        camera.annotate_text = "\n" + filename
        time.sleep(3)
        camera.annotate_text = ""
        return True

    if capture_type == "photo":
        photo()
    elif capture_type == "timelapse":
        timelapse()
    elif capture_type == "panorama":
        panorama()

# Change mode of the camera (using buttons)
def switch_mode():
    print("Switching Mode")
    global capture_type, capture_type_nb
    if(capture_type_nb >= len(capture_type_name) - 1):
        capture_type_nb = 0
    else:
        capture_type_nb += 1
    print("Capture type changed")
    mode = capture_type_name[capture_type_nb]

    mqttapi.set("apps/mode", mode) #From MQTT

# Change mode of the camera (using mqtt)
def change_mode():
    global camera, capture_type, mode_overlay
    print("Change mode to " + capture_type)
    camera.remove_overlay(mode_overlay)
    mode_overlay = create_overlay("overlays/mode_" + capture_type + ".png",3)

    if(capture_type == "photo"):
        annotate_timed("Photo")
    elif(capture_type == "timelapse"):
        annotate_timed("Timelapse")
    elif(capture_type == "panorama"):
        annotate_timed("Panorama")

# Display QRCode or Network Information
def information_switch():
    global camera, information_n, qrcode_toggle, qrcode_overlay
    qrcode_toggle = not qrcode_toggle
    if qrcode_toggle:
        qrcode_overlay = create_qrcode(system.getIP())
    else:
        camera.remove_overlay(qrcode_overlay)

# Generate a qrcode with the IP
def create_qrcode(ip):
    img = qrcode.make("http://" + ip)
    img = img.save("overlays/qrcode.png", format="png")
    qrcode_overlay = create_overlay("overlays/qrcode.png", 3)
    return qrcode_overlay

# Create an overlay based on an image
def create_overlay(image, layer, format="RGBA", alpha=255):
    img = Image.open(image)
    pad = Image.new(format, (
            ((img.size[0] + 31) // 32) * 32,
            ((img.size[1] + 15) // 16) * 16,
            ))
    pad.paste(img, (0, 0))
    o = camera.add_overlay(pad.tobytes(), size=pad.size)
    #print(alpha)
    o.alpha = alpha
    o.layer = layer
    return o

# Streaming video

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()
class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# Streaming Page
#PAGE='<html><body><img id="stream" src="stream.mjpg" style="width=100%; height:100%;" /></body></html>'

PAGE='<html><body style="background-image: url(\'stream.mjpg\'); height: 100%; background-position: center; background-repeat: no-repeat; background-size: cover;" ></body></html>'

#  Buttons
button1 = Button(17)
button2 = Button(22)
button3 = Button(23)
button4 = Button(27)

# Main Program
system.cleanTemp() # Clear temp folder
button1.when_pressed = take_picture # Take Picture when button 1 pressed
button2.when_pressed = switch_mode  # Switch mode when button 2 pressed
button3.when_pressed = information_switch # Display QRCode when button 3 pressed

# Camera Loop
with picamera.PiCamera(resolution=resolution_string, framerate=24) as camera:
    # Get settings and generate API
    mqttapi = MQTTAPI(password="pilaroid", message_callback=callback_mqttapi)
    mqttapi.set_default("apps/timer", 3)
    mqttapi.set_default("apps/mode", "photo")

    capture_type_name = ["photo", "timelapse", "panorama"]
    capture_type =  mqttapi.get("apps/mode") # 0 Photo / 1 Gif
    capture_type_nb = capture_type_name.index(capture_type)

    # Image Overlay
    create_overlay("overlays/overlay.png",0) # Turn black overlay to hide command line
    create_overlay("overlays/record.png",3)  # Add Record button
    create_overlay("overlays/qrcode_icon.png",3) # Create qrcode overlay

    mode_overlay = create_overlay("overlays/mode_" + capture_type + ".png",3) # Add Mode button

    mqttapi.run()

    # Text Overlay
    camera.annotate_text_size = 160
    camera.annotate_background = picamera.Color('black')
    #camera.rotation = 180

    # Streaming
    output = StreamingOutput()

    # Create preview on TFT Screen
    camera.start_preview()

    # Prepare recording for streaming
    camera.start_recording(output, format='mjpeg')
    #camera.annotate_text = ""

    # Generate streaming server
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        print("Gracefully quit")
        mqttapi.client.publish("system/app", "none", retain=True)
        camera.stop_recording()
