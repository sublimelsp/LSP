from __future__ import annotations

import sublime


class ProgressReporter:

    def __init__(self, title: str) -> None:
        self.title = title
        self._message: str | None = None
        self._percentage: None | int | float = None

    def __del__(self) -> None:
        pass

    def _render(self) -> str:
        result = self.title
        if self._message:
            result += ': ' + self._message
        if self._percentage:
            fmt = ' ({:.1f}%)' if isinstance(self._percentage, float) else ' ({}%)'
            result += fmt.format(self._percentage)
        return result

    def __call__(self, message: str | None, percentage: None | int | float) -> None:
        if percentage is not None:
            self._percentage = percentage
        if message is not None:
            self._message = message


class ViewProgressReporter(ProgressReporter):

    def __init__(self, view: sublime.View, key: str, title: str, message: str | None = None,
                 percentage: None | int | float = None) -> None:
        super().__init__(title)
        self._view = view
        self._key = key
        self.__call__(message, percentage)

    def __del__(self) -> None:
        self._view.erase_status(self._key)
        super().__del__()

    def __call__(self, message: str | None = None, percentage: None | int | float = None) -> None:
        super().__call__(message, percentage)
        self._view.set_status(self._key, self._render())


class WindowProgressReporter(ProgressReporter):

    def __init__(self, window: sublime.Window, key: str, title: str, message: str | None = None,
                 percentage: None | int | float = None) -> None:
        super().__init__(title)
        self._window = window
        self._key = key
        self.__call__(message, percentage)

    def __del__(self) -> None:
        for view in self._window.views():
            view.erase_status(self._key)
        super().__del__()

    def __call__(self, message: str | None = None, percentage: None | int | float = None) -> None:
        super().__call__(message, percentage)
        display = self._render()
        for view in self._window.views():
            view.set_status(self._key, display)


class ApplicationProgressReporter(ProgressReporter):

    def __init__(self, key: str, title: str, message: str | None = None,
                 percentage: None | int | float = None) -> None:
        super().__init__(title)
        self._key = key
        self.__call__(message, percentage)

    def __del__(self) -> None:
        for window in sublime.windows():
            for view in window.views():
                view.erase_status(self._key)
        super().__del__()

    def __call__(self, message: str | None = None, percentage: None | int | float = None) -> None:
        super().__call__(message, percentage)
        display = self._render()
        for window in sublime.windows():
            for view in window.views():
                view.set_status(self._key, display)
