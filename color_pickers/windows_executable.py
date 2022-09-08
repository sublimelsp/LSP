import ctypes

CC_SOLIDCOLOR = 0x80
CC_RGBINIT = 0x01
CC_FULLOPEN = 0x02

red = 0.5
green = 0.2
blue = 0.1
default_color = (round(255*blue) << 16) | (round(255*green) << 8) | round(255*red)

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

def bgr2hexcolor(bgr):
        # 0x00BBGGRR
        byte_table = list(["{0:02X}".format(b) for b in range(256)])
        b = byte_table[(bgr >> 16) & 0xff]
        g = byte_table[(bgr >> 8) & 0xff]
        r = byte_table[(bgr) & 0xff]
        return "#" + (r + g + b).lower()


def on_select_color():
    ChooseColorW = ctypes.windll.Comdlg32.ChooseColorW
    ChooseColorW.argtypes = [ctypes.POINTER(CHOOSECOLOR)]
    ChooseColorW.restype = ctypes.c_int32

    cc = CHOOSECOLOR()
    ctypes.memset(ctypes.byref(cc), 0, ctypes.sizeof(cc))
    cc.lStructSize = ctypes.sizeof(cc)
    cc.hwndOwner = None
    CustomColors = ctypes.c_uint32 * 16
    cc.lpCustColors = CustomColors() # uses 0 (black) for all 16 predefined custom colors
    cc.rgbResult = ctypes.c_uint32(default_color)
    cc.Flags = CC_SOLIDCOLOR | CC_FULLOPEN | CC_RGBINIT

    # ST window will become unresponsive until color picker dialog is closed
    result = ChooseColorW(ctypes.byref(cc))

    if result == 1: # user clicked OK
        print(bgr2hexcolor(cc.rgbResult))

on_select_color()