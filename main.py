from time import sleep
from binascii import crc32
from threading import Thread
from struct import pack, unpack
from socket import socket, AF_INET, SOCK_STREAM
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy import config
config.Config.set('input', 'mouse', 'mouse,disable_multitouch')


class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.motor = None
        self.motor_connected = False
        self.thread_on = True
        Thread(target=self.get_position).start()

    def get_position(self):
        while self.thread_on:
            if not self.motor_connected:
                try:
                    self.motor = Motor('192.168.39.5', 2317)
                    self.motor_connected = True
                    self.ids.device.text = 'Status : Device connected.'
                    self.ids.btn_on.disabled = False
                except:
                    self.ids.device.text = 'Status : Device not connected.'
                    self.on_or_off(False)
                    self.ids.btn_on.disabled = True
                    self.motor_connected = False
                sleep(2)
            else:
                try:
                    pos = self.motor.motor_read_pos()
                    self.ids.cur_pos.text = str(pos)
                except:
                    self.motor_connected = False
                sleep(0.5)
        return 0

    def on_or_off(self, on_off):
        self.ids.btn_on.disabled = on_off
        self.ids.btn_off.disabled = not on_off
        self.ids.btn_pos.disabled = not on_off

    def on(self):
        self.motor.motorcontrol_on()
        self.on_or_off(True)

    def off(self):
        self.motor.motorcontrol_off()
        self.on_or_off(False)

    def go_to_position(self):
        pos = int(self.ids.input_position.text)
        if -100000000 <= pos <= 100000000:
            self.motor.motor_move_pos(pos)

    def set_speed(self):
        print('set speed')


class MainApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self):
        self.root = MainScreen()
        return self.root

    def on_stop(self):
        self.root.thread_on = False
        try:
            self.root.motor.s.close()
        except:
            pass


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


if __name__ == "__main__":
    app = MainApp()
    app.run()
