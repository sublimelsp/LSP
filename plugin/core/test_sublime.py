

DIALOG_CANCEL = 0
DIALOG_YES = 1
DIALOG_NO = 2


def message_dialog(msg: str) -> None:
    pass


def ok_cancel_dialog(msg: str, ok_title: str) -> bool:
    return True


def yes_no_cancel_dialog(msg, yes_title: str, no_title: str) -> int:
    return DIALOG_YES


def set_timeout_async(callback, duration):
    callback()


class Region(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b
