from time import sleep
from binascii import crc32
from threading import Thread
from struct import pack, unpack
from socket import socket, AF_INET, SOCK_STREAM
from kivy.app import App
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from kivy import config
config.Config.set('input', 'mouse', 'mouse,disable_multitouch')


class IconButton(ButtonBehavior, Image):
    # A class to have an image which behave like a button
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class MotorScreen(Screen):
    def __init__(self, ip=None, **kwargs):
        super().__init__(**kwargs)
        # self.motor contains the class to talk to the motor through tcp/ip
        self.motor = Motor_TCPIP(ip, 2317)
        #   Try to connect
        try:
            self.motor.open_socket()
            self.ids.device.text = self.name + ' Status : Connected.'
            self.ids.btn_on.disabled = False
            # thread_on is just here to close properly the thread when window
            # is closed
            self.thread_on = True
            Thread(target=self.get_position).start()
        except:
            self.ids.device.text = self.name + ' Status : Not connected.'
            self.on_or_off(False)
            self.ids.btn_on.disabled = True

    def get_position(self):
        # This loop reads position if the motor is on
        while self.thread_on:
            try:
                pos = self.motor.motor_read_pos()
                self.ids.cur_pos.text = "[b]Current Position "
                self.ids.cur_pos.text += "[color=#008000]" + str(pos)
                self.ids.cur_pos.text += "[/color] ?[/b]"
                speed = self.motor.motor_read_speed()
                self.ids.cur_speed.text = "[b]Current Speed "
                self.ids.cur_speed.text += "[color=#008000]%.2f" % speed
                self.ids.cur_speed.text += "[/color] ?[/b]"
            except:
                self.motor.close_socket()
                self.ids.device.text = 'Status : Device not connected.'
                self.on_or_off(False)
                self.ids.btn_on.disabled = True
                break
            sleep(0.5)
        return 0

    def on_or_off(self, on_off):
        # Just to disable or enable buttons
        self.ids.btn_on.disabled = on_off
        self.ids.btn_off.disabled = not on_off
        self.ids.btn_pos.disabled = not on_off
        self.ids.btn_speed.disabled = not on_off

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
        speed = int(self.ids.input_speed.text)
        if 1 <= speed <= 300:
            self.motor.set_speed(speed)


class MainScreen(BoxLayout):
    # The main screen, which contains 2 sub_screens for 2 motors
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        screen = MotorScreen(ip='192.168.39.5', name='Motor1')
        self.ids.rootscreen.add_widget(screen)
        screen = MotorScreen(ip='192.168.39.6', name='Motor2')
        self.ids.rootscreen.add_widget(screen)

    def shift_screen(self):
        self.ids.rootscreen.current = self.ids.rootscreen.next()


class MainApp(App):
    # Main App class, see Kivy documentation for details
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self):
        self.root = MainScreen()
        return self.root

    def on_stop(self):
        # Close connexion when app is closed
        screen1 = self.root.ids.rootscreen.get_screen('Motor1')
        screen2 = self.root.ids.rootscreen.get_screen('Motor2')
        try:
            screen1.thread_on = False
            screen1.motor.motorcontrol_off()
            screen1.motor.close_socket()
        except:
            pass
        try:
            screen2.thread_on = False
            screen2.motor.motorcontrol_off()
            screen2.motor.close_socket()
        except:
            pass


class Motor_TCPIP(object):
    def __init__(self, tcp_ip, tcp_port):
        self.buffer = 2048
        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.settimeout(1)

    def open_socket(self):
        # Open the connexion
        self.s.connect((self.tcp_ip, self.tcp_port))

    def close_socket(self):
        # Close the connexion
        self.s.shutdown(2)
        self.s.close()

    def motorcontrol_on(self):
        # Command to turn the motor on, the ID corresponds to the DriveManager
        # ID that is being overwritten. It's the same principle for all other
        # function. The value has been guessed by observing the behavior of
        # motor and sniffing packets.
        self.packet_sender(2, 229, 128, 'int32')

    def motorcontrol_off(self):
        self.packet_sender(2, 229, 0, 'int32')

    def motor_move_pos(self, position):
        # Only one packet is containing the position information. The others
        # are just here to trigger the movement. Again, we don't know why
        # exactly it is needed but we guessed that with DriveManager.
        self.packet_sender(2, 300, 3, 'uint16')
        self.packet_sender(2, 301, 0, 'uint16')
        self.packet_sender(2, 230, position, 'int32')
        self.packet_sender(2, 229, 1153, 'int32')

    def set_speed(self, speed):
        # Acceleration and decceleration are 232 and 233 float if needed
        self.packet_sender(2, 231, speed, 'float')

    def motor_read_pos(self):
        # Packet to read positions. Note it's a function with a
        # "return". It's because we need to use the returning packet.
        data = self.packet_sender(1, 276, 1, 'int32')
        data = data[len(data) - 4:len(data)]

        return unpack('<i', data)[0]

    def motor_read_speed(self):
        data = self.packet_sender(1, 281, 1, 'int32')
        data = data[len(data) - 4:len(data)]

        return unpack('<f', data)[0]

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
