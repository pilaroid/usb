import time

# Generate a countdown
class Countdown():
    def __init__(self, delay=1, nb=3):
        self.start_timer = 0
        self.started = False
        self.delay = delay
        self.nb = nb

    def current(self):
        if self.state > self.nb:
            self.state = self.nb
        return self.state

    def running(self):
        if self.started:
            if time.time() > (self.start_timer + self.delay):
                if self.state > 1:
                    self.state = self.state - 1
                    self.run = True
                else:
                    self.run = False
                    self.started = False
                self.start_timer = time.time()
            return True
        else:
            self.state = self.nb
            return False

    def start(self):
        self.start_timer = time.time()
        self.state = self.nb + 1
        self.started = True
