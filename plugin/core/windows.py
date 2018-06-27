from .sessions import Session


class WindowLike(object):
    def id(self):
        return 0


class WindowManager(object):
    def __init__(self):
        self._windows = {}  # type: Dict[int, WindowState]

    def lookup(self, window: WindowLike):
        state = self._windows.get(window.id())
        if state is None:
            state = WindowState()
            self._windows[window.id()] = state
        return state


class WindowState(object):
    def __init__(self):
        self._sessions = dict()  # type: Dict[str, Session]

    def get_session(self, config_name: str) -> 'Optional[Session]':
        return self._sessions.get(config_name)

    def add_session(self, config_name: str, session: Session) -> None:
        if config_name not in self._sessions:
            self._sessions[config_name] = session
        else:
            raise Exception("session already added")
