import uuid
import os

class Video():
    def __init__(self, tmp="/media/usb/tmp/images", dest="/media/usb/images"):
        self.source = tmp
        self.destination = dest

    def gif(self, fps):
        return self.timelapse(fps, "gif")

    def mp4(self, fps):
        return self.timelapse(fps, "mp4")

    def timelapse(self, fps, format):
        # Get UUID
        image_id = str(uuid.uuid4())[:8]

        # Execute FFMPEG silent, to convert list of images into a gif
        result = os.system("ffmpeg -hide_banner -loglevel error -y -f image2 -r "+ str(fps) + " -i " + self.source + "/timelapse_%d.jpg " + self.source + "/timelapse_" + image_id + "." + format)
        os.rename(self.source + "/timelapse_" + image_id + "." + format, self.destination + "/timelapse_" + image_id + "." + format)
        filename = "timelapse_" + image_id + "." + format
        return result, filename
