import sys
from os.path import dirname, realpath
from time import sleep
from binascii import crc32
from threading import Thread
from struct import pack, unpack
from PyQt5 import QtWidgets
from PyQt5.uic import loadUi
from socket import socket, AF_INET, SOCK_STREAM


class GUIMainWindow(QtWidgets.QMainWindow):
    # Main class with GUI signals and slots
    def __init__(self, parent=None):
        super().__init__(parent)
        # This file contains the GUI, use QtDesigner to change it
        self.ui = loadUi(dirname(realpath(__file__)) + '/main.ui', self)
        # When clicked, triggers a specific function
        self.ui.pushButton_motoron.clicked.connect(self.on)
        self.ui.pushButton_motoroff.clicked.connect(self.off)
        self.ui.pushButton_go.clicked.connect(self.move_pos)
        try:
            # Create a motor class, with this specific IP
            self.motor = Motor('192.168.39.5', 2317)
            self.on = True
            Thread(target=self.read_pos).start()
        except:
            # if it fails, print something
            print('No motor connected')
        finally:
            pass

    def on(self):
        # Call the motorcontrol_on function in motor class
        self.motor.motorcontrol_on()

    def off(self):
        self.motor.motorcontrol_off()

    def move_pos(self):
        self.motor.motor_move_pos(int(self.ui.doubleSpinBox_targetpos.value()))

    def read_pos(self):
        # Read position every 500 ms and print it in a spinbox
        while self.on:
            pos = self.motor.motor_read_pos()
            self.ui.doubleSpinBox_currentpos.setValue(pos)
            sleep(0.5)

        return 0

    def closeEvent(self, event):
        # When window is closed, close the IP connexion
        self.on = False
        self.motor.s.close()


class Motor(object):
    def __init__(self, tcp_ip, tcp_port):
        # Open the connexion
        self.buffer = 2048
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.connect((tcp_ip, tcp_port))

    def motorcontrol_on(self):
        # Command to turn the motor on, the ID corresponds to the DriveManager
        # ID that is being overwritten. It's the same principle for all other
        # function. The value has been guessed by observing the behavior of
        # motor and sniffing packets.
        self.packet_sender(2, 229, 128, 'int32')
        print("Done")

    def motorcontrol_off(self):
        self.packet_sender(2, 229, 0, 'int32')
        print("Done")

    def motor_move_pos(self, position):
        # Only one packet is containing the position information. The others
        # are just here to trigger the movement. Again, we don't know why
        # exactly it is needed but we guessed that with DriveManager.
        self.packet_sender(2, 300, 3, 'uint16')
        self.packet_sender(2, 301, 0, 'uint16')
        self.packet_sender(2, 230, position, 'int32')
        self.packet_sender(2, 229, 1153, 'int32')
        print("Done")

    def motor_read_pos(self):
        # Packet to read positions. Note it's the only function with a
        # "return". It's because we need to use the returning packet.
        data = self.packet_sender(1, 276, 1, 'int32')
        data = data[len(data) - 4:len(data)]

        return unpack('<i', data)[0]

    def packet_sender(self, p_type, id_value, value, type_v):
        # This is building packets, the explanation can be found in Robert's
        # documentation which contains the structure of each packet. But it is
        # unlikely you'll have to modify start/adress/length/record/index
        # Only s_id (type of ID, can be found in DriveManager), param_ID (the
        # actual ID, also found in Drive Manager) and number (value to write in
        # ID) will have to be changed if you want to do other simple tasks.
        # The 2685547530 'magic' number is given in the documentation
        start = pack('<L', 2685547530)
        adress = pack('<L', 0)
        s_id = pack('<L', p_type)
        length = pack('<L', 16)
        record = pack('<l', -1)
        param_id = pack('<L', id_value)
        index = pack('<L', 0)
        if type_v == 'int32':
            number = pack('<L', value)
        elif type_v == 'float':
            number = pack('<f', value)
        else:
            number = pack('<i', value)
        # The 3344495068/3344494807 are necessary to obtain a correct checksum
        # They have been found by sniffing packets, and bruteforcing numbers
        # until both checksum are the same.
        checksum = crc32(start + adress + s_id + length, 3344495068)
        checksum_start = pack('<L', checksum)
        checksum = crc32(record + param_id + index + number, 3344494807)
        checksum_data = pack('<L', checksum)
        packet = start + adress + s_id + length + checksum_start
        packet += checksum_data + record + param_id + index + number
        self.s.send(packet)
        data = self.s.recv(self.buffer)

        return data

# Excecute script when file is excecuted
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    myapp = GUIMainWindow()
    myapp.show()
    sys.exit(app.exec_())
