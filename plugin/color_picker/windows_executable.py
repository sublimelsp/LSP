import ctypes
import sys

class CHOOSECOLOR(ctypes.Structure):
    _fields_ = [
        ("lStructSize", ctypes.c_uint32),
        ("hwndOwner", ctypes.c_void_p),
        ("hInstance", ctypes.c_void_p),
        ("rgbResult", ctypes.c_uint32),
        ("lpCustColors", ctypes.POINTER(ctypes.c_uint32)),
        ("Flags", ctypes.c_uint32),
        ("lCustData", ctypes.c_void_p),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", ctypes.c_wchar_p)]

CC_SOLIDCOLOR = 0x80
CC_RGBINIT = 0x01
CC_FULLOPEN = 0x02
ChooseColorW = ctypes.windll.Comdlg32.ChooseColorW
ChooseColorW.argtypes = [ctypes.POINTER(CHOOSECOLOR)]
ChooseColorW.restype = ctypes.c_int32


default_color = (255 << 16) | (255 << 8) | (255)

if len(sys.argv) > 1: # sys.argv[1] looks like '1,0.2,1,0.5'
    r, g, b, a = map(float, sys.argv[1].split(','))
    default_color = (round(255*b) << 16) | (round(255*g) << 8) | round(255*r)


cc = CHOOSECOLOR()
ctypes.memset(ctypes.byref(cc), 0, ctypes.sizeof(cc))
cc.lStructSize = ctypes.sizeof(cc)
cc.hwndOwner = None
CustomColors = ctypes.c_uint32 * 16
cc.lpCustColors = CustomColors() # uses 0 (black) for all 16 predefined custom colors
cc.rgbResult = ctypes.c_uint32(default_color)
cc.Flags = CC_SOLIDCOLOR | CC_FULLOPEN | CC_RGBINIT

# ST window will become unresponsive until color picker dialog is closed
output = ChooseColorW(ctypes.byref(cc))


def bgr2color(bgr) -> str:
    # 0x00BBGGRR
    byte_table = list(["{0:02X}".format(b) for b in range(256)])
    b_hex = byte_table[(bgr >> 16) & 0xff]
    g_hex = byte_table[(bgr >> 8) & 0xff]
    r_hex = byte_table[(bgr) & 0xff]

    r = int(r_hex, 16) / 255
    g = int(g_hex, 16) / 255
    b = int(b_hex, 16) / 255
    return '{},{},{}'.format(r, g, b)


if output == 1: # user clicked OK
    print(bgr2color(cc.rgbResult))



