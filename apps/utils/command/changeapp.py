import argparse
import configparser
import os

parser = argparse.ArgumentParser()
parser.add_argument("app", help="Application to change")
args = parser.parse_args()
if args.app:
  app_name = args.app
  supervisor = configparser.ConfigParser()
  supervisor.read("/media/usb/apps.conf")

  if os.path.isfile("/media/usb/apps/projects/" + app_name + "/" + app_name + ".py"):
    if(os.path.isfile("/media/usb/apps/projects/" + app_name + "/desktop")):
        supervisor["program:app"]["user"] = "pi"
        supervisor["program:app"]["environment"] = "DISPLAY=:0"
    else:
        if(os.path.isfile("/media/usb/apps/projects/" + app_name + "/root")):
            supervisor["program:app"]["user"] = "root"
        else:
            supervisor["program:app"]["user"] = "pi"

    # change application in supervisor
    supervisor["program:app"]["command"] = "/usr/bin/python " + app_name + ".py"
    supervisor["program:app"]["directory"] = "/media/usb/apps/projects/" + app_name
    with open("/media/usb/apps.conf", 'w') as configfile:
        supervisor.write(configfile)
    os.system("sudo supervisorctl stop app")
    os.system("sudo supervisorctl update")
    os.system("sudo supervisorctl start app")
    # os.system("sudo supervisorctl stop webapi")
    # os.system("sudo supervisorctl start webapi")
  else:
    print("/media/usb/apps/projects/" + app_name + "/" + app_name + ".py" + " doesn't exists ")
