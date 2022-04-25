# System is a libraries to manage Pilaroid system (network/supervisor applications/sdcard write protection/screen)

import subprocess # Use to start bash command
import time # Use for timer
import os # Use to start bash command / file management
import socket # Use to get network info
import urllib.request # Use to check internet connectivity
import configparser # Use to read ini file (supervisor/user settings)
import shutil # file management (copy)
import json

class System():
    def __init__(self, update=True, supervisor_file="/media/usb/apps.conf", settings_file = "/media/usb/settings.ini", secrets_file = "/media/usb/secrets.ini"):

        # Settings file
        self.supervisor_file = supervisor_file # Supervisor file (Where apps started at launch are defined)
        self.settings_file = settings_file # Settings (Peripheral settings)
        self.secrets_file = secrets_file # Secrets (Passwords)

        self.info = {} # System information
        if os.geteuid() == 0:
            self.info["root"] = True # Root
        else:
            self.info["root"] = False # Non Root

        self.info["WiFiConnected"] = -1 # Is WiFi connected ?

        self.info["ssids"] = [] # SSIDS list (need to be refresh manually because it is time consuming)
        self.settings = configparser.ConfigParser() # Prepare settings object
        self.secrets = configparser.ConfigParser() # Prepare secrets object

        self.getSupervisorSettings() # Apps settings loaded here
        self.info["username"] = self.username()
        self.getSettings() # User settings / Secrets loaded here

        self.refresh = update # Do we want to update info (longer startup / useless if you just want settings)

        if(self.refresh):
            self.update()

    """ Settings """
        # Update all information
    def update(self):
        self.getHostname()
        self.getIP()
        self.getSSID()
        self.getWiFi()
        self.getWiFiCountry()
        self.getInternet()
        self.getDevMode()
        self.getApps()
        self.getScreen()

    def username(self):
        try:
            user = os.getlogin()
        except:
            user = "pi"
        return user

    def password(self):
        try:
            return self.secrets["USER"]["password"]
        except:
            return "pilaroid"

    def imagesFolder(self):
        default = "/media/usb/images"
        try:
            if os.path.exists(self.settings["FOLDERS"]["temp"]):
                return self.settings["FOLDERS"]["images"]
            else:
                return default
        except:
            return default

    def tempFolder(self):
        default = "/media/usb/tmp"
        try:
            if os.path.exists(self.settings["FOLDERS"]["temp"]):
                return self.settings["FOLDERS"]["temp"]
            else:
                return default
        except:
            return default

    def tempImagesFolder(self):
        return self.tempFolder() + "/images/"

    def cleanTemp(self):
        tempfolder = self.tempImagesFolder()
        # Erase all files in the temp folder
        if(len(os.listdir(tempfolder)) != 0):
            for img in os.listdir(tempfolder):
                print("Effacement " + tempfolder + img)
                os.remove(tempfolder + img)

    """ Helpers """
    def isJSON(self, jsonData):
        try:
            json.loads(jsonData)
        except ValueError as e:
            return False
        return True

    def isIPv4(self, address):
        try:
            socket.inet_pton(socket.AF_INET, address)
        except AttributeError:  # no inet_pton here, sorry
            try:
                socket.inet_aton(address)
            except socket.error:
                return False
            return address.count('.') == 3
        except socket.error:  # not a valid address
            return False

        return True

    # Get Aspect Ratio from resolution
    def getAspectRatio(self, resolution):
        ratio = resolution[1] / resolution[0]
        if(ratio == 0.5625):
            aspectratio = "16:9"
        elif(ratio == 0.75):
            aspectratio = "4:3"
        else:
            aspectratio = "4:3"
        return aspectratio

    def getPID(self, application_name):
        pid = "null"
        ps_aux = subprocess.check_output(["ps","aux"])
        ps_aux = str(ps_aux).split("\\n")
        for line in ps_aux:
            if application_name in line:
                print(line)
                pid = line.split(" ")[7]
        return pid

    """ System"""

    def reboot(self):
        os.system("sudo /usr/local/bin/power reboot")

    def off(self):
        os.system("sudo /usr/local/bin/power off")

    def getSettings(self):
        #resolution = (320,240) # Screen Resolution
        #resolution = (1280,720) # Screen Resolution
        #resolution = (1856,1392) #Optimal 4:3 Ratio
        #resolution = (960,540)   #Optimal 4 Zone HD
        #resolution = [1920,1080] #HD (crop stream/preview)
        self.settings.read(self.settings_file)
        self.secrets.read(self.secrets_file)
        try:
            self.info["resolution"] = ()
            resolution_string = self.settings["SETTINGS"]["resolution"]
            resolution_array = resolution_string.split("x")
            self.info["resolutionString"] = resolution_string
            self.info["resolution"] = (int(resolution_array[0]), int(resolution_array[1]))
        except:
            self.info["resolutionString"] = "1280x720"
            self.info["resolution"] = (1280,720)

    # get resolution as a tuples
    def getResolution(self):
        return self.info["resolution"]

    #get resolution as a string (as used by picamera)
    def getResolutionString(self):
        return self.info["resolutionString"]

    # Load supervisor ini file
    def getSupervisorSettings(self):
        self.supervisor = configparser.ConfigParser()
        self.supervisor.read("/media/usb/apps.conf")

    # Get application list from config file
    def getApps(self):
        self.info["current_app"] = self.supervisor["program:app"]["command"].split("python")[1].split(".py")[0].strip()
        self.info["apps"] = []
        self.info["apps_in_use"] = []

        for section in self.supervisor.sections():
            try:
                self.info["apps_in_use"].append(self.supervisor[section]["command"].split("python")[1].split(".py")[0].strip())
            except:
                self.info["apps_in_use"].append(self.supervisor[section]["command"])

        for dir in os.listdir("/media/usb/apps/projects/"):
            self.info["apps"].append(dir)
        return self.info["apps"]

    # Guess screen resolution from boot file
    def getScreen(self):
        self.info["screen"] = None
        self.info["screen_resolution"] = (320,240)
        f = open("/boot/config.txt", "r")
        lines = f.readlines()
        for line in lines:
            if "dtoverlay" in line and "#dtoverlay" not in line and "fps" in line:
                self.info["screen"] = line.strip().split("dtoverlay=")[1].split(",")[0]
        if self.info["screen"] == "pitft22":
            self.info["screen_resolution"] = (320,240)
        return self.info["screen_resolution"]

    # Check if SD Card is writed protected
    def getDevMode(self):
        f = open("/boot/cmdline.txt")
        lines = f.readlines()
        self.info["devmode"] = False
        for line in lines:
            if "overlay" in line:
                self.info["devmode"] = True
        f.close()
        return self.info["devmode"]

    # Get Hostname
    def getHostname(self):
        self.info["hostname"] = socket.gethostname()
        return self.info["hostname"]

    # Get WiFi Country as saved in wpa_supplicant.conf
    def getWiFiCountry(self):
        self.info["wifi_country"] = ""
        if(self.info["root"]):
            f = open("/etc/wpa_supplicant/wpa_supplicant.conf", "r")
            lines = f.readlines()
            for line in lines:
                if "country=" in line:
                    self.info["wifi_country"] = line.split("=")[1].strip()
                    f.close()
                    return self.info["wifi_country"]
            f.close()
        return self.info["wifi_country"]

    # Get first IP address from hostname
    def getIP(self):
        ip = subprocess.check_output(["hostname", "-I"])
        ip = ip.decode()
        ip = ip.split(" ")[0]
        self.info["ip"] = ip
        return ip

    # Get SSID
    def getSSID(self):
        try:
            ssid = subprocess.check_output(["iwgetid", "-r"])
            self.info["ssid"] = ssid.decode().strip()
        except:
            print("Wifi is disconnected")
            self.info["ssid"] = ""
        return self.info["ssid"]

    # Scan SSIDS and return list
    def scanSSID(self):
        scan_ssid = subprocess.check_output(["sudo", "iwlist", "wlan0", "scanning"])
        scan_ssid = scan_ssid.decode().strip()
        scan_ssid = scan_ssid.split("\n")
        list_ssids = []
        for scan in scan_ssid:
            if("ESSID:" in scan):
                scan = scan.split(":")[1]
                scan = scan.replace("\"", "")
                list_ssids.append(scan)
        self.info["ssids"] = list_ssids
        return list_ssids

    # Check if WiFi is connected
    def getWiFi(self):
        child = subprocess.Popen(["ifconfig", "wlan0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result = child.stdout.read().decode()
        if "inet" in result:
            self.info["WiFiConnected"] = True
        else:
            self.info["WiFiConnected"] = False
        return self.info["WiFiConnected"]

    # Change WiFi settings
    def setupWiFi(self, wifi_name, wifi_password, wifi_country):
        if(self.info["root"]):
            wpa_supplicant_file = open("/etc/wpa_supplicant/wpa_supplicant.conf", "w")
            wpa_supplicant_file.write("ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
            wpa_supplicant_file.write("update_config=1\n")
            wpa_supplicant_file.write("country=" + wifi_country +"\n")
            wpa_supplicant_file.write("network={\n")
            wpa_supplicant_file.write("         ssid=\"" + wifi_name + "\"\n")
            wpa_supplicant_file.write("         psk=\"" + wifi_password + "\"\n")
            wpa_supplicant_file.write("}\n")
            wpa_supplicant_file.close()
            return True
        else:
            print("Warning you need permissions to write WiFi, WiFi change will not be changed")
            return False

    # Test current WiFi settings if failed to connect you can still rollback
    # To previous settings (if saved)
    def testWiFi(self, timeout=15):
        waiting = True
        state = False
        endTimer = time.time()

        while waiting:
            if time.time() - endTimer > timeout:
                waiting = False
            print(time.time() - endTimer)
            child = subprocess.Popen(["ifconfig", "wlan0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            result = child.stdout.read().decode()
            print(result)
            if "inet" in result:
                state = True
                waiting = False

            time.sleep(0.1)

        return state

    # Save current wifi settings in temp file
    def backupWiFiSettings(self):
        if(self.info["root"]):
            shutil.copyfile("/etc/wpa_supplicant/wpa_supplicant.conf", "/etc/wpa_supplicant/wpa_supplicant.conf.tmp")
            return True
        else:
            print("Warning : Need root permissions")
            return False

    # Restore temp wifi settings to wifi settings
    def restoreWiFiSettings(self):
        if(self.info["root"]):
            shutil.copyfile("/etc/wpa_supplicant/wpa_supplicant.conf.tmp", "/etc/wpa_supplicant/wpa_supplicant.conf")
        else:
            print("Warning : Need root permissions")
            return False

    # Remove temp wifi settings
    def removeWiFiTempSettings(self):
        if(self.info["root"]):
            os.remove("/etc/wpa_supplicant/wpa_supplicant.conf.tmp")
        else:
            print("Warning : Need root permissions")
            return False

    # Check if internet is connected
    def getInternet(self):
        try:
            urllib.request.urlopen("https://wikipedia.org")
            self.info["internet"] = True
        except:
            self.info["internet"] = False
        return self.info["internet"]

    def info(self):
        return self.info

    # Change Samba Password
    # https://stackoverflow.com/questions/19813376/change-an-user-password-on-samba-with-python
    def changeSambaUser(self, username, password):
        if (self.info["root"]):
            proc = subprocess.Popen(['smbpasswd', '-a', username], stdin=subprocess.PIPE)
            proc.communicate(input=password.encode() + '\n'.encode() + password.encode() + '\n'.encode())
            return True
        else:
            print("Warning : Need root permissions")
            return False

    # Change SSH User Password
    def changeSSHUser(self, username, password):
        if (self.info["root"]):
            pass_ssh = "\""+username+":"+password+"\""
            os.system("echo " + pass_ssh + " | chpasswd")
        else:
            print("Warning : Need root permissions")
            return False

    # Restart WiFi
    def restartWifi(self):
        if(self.info["root"]):
            child = subprocess.Popen(["sudo", "pkill", "wpa_supplicant"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(child.stdout.read().decode())
            time.sleep(1)
            child = subprocess.Popen(["wpa_supplicant", "-B", "-i","wlan0", "-c","/etc/wpa_supplicant/wpa_supplicant.conf"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(child.stdout.read().decode())

    # Stop an application from supervisor
    def stopApp(self):
        if(self.info["root"]):
            os.system("sudo supervisorctl stop app")

    # Get Status of application
    def statusApp(self):
        status_app = subprocess.check_output(["sudo", "supervisorctl", "status", "app"])
        return status_app.decode().split(" ")[30]

    def appSettings(self):
        self.getApps()
        app_path = "/media/usb/apps/projects/" + self.info["current_app"]
        print(app_path)
        if(os.path.exists(app_path + "/settings.json")):
            return json.load(open(app_path + "/settings.json"))
        else:
            return {}

    # Start application from supervisor
    def startApp(self):
        if(self.info["root"]):
            os.system("sudo supervisorctl start app")

    # Change Application
    # If xinit file in application prepare to start xwindow app
    # If root file in application user will be root
    def changeApp(self, app_name):
        if(self.info["root"]):
            # If app_name.py file exists
            if os.path.isfile("/media/usb/apps/projects/" + app_name + "/" + app_name + ".py"):
                if(os.path.isfile("/media/usb/apps/projects/" + app_name + "/desktop")):
                    self.supervisor["program:app"]["user"] = "pi"
                    self.supervisor["program:app"]["environment"] = "DISPLAY=:0"
                else:
                    if(os.path.isfile("/media/usb/apps/projects/" + app_name + "/root")):
                        self.supervisor["program:app"]["user"] = "root"
                    else:
                        self.supervisor["program:app"]["user"] = "pi"

                # change application in supervisor
                self.supervisor["program:app"]["command"] = "/usr/bin/python " + app_name + ".py"
                self.supervisor["program:app"]["directory"] = "/media/usb/apps/projects/" + app_name
                with open(self.supervisor_file, 'w') as configfile:
                    self.supervisor.write(configfile)
                os.system("sudo supervisorctl stop app")
                os.system("sudo supervisorctl update")
                os.system("sudo supervisorctl start app")
                # os.system("sudo supervisorctl stop webapi")
                # os.system("sudo supervisorctl start webapi")
            else:
                print("/media/usb/apps/projects/" + app_name + "/" + app_name + ".py" + " doesn't exists ")

    # Change hostname
    def changeName(self, name):
        if(self.info["root"]):
            f = open("/etc/hostname", "w")
            f.write(name)
            f.close()
            # Change name in /etc/hosts
            f = open("/etc/hosts", "r")
            lines = f.readlines()
            i = 0
            for line in lines:
                # If line contains 127.0.1.1
                if "127.0.1.1" in line:
                    # Split line in two string
                    lines[i] = "127.0.1.1   " + name + "\n"
                i += 1
            # Save lines in /etc/hosts
            f = open("/etc/hosts", "w")
            f.writelines(lines)
            f.close()

            os.system("hostname " + name)
            os.system("systemctl restart avahi-daemon")
            return True
        else:
            print("Warning : Need root permissions")
            return False
