#!/usr/bin/env python3

from dvrip import DVRIPCam
from telnetlib import Telnet
import argparse
import json
import os
import socket
import time
import zipfile

TELNET_PORT = 4321

"""
    Tested on XM boards:
    IPG-53H20PL-S       53H20L_S39                  00002532
    IVG-85HF20PYA-S     HI3516EV200_50H20AI_S38     000559A7
"""


# Borrowed from InstallDesc
flashes = {
    '000559A7': [ "0x00EF4017", "0x00EF4018", "0x00C22017", "0x00C22018",
                  "0x00C22019", "0x00C84017", "0x00C84018", "0x001C7017",
                  "0x001C7018", "0x00207017", "0x00207018", "0x000B4017",
                  "0x000B4018", ]
}

def add_flashes(desc, swver):
    supported = flashes.get(swver)
    if supported is None:
        return

    fls = []
    for i in supported:
        fls.append({"FlashID":	i})
    desc['SupportFlashType'] = fls


def make_zip(filename, data):
    zipf = zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED)
    zipf.writestr("InstallDesc", data)
    zipf.close()


def check_port(host_ip, port):
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result_of_check = a_socket.connect_ex((host_ip, port))
    return result_of_check == 0


def extract_gen(swver):
    return swver.split(".")[3]


def open_telnet(host_ip, port, **kwargs):
    do_reboot=kwargs.get('reboot', False)
    user=kwargs.get('username', 'admin')
    password=kwargs.get('password', '')

    cam = DVRIPCam(host_ip, user=user, password=password)
    if not cam.login():
        print(f"Cannot connect {host_ip}")
        return
    upinfo = cam.get_upgrade_info()
    hw = upinfo["Hardware"]
    print(f"Modifiying camera {hw}")
    sysinfo = cam.get_system_info()
    swver = extract_gen(sysinfo["SoftWareVersion"])
    print(f"Firmware generation {swver}")

    armbenv = {
        "Command": "Shell",
        "Script": "XmEnv -s xmuart 0; XmEnv -s telnetctrl 1",
    }
    telnetd = {
        "Command": "Shell",
        "Script": f"busybox telnetd -F -p {port} -l /bin/sh",
    }
    desc = {
        "UpgradeCommand": [armbenv],
        "Hardware": hw,
        "DevID": f"{swver}1001000000000000",
        "CompatibleVersion": 2,
        "Vendor": "General",
        "CRC": "1ce6242100007636",
    }
    add_flashes(desc, swver)
    zipfname = "upgrade.bin"
    make_zip(zipfname, json.dumps(desc, indent=2))
    cam.upgrade(zipfname)
    cam.close()
    os.remove(zipfname)

    if check_port(host_ip, port):
        if not do_reboot:
            print(f"Now use 'telnet {host_ip} {port}' to login")
        else:
            tn = Telnet(host_ip, port=port)
            tn.read_until(b"# ")
            tn.write(b'reboot\n')
            tn.read_all().decode('ascii')
            print("Reboot has been initiated")
    else:
        print("Something went wrong")
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hostname", help="Camera IP address or hostname")
    parser.add_argument("-u", "--username", default='admin',
                        help="Username for camera login")
    parser.add_argument("-p", "--password", default='',
                        help="Password for camera login")
    parser.add_argument("-r", "--reboot", action="store_true",
                        help="Reboot camera after make changes")
    args = parser.parse_args()
    open_telnet(args.hostname, TELNET_PORT, **vars(args))


if __name__ == "__main__":
    main()
