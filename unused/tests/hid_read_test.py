import hid
import time
import struct


VID = 0x45e
PID = 0xb12


def decode(data):
    if len(data) < 18 or data[0] != 0x20:
        return None

    raw = bytes(data)
    b1 = data[4]
    b2 = data[5]

    return {
        'seq': data[2],
        'A': bool(b1 & 0x10),
        'B': bool(b1 & 0x20),
        'X': bool(b1 & 0x40),
        'Y': bool(b1 & 0x80),
        'LB': bool(b2 & 0x10),
        'RB': bool(b2 & 0x20),
        'dpad_up': bool(b2 & 0x01),
        'dpad_down': bool(b2 & 0x02),
        'dpad_left': bool(b2 & 0x04),
        'dpad_right': bool(b2 & 0x08),
        'LT': struct.unpack_from('<H', raw, 6)[0],
        'RT': struct.unpack_from('<H', raw, 8)[0],
        'LX': struct.unpack_from('<h', raw, 10)[0] / 32767.0,
        'LY': -struct.unpack_from('<h', raw, 12)[0] / 32767.0,
        'RX': struct.unpack_from('<h', raw, 14)[0] / 32767.0,
        'RY': -struct.unpack_from('<h', raw, 16)[0] / 32767.0,
    }


def main():
    dev = hid.device()
    try:
        dev.open(VID, PID)
        print(f'Connected: {dev.get_product_string()}')
    except Exception as e:
        print(f'Failed: {e}')
        return

    dev.set_nonblocking(True)
    print('入力待ち... (Ctrl+C で終了)\n')

    try:
        while True:
            data = dev.read(64)
            if data:
                s = decode(data)
                if s:
                    # 何か入力あるときだけ表示
                    active = (s['A'] or s['B'] or s['X'] or s['Y']
                              or s['LB'] or s['RB']
                              or s['dpad_up'] or s['dpad_down']
                              or s['dpad_left'] or s['dpad_right']
                              or s['LT'] > 500 or s['RT'] > 500
                              or abs(s['LX']) > 0.15 or abs(s['LY']) > 0.15
                              or abs(s['RX']) > 0.15 or abs(s['RY']) > 0.15)
                    if active:
                        print(f'A={int(s["A"])} B={int(s["B"])} X={int(s["X"])} Y={int(s["Y"])} '
                              f'LB={int(s["LB"])} RB={int(s["RB"])} '
                              f'LT={s["LT"]:4d} RT={s["RT"]:4d} '
                              f'L=({s["LX"]:+.2f},{s["LY"]:+.2f}) '
                              f'R=({s["RX"]:+.2f},{s["RY"]:+.2f}) '
                              f'DPad=U{int(s["dpad_up"])}D{int(s["dpad_down"])}L{int(s["dpad_left"])}R{int(s["dpad_right"])}')
            time.sleep(0.01)
    except KeyboardInterrupt:
        print('\nEnd.')
    finally:
        dev.close()


if __name__ == '__main__':
    main()