import sys
sys.path.append("/media/usb/apps/libraries")
from mqttapi.client import MQTTAPI

# import the opencv library
import cv2
import numpy as np
from gpiozero import Button
import uuid
import time

from http import server
import socketserver
import logging
import io
from threading import Condition
import threading

# Clear terminal (remove all xinit debug)
print("\033c", end="")

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        print("Get")
        global ready_frame
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
        elif self.path.startswith('/stream.mjpg'):
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    (flag, encodedImage) = cv2.imencode(".jpg", ready_frame)
                    byte_encodedImage = bytearray(encodedImage)
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(byte_encodedImage))
                    self.end_headers()
                    self.wfile.write(byte_encodedImage)
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

def color_name_to_array(color_name, value=1):
    if color_name == "blue":
        return (value,0,0)
    elif color_name == "red":
        return (0,0,value)
    elif color_name == "black":
        return (0,0,0)
    elif color_name == "white":
        return (value,value,value)
    elif color_name == "green":
        return (0,value,0)
    elif color_name == "cyan":
        return (value,value,0)
    elif color_name == "purple":
        return (value,0,value)
    elif color_name == "yellow":
        return (0,value,value)
    else:
        return (value,value,value)

def canny_edge(frame, color_name="white", background_color_name="black", offset=0.33, sigma=0.33):
    """
        Prepare images for Canny Filter
    """
    # Convert image to Gray
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Convert Grey image to blurred image
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    # Compute the median of the single channel pixel intensities
    v = np.median(blurred) - offset

    """
        Apply Canny Filter
    """

    # apply automatic Canny edge detection using the computed median
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    edged = cv2.Canny(blurred, lower, upper)

    # Convert result back to RGB to display
    frame = cv2.cvtColor(edged, cv2.COLOR_BGR2RGB)
    # Change color to red
    frame *= np.array(color_name_to_array(color_name),np.uint8)
    frame = background_color(frame, background_color_name)
    return frame

def background_color(frame, color_name="black"):
    if color_name != "black":
        color = color_name_to_array(color_name, value=255)
        Conv_hsv_Gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret, mask = cv2.threshold(Conv_hsv_Gray, 0, 255,cv2.THRESH_BINARY_INV |cv2.THRESH_OTSU)
        frame[mask == 255] = color
    return frame

def laplacian(frame, ksize=3):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    grad_lap = cv2.Laplacian(frame,cv2.CV_16S,ksize=ksize)
    frame = cv2.convertScaleAbs(grad_lap)
    frame *= np.array((1,1,1), np.uint8)
    cv2.normalize(frame, frame, 255, 0, cv2.NORM_MINMAX)
    return frame

def median_blur(frame):
    frame = cv2.medianBlur(frame, 31)
    return frame


# define a video capture object
vid = cv2.VideoCapture(0)
vid.set(3,320)
vid.set(4,240)
cv2.namedWindow("Output", cv2.WND_PROP_FULLSCREEN)
cv2.resizeWindow("Output", 640, 480)
cv2.setWindowProperty("Output", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

mode_name = ["Canny", "Laplacian", "Median", "Original"]
frame = ""
preview_image = False
prepare_record = False
record_image = False
filename = ""
mode = 2

def countdown(message, nb):
    global preview_image
    for x in range(nb, 0, -1):
        preview_image = str(x)
        time.sleep(1)

def take_picture():
    global preview_image, filename, prepare_record
    countdown("",mqttapi.get("apps/timer"))
    print("Taking picture...")
    preview_image = False
    prepare_record = True
    time.sleep(1)
    print("Show image name")
    preview_image = filename
    time.sleep(5)
    preview_image = False

def change_mode():
    global mode
    print("Mode changed")
    if(mode < 3):
        mode+=1
        print(mode_name[mode])
    else:
        mode = 0

gpio = [17, 16, 23, 24]
button1 = Button(17)
button2 = Button(22)
button3 = Button(23)
button4 = Button(27)

button1.when_pressed = take_picture
button2.when_pressed = change_mode

#PAGE='<html><body><img id="stream" src="stream.mjpg" width="' + str(320) + '" height="' + str(240) +'" /></body></html>'
PAGE="""
<html>
    <body
        style="background-image: url(\'stream.mjpg\');
        height: 100%;
        background-position: center;
        background-repeat: no-repeat;
        background-size: cover;" >
    </body>
</html>
"""

address = ('', 8000)
server = StreamingServer(address, StreamingHandler)
thread_stream = threading.Thread(target=server.serve_forever, daemon=True)
thread_stream.start()

mqttapi = MQTTAPI()
mqttapi.set_default("apps/timer", 3)
mqttapi.set_default("apps/effects", "comics")
mqttapi.set_default("apps/mode", "photo")
mqttapi.set_default("apps/color", "white")
mqttapi.set_default("apps/background_color", "black")
mqttapi.set_default("apps/comics_line", 10)
mqttapi.set_default("apps/matrix_line", 3)
mqttapi.run()

while(True):
    # Capture the video frame
    # by frame
    ret, frame = vid.read()

    if mqttapi.get("apps/effects") == "matrix":
        frame = laplacian(frame, ksize = mqttapi.get("apps/matrix_line"))
        frame *= np.array(color_name_to_array(mqttapi.get("apps/color")),np.uint8)
        frame = background_color(frame, color_name = mqttapi.get("apps/background_color"))
    elif mqttapi.get("apps/effects") == "comics":
        frame = canny_edge(frame, color_name = mqttapi.get("apps/color"), background_color_name = mqttapi.get("apps/background_color"), offset = mqttapi.get("apps/comics_line"))
        #frame = cv2.bitwise_not(frame)
    elif mqttapi.get("apps/effects") == "colored_comics":
        #frame1 = laplacian(frame)
        frame1 = canny_edge(frame, color_name = mqttapi.get("apps/color"), offset = mqttapi.get("apps/comics_line"))
        frame2 = median_blur(frame)
        frame = cv2.add(frame2,frame1)
    elif mqttapi.get("apps/effects") == "none":
        pass

        #frame = cv2.addWeighted(frame1, 0.5, frame2, 0.5, 0)
    ready_frame = frame
    if prepare_record == True and record_image == False:
        vid.set(3,1152)
        vid.set(4,864)
        record_image = True
        prepare_record = False
    elif prepare_record == False and record_image == True:
        print("Record image")
        filename = "photo" + str(uuid.uuid4())[:8] + ".jpg"
        cv2.imwrite("/media/usb/images/" + filename, frame)
        record_image = False
        vid.set(3,320)
        vid.set(4,240)

    if preview_image != False:
        cv2.putText(frame,
                    str(preview_image),
                    (0,128),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    5,
                    (255,0,0,255),
                    5)

    cv2.imshow('Output', ready_frame)
    # the 'q' button is set as the
    # quitting button you may use any
    # desired button of your choice
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# After the loop release the cap object
vid.release()
# Destroy all the windows
cv2.destroyAllWindows()
