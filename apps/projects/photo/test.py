import subprocess
import os
import sys
import time
sys.path.append("../../libraries")
from system.manager import System
system = System(update=True)

os.system("cvlc --quiet --loop /media/usb/images/timelapse_eff728ab.mov")
#time.sleep(2)
#pid = system.getPID("vlc")
#os.system("kill -9 " + str(pid))

