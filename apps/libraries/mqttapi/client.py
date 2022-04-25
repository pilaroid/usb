
import paho.mqtt.client as mqtt
import threading
import os
import sys
import json

class MQTTAPI():
    def __init__(self, password="pilaroid", message_callback=None):
        self.password = password
        filename = os.path.basename(sys.argv[0])
        filename = os.path.splitext(filename)[0]
        self.app = filename
        self.message_callback = message_callback
        self.values = {}
        self.settings_file = os.getcwd() + "/settings.json"

    def isInt(self, string):
        if string.isdigit():
            return True
        elif string.startswith('-') and string[1:].isdigit():
            return True
        else:
            return False

    def isFloat(self, string):
        try:
            float(string)
            return True
        except:
            return False

    def on_message(self, client, userdata, msg):
        # Save settings as an dictionnary (self.values)

        # Convert binary payload into a utf-8 string
        msg.payload = str(msg.payload.decode("utf-8"))

        # If this is an integer convert it
        if self.isInt(msg.payload):
            self.values[msg.topic] = int(msg.payload)
        # If this is a float convert it
        elif self.isFloat(msg.payload):
            self.values[msg.topic] = float(msg.payload)
        else:
            self.values[msg.topic] = msg.payload
        self.backup()
        if self.message_callback != None:
            self.message_callback(msg.topic, self.values[msg.topic])

        #print("Settings changed")
        #print(self.values)

    def backup(self):
        file = open(self.settings_file, "w")
        file.write(json.dumps(self.values))
        file.close()

    def on_connect(self, client, userdata, flags, rc):
        if(str(rc) == "5"):
            self.state = False
            print("MQTT : Not Authorized! Check username/password")
        else:
            self.state = True
            print("MQTT : Connected - "+str(rc))
        if(self.state):
            client.subscribe("apps/#")
            client.publish("system/app", self.app, retain=True)
        for key,value in self.values.items():
            client.publish(key, value, retain=True)

    def set_default(self, topic, value):
        self.values[topic] = value

    def get(self, topic):
        return self.values[topic]

    def set(self, topic, value):
        self.values[topic] = value
        self.client.publish(topic, value, retain=True)

    def run(self):
        if os.path.exists(self.settings_file):
            try:
                file = open(self.settings_file)
                self.values = json.load(file)
                file.close()
            except:
                print("Settings file "+ self.settings_file +" corrupt")
                self.backup()
        else:
            print("Settings file "+ self.settings_file +" doesn't exists")
            self.backup()

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.username_pw_set("pi", self.password)
        self.client.will_set("system/app", "none",retain=True)
        self.client.connect(host="127.0.0.1",port=1883,keepalive=60)
        self.thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        self.thread.start()
