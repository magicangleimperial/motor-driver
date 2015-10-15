import sys
from os import path
from time import sleep
from binascii import crc32
from threading import Thread
from struct import pack, unpack
from PyQt5 import uic, QtWidgets
from socket import socket, AF_INET, SOCK_STREAM


class GUIMainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = uic.loadUi(path.dirname(path.realpath(__file__)) + '/main.ui', self)
        self.ui.pushButton_motoron.clicked.connect(self.on)
        self.ui.pushButton_motoroff.clicked.connect(self.off)
        self.ui.pushButton_go.clicked.connect(self.move_pos)

        self.motor = Motor('192.168.39.5', 2317)
        self.on = True
        Thread(target=self.read_pos).start()

    def on(self):
        self.motor.motorcontrol_on()

    def off(self):
        self.motor.motorcontrol_off()

    def move_pos(self):
        self.motor.motor_move_pos(int(self.ui.doubleSpinBox_targetpos.value()))

    def read_pos(self):
        while self.on:
            pos = self.motor.motor_read_pos()
            self.ui.doubleSpinBox_currentpos.setValue(pos)
            sleep(0.5)

        return 0

    def closeEvent(self, event):
        self.on = False
        self.motor.s.close()


class Motor(object):
    def __init__(self, tcp_ip, tcp_port):
        self.buffer = 2048
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.connect((tcp_ip, tcp_port))

    def motorcontrol_on(self):
        self.packet_sender(2, 229, 128, 'int32')
        print("Done")

    def motorcontrol_off(self):
        self.packet_sender(2, 229, 0, 'int32')
        print("Done")

    def motor_move_pos(self, position):
        self.packet_sender(2, 300, 3, 'uint16')
        self.packet_sender(2, 301, 0, 'uint16')
        self.packet_sender(2, 230, position, 'int32')
        self.packet_sender(2, 229, 1153, 'int32')
        print("Done")

    def motor_read_pos(self):
        data = self.packet_sender(1, 276, 1, 'int32')
        data = data[len(data) - 4:len(data)]

        return unpack('<i', data)[0]

    def packet_sender(self, p_type, id_value, value, type_v):
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
        checksum_start = pack('<L', crc32(start + adress + s_id + length, 3344495068))
        checksum_data = pack('<L', crc32(record + param_id + index + number, 3344494807))
        packet = start + adress + s_id + length + checksum_start + checksum_data + record + param_id + index + number
        self.s.send(packet)
        data = self.s.recv(self.buffer)

        return data

# Main Function
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    myapp = GUIMainWindow()
    myapp.show()
    sys.exit(app.exec_())
