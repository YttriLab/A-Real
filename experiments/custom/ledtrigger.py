import serial
import time


class LEDstim:
    def __init__(self):
        self.ser = serial.Serial('COM4', 9600, timeout=1)
        self.on = False
        self.off = True

    def LEDon(self):
        self.on = True
        self.ser.write(b'H')


    def LEDoff(self):
        self.on = False
        self.ser.write(b'L')


    def toggle(self):
        if self.on:
            self.LEDoff()

            # time.sleep(1)
            print('LED already on')
        else:
            self.LEDon()

