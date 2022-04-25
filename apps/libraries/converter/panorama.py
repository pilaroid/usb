"""
📚 Pilaroid Libraries - Converter/Panorama
🧑 Author : µsini (Rémi Sarrailh - remi@usini.eu)
❓  Panorama Stitcher
📕 Source : https://www.pyimagesearch.com/2018/12/17/image-stitching-with-opencv-and-python/
"""

import numpy as np
import imutils
import cv2
import os

class Hugin_Panorama():
    def __init__(self, images_dir="/media/usb/images", temp="/media/usb/tmp", workflow="advanced"):
        self.status= -1
        self.images_dir = images_dir
        self.temp = temp
        self.workflow = workflow
        self.pto_temp = self.temp + "/temp_pano.pto "
        self.images_temp = self.temp + "/images/pano_*.jpg "

    def advanced_workflow(self, filename):
        print("pto_gen -o " + self.pto_temp + self.images_temp)
        os.system("pto_gen -o " + self.pto_temp + self.images_temp)
        print("cpfind -o " + self.pto_temp + "--multirow --celeste " + self.pto_temp)
        os.system("cpfind -o " + self.pto_temp + "--multirow --celeste " + self.pto_temp)
        print("cpclean -o " + self.pto_temp + self.pto_temp)
        os.system("cpclean -o " + self.pto_temp + self.pto_temp)
        print("linefind -o " + self.pto_temp + self.pto_temp)
        os.system("linefind -o " + self.pto_temp + self.pto_temp)
        print("autooptimiser -a -m -l -s -o"+self.pto_temp + self.pto_temp)
        os.system("autooptimiser -a -m -l -s -o"+self.pto_temp + self.pto_temp)
        print("pano_modify --canvas=AUTO --crop=AUTO -o" + self.pto_temp + self.pto_temp)
        os.system("pano_modify --canvas=AUTO --crop=AUTO -o" + self.pto_temp + self.pto_temp)
        print("/usr/bin/nona -o "+ filename +" -m JPEG "+ self.pto_temp)
        os.system("/usr/bin/nona -o "+ filename +" -m JPEG "+ self.pto_temp)

    def simple_workflow(self):
        os.system("pto_gen -o " + self.pto_temp + self.images_temp)
        os.system("hugin_executor --assistant " + self.pto_temp)


class OpenCV_Panorama():
    def __init__(self, debug=False):
        self.status = -1
        self.stitched = None
        self.debug = debug

    def save(self, filename):
        if self.stitched is None:
            return None
        else:
            if(self.debug):
                print("📁 " + filename)
            cv2.imwrite(filename, self.stitched)
            self.stitched = None
            return filename

    # Stitch images using Features Detections
    def join_images(self, images_path):
        images = []
        for image in os.listdir(images_path):
            if(self.debug):
                print("📁 " + images_path + "/" + image)
            images.append(cv2.imread(images_path + "/" + image))

        # Create Stitcher Objects
        stitcher = cv2.Stitcher_create()
        #stitcher.setPanoConfidenceThresh(0.1)

        # Apply Stitcher Algorithm to images
        (self.status, self.stitched) = stitcher.stitch(images)

        # Generate Borders
        self.stitched = cv2.copyMakeBorder(self.stitched, 10, 10, 10, 10, cv2.BORDER_CONSTANT, (0, 0, 0))
        #cv2.imwrite(self.path_temp + stitched_name, self.stitched)
        print(self.status)
    """
    Manual Cropper
    """

    # Crop images to remove black borders
    def crop_images(self, crop_size):
        shape = self.stitched.shape
        self.stitched = self.stitched[crop_size:shape[0]-crop_size, crop_size:shape[1]-crop_size]

    """
    Automatic Cropper
    """
    # Apply a filter to get only Black parts
    # Not used here, as it has a tendency to fail if images has parts which are too dark
    def get_contours(self):
        gray = cv2.cvtColor(self.stitched, cv2.COLOR_BGR2GRAY)
        # cv2.imwrite("/media/usb/images/gray.png", gray)
        self.thres = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)[1]
        cnts = cv2.findContours(self.thres.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        self.c = max(cnts, key=cv2.contourArea)
        # cv2.imwrite(self.path + "temp/threshold.png", self.thres)

    # Get value for the contours
    def set_contours_mask(self):
        self.mask = np.zeros(self.thres.shape, dtype="uint8")
        (x, y, w, h) = cv2.boundingRect(self.c)
        cv2.rectangle(self.mask, (x,y), (x + w, y + h), 255, -1)

    # Apply crop based on contours detection
    def set_contours(self):
        minRect = self.mask.copy()
        sub = self.mask.copy()
        while cv2.countNonZero(sub) > 0:
            minRect = cv2.erode(minRect, None)
            sub = cv2.subtract(minRect, self.thres)

        cnts = cv2.findContours(minRect.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        self.c = max(cnts, key=cv2.contourArea)
        (x, y, w, h) = cv2.boundingRect(self.c)
        self.stitched = self.stitched[y:y + h, x:x + w]
