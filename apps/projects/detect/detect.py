# Copyright 2021 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Main script to run the object detection routine."""
import argparse
import sys
import time
import json
import threading

import cv2
from object_detector import ObjectDetector
from object_detector import ObjectDetectorOptions
import utils

import sys
sys.path.append("/media/usb/apps/libraries")
from mqttapi.client import MQTTAPI
mqttapi = MQTTAPI()
mqttapi.run()

detection_finish = False
detections = ""

### STREAMING ###

from http import server
import socketserver
import logging
import io
ready_frame = ""
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

### STREAMING ###

def detect(detector, image):
    global detection_finish, detections
    if not detection_finish:
      detection_finish = True
      # Run object detection estimation using the model.
      new_detections = detector.detect(image)

      detections_array = []
      for detection in new_detections:
        detection_json = {}
        detection_json["left"] = detection.bounding_box.left
        detection_json["top"] = detection.bounding_box.top
        detection_json["right"] = detection.bounding_box.right
        detection_json["bottom"] = detection.bounding_box.bottom
        detection_json["label"] = detection.categories[0].label
        detection_json["probabibility"] = round(float(detection.categories[0].score),2)
        detections_array.append(detection_json)

      mqttapi.set("apps/detections", json.dumps(detections_array))

      # Draw keypoints and edges on input image
      detections  = new_detections
      detection_finish = False

def run(model: str, camera_id: int, width: int, height: int, num_threads: int,
        enable_edgetpu: bool) -> None:
  """Continuously run inference on images acquired from the camera.

  Args:
    model: Name of the TFLite object detection model.
    camera_id: The camera id to be passed to OpenCV.
    width: The width of the frame captured from the camera.
    height: The height of the frame captured from the camera.
    num_threads: The number of CPU threads to run the model.
    enable_edgetpu: True/False whether the model is a EdgeTPU model.
  """

  # Variables to calculate FPS
  counter, fps = 0, 0
  start_time = time.time()

  # Start capturing video input from the camera
  cap = cv2.VideoCapture(camera_id)
  cap.set(3,320)
  cap.set(4,200)

  # Visualization parameters
  row_size = 20  # pixels
  left_margin = 24  # pixels
  text_color = (0, 0, 255)  # red
  font_size = 1
  font_thickness = 1
  fps_avg_frame_count = 10

  # Initialize the object detection model
  options = ObjectDetectorOptions(
      num_threads=num_threads,
      score_threshold=0.3,
      max_results=3,
      enable_edgetpu=enable_edgetpu)
  detector = ObjectDetector(model_path=model, options=options)

  cv2.namedWindow("Output", cv2.WND_PROP_FULLSCREEN)
  cv2.resizeWindow("Output", 640, 480)
  cv2.setWindowProperty("Output", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

  # Continuously capture images from the camera and run inference
  while cap.isOpened():
    global ready_frame
    success, image = cap.read()
    if not success:
      sys.exit(
          'ERROR: Unable to read from webcam. Please verify your webcam settings.'
      )

    counter += 1
    image = cv2.flip(image, 1)

    threading.Thread(target=detect, args = (detector,image, )).start()
    if detections != "":
      image = utils.visualize(image, detections)
    # Calculate the FPS
    if counter % fps_avg_frame_count == 0:
      end_time = time.time()
      fps = fps_avg_frame_count / (end_time - start_time)
      start_time = time.time()

    # Show the FPS
    fps_text = 'FPS = {:.1f}'.format(fps)
    text_location = (left_margin, row_size)
    cv2.putText(image, fps_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                font_size, text_color, font_thickness)
    #print(fps)
    # Stop the program if the ESC key is pressed.
    if cv2.waitKey(1) == 27:
      break
    cv2.imshow('Output', image)
    ready_frame = image # Streaming

  cap.release()
  cv2.destroyAllWindows()


def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument(
      '--model',
      help='Path of the object detection model.',
      required=False,
      default='efficientdet_lite0.tflite')
  parser.add_argument(
      '--cameraId', help='Id of camera.', required=False, type=int, default=0)
  parser.add_argument(
      '--frameWidth',
      help='Width of frame to capture from camera.',
      required=False,
      type=int,
      default=640)
  parser.add_argument(
      '--frameHeight',
      help='Height of frame to capture from camera.',
      required=False,
      type=int,
      default=480)
  parser.add_argument(
      '--numThreads',
      help='Number of CPU threads to run the model.',
      required=False,
      type=int,
      default=4)
  parser.add_argument(
      '--enableEdgeTPU',
      help='Whether to run the model on EdgeTPU.',
      action='store_true',
      required=False,
      default=False)
  args = parser.parse_args()

  run(args.model, int(args.cameraId), args.frameWidth, args.frameHeight,
      int(args.numThreads), bool(args.enableEdgeTPU))


if __name__ == '__main__':
  main()
