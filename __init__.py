import sublime_plugin
from .event_loop import setup_event_loop, shutdown_event_loop

setup_event_loop()


class EventLoopListener(sublime_plugin.EventListener):
    def on_exit(self) -> None:
        shutdown_event_loop()
