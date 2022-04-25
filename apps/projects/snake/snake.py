#https://machinelearningprojects.net/snake-game-in-python/

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
import imutils

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

# define a video capture object
vid = cv2.VideoCapture(0)
vid.set(3,320)
vid.set(4,240)
cv2.namedWindow("Output", cv2.WND_PROP_FULLSCREEN)
cv2.resizeWindow("Output", 640, 480)
cv2.setWindowProperty("Output", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

frame = ""

#PAGE='<html><body><img id="stream" src="stream.mjpg" width="' + str(320) + '" height="' + str(240) +'" /></body></html>'
PAGE="""
    <html><body><img id="stream" src="stream.mjpg" width="' + str(320) + '" height="' + str(240) +'" /></body>
    <script>
    setInterval(function() {
    var myImg = document.getElementById('stream');
    myImg.src = '/stream.mjpg';
    }, 500);
    </script>
    </html>
"""

address = ('', 8000)
server = StreamingServer(address, StreamingHandler)
thread_stream = threading.Thread(target=server.serve_forever, daemon=True)
thread_stream.start()

score = 0
max_score=20
list_capacity = 0
max_lc =20
l = []
flag=0
apple_x = None
apple_y = None
center = None
prev_c = None
# distance function
def dist(pt1,pt2):
    return np.sqrt((pt1[0]-pt2[0])**2 + (pt1[1]-pt2[1])**2)


while(True):
    # Capture the video frame
    # by frame
    ret, frame = vid.read()
    img = frame
    img = cv2.GaussianBlur(img,(11,11),0)
    img = cv2.cvtColor(img,cv2.COLOR_BGR2HSV)

    if apple_x is None or apple_y is None:
        # assigning random coefficients for apple coordinates
        apple_x = np.random.randint(30,frame.shape[0]-30)
        apple_y = np.random.randint(100,240)
    cv2.circle(frame,(apple_x,apple_y),3,(0,0,255),-1)

    # change this range acc to your need
    greenLower = (29, 86, 18)
    greenUpper = (93, 255, 255)

    # masking out the green color
    mask = cv2.inRange(img,greenLower,greenUpper)
    mask = cv2.erode(mask,None,iterations=2)
    mask = cv2.dilate(mask,None,iterations=2)

    # find contours
    cnts = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)


    if len(cnts)>0:
        ball_cont = max(cnts,key=cv2.contourArea)
        (x,y),radius = cv2.minEnclosingCircle(ball_cont) # find the minimum enclosing circle about the found contour 

        M = cv2.moments(ball_cont)
        center = (int(M['m10']/M['m00']),int(M['m01']/M['m00']))

        if radius>10:
            cv2.circle(frame,center,2,(0,0,255),3)

            if len(l)>list_capacity:
                l = l[1:]

            if prev_c and (dist(prev_c,center) >3.5):
                l.append(center)

            apple = (apple_x,apple_y)
            if dist(apple,center)<5:
                score+=1
                if score==max_score:
                    flag=1
                list_capacity+=1
                apple_x = None
                apple_y = None

    for i in range(1,len(l)):
        if l[i-1] is None or l[i] is None:
            continue
        r,g,b = np.random.randint(0,255,3)

        cv2.line(frame,l[i],l[i-1],(int(r),int(g),int(b)), thickness = int(len(l)/max_lc+2)+2)

    cv2.putText(frame,'Score :'+str(score),(100,100),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,203),2)
    if flag==1:
        cv2.putText(frame,'YOU WIN !!',(0,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2)
    ready_frame = frame
    cv2.imshow('Output', frame)
    prev_c = center
    # the 'q' button is set as the
    # quitting button you may use any
    # desired button of your choice
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# After the loop release the cap object
vid.release()
# Destroy all the windows
cv2.destroyAllWindows()
