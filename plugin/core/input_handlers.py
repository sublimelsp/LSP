from __future__ import annotations
from .constants import ST_VERSION
from abc import ABCMeta
from abc import abstractmethod
from typing import Any, Callable, List, Tuple, Union
from typing import final
from typing_extensions import ParamSpec
import functools
import sublime
import sublime_plugin
import time
import weakref


ListItemsReturn = Union[List[str], Tuple[List[str], int], List[Tuple[str, Any]], Tuple[List[Tuple[str, Any]], int],
                        List[sublime.ListInputItem], Tuple[List[sublime.ListInputItem], int]]

P = ParamSpec('P')


def debounced(user_function: Callable[P, Any]) -> Callable[P, None]:
    """ A decorator which debounces the calls to a function.

    Note that the return value of the function will be discarded, so it only makes sense to use this decorator for
    functions that return None. The function will run on Sublime's main thread.
    """
    DEBOUNCE_TIME = 0.5  # seconds

    @functools.wraps(user_function)
    def wrapped_function(*args: P.args, **kwargs: P.kwargs) -> None:
        def check_call_function() -> None:
            target_time = getattr(wrapped_function, '_target_time', None)
            if isinstance(target_time, float):
                additional_delay = target_time - time.monotonic()
                if additional_delay > 0:
                    setattr(wrapped_function, '_target_time', None)
                    sublime.set_timeout(check_call_function, int(additional_delay * 1000))
                    return
            delattr(wrapped_function, '_target_time')
            user_function(*args, **kwargs)
        if hasattr(wrapped_function, '_target_time'):
            setattr(wrapped_function, '_target_time', time.monotonic() + DEBOUNCE_TIME)
            return
        setattr(wrapped_function, '_target_time', None)
        sublime.set_timeout(check_call_function, int(DEBOUNCE_TIME * 1000))
    return wrapped_function


class PreselectedListInputHandler(sublime_plugin.ListInputHandler, metaclass=ABCMeta):
    """ A ListInputHandler which can preselect a value.

    Subclasses of PreselectedListInputHandler must not implement the `list_items` method, but instead `get_list_items`,
    i.e. just prepend `get_` to the regular `list_items` method.

    To create an instance of PreselectedListInputHandler pass the window to the constructor, and optionally a second
    argument `initial_value` to preselect a value. Usually you then want to use the `next_input` method to push another
    InputHandler onto the input stack.

    Inspired by https://github.com/sublimehq/sublime_text/issues/5507.
    """

    def __init__(
        self, window: sublime.Window, initial_value: str | sublime.ListInputItem | None = None
    ) -> None:
        super().__init__()
        self._window = window
        self._initial_value = initial_value

    @final
    def list_items(self) -> ListItemsReturn:
        if self._initial_value is not None:
            sublime.set_timeout(self._select_and_reset)
            return [self._initial_value], 0  # pyright: ignore[reportReturnType]
        else:
            return self.get_list_items()

    def _select_and_reset(self) -> None:
        self._initial_value = None
        if self._window.is_valid():
            self._window.run_command('select')

    @abstractmethod
    def get_list_items(self) -> ListItemsReturn:
        raise NotImplementedError()


class DynamicListInputHandler(sublime_plugin.ListInputHandler, metaclass=ABCMeta):
    """ A ListInputHandler which can update its items while typing in the input field.

    Subclasses of DynamicListInputHandler must not implement the `list_items` method, but can override
    `get_list_items` for the initial list items. The `on_modified` method will be called after a small delay (debounced)
    whenever changes were made to the input text. You can use this to call the `update` method with a list of
    `ListInputItem`s to update the list items.

    To create an instance of the derived class pass the command instance and the command arguments to the constructor,
    like this:

    def input(self, args):
        return MyDynamicListInputHandler(self, args)

    For now, the type of the command must be a WindowCommand, but maybe it can be generalized later if needed.
    This class will set and modify `_items` and '_text' attributes of the command, so make sure that those attribute
    names are not used in another way in the command's class.
    """

    def __init__(self, command: sublime_plugin.WindowCommand, args: dict[str, Any]) -> None:
        super().__init__()
        self.command = command
        self.args = args
        self.text = getattr(command, '_text', '')
        self.listener: sublime_plugin.TextChangeListener | None = None
        self.input_view: sublime.View | None = None

    def _attach_listener(self) -> None:
        for buffer in sublime._buffers():  # type: ignore
            view = buffer.primary_view()
            # This condition to find the input field view might not be sufficient if there is another command palette
            # open in another group in the same window
            if view.element() == 'command_palette:input' and view.window() == self.command.window:
                self.input_view = view
                break
        else:
            raise RuntimeError('Could not find the Command Palette input field view')
        self.listener = InputListener(self)
        self.listener.attach(buffer)
        if ST_VERSION < 4161 and self.input_view:
            # Workaround for initial_selection not working; see https://github.com/sublimehq/sublime_text/issues/6175
            selection = self.input_view.sel()
            selection.clear()
            selection.add(len(self.text))

    def _detach_listener(self) -> None:
        if self.listener and self.listener.is_attached():
            self.listener.detach()

    @final
    def list_items(self) -> list[sublime.ListInputItem]:
        if not self.text:  # Show initial items when the command was just invoked
            return self.get_list_items() or [sublime.ListInputItem("No Results", "")]
        else:  # Items were updated after typing
            items = getattr(self.command, '_items', None)
            if items:
                if ST_VERSION >= 4157:
                    return items
                else:
                    # Trick to select the topmost item; see https://github.com/sublimehq/sublime_text/issues/6162
                    sublime.set_timeout(self._select_first_row)
                    return [sublime.ListInputItem("", "")] + items
            return [sublime.ListInputItem(f'No Symbol found: "{self.text}"', "")]

    def _select_first_row(self) -> None:
        self.command.window.run_command('move', {'by': 'lines', 'forward': True})

    def initial_text(self) -> str:
        setattr(self.command, '_text', '')
        sublime.set_timeout(self._attach_listener)
        return self.text

    def initial_selection(self) -> list[tuple[int, int]]:
        pt = len(self.text)
        return [(pt, pt)]

    def validate(self, text: str) -> bool:
        return bool(text)

    def cancel(self) -> None:
        self._detach_listener()

    def confirm(self, text: str) -> None:
        self._detach_listener()

    def on_modified(self, text: str) -> None:
        """ Called after changes have been made to the input, with the text of the input field passed as argument. """
        pass

    def get_list_items(self) -> list[sublime.ListInputItem]:
        """ The list items which are initially shown. """
        return []

    def update(self, items: list[sublime.ListInputItem]) -> None:
        """ Call this method to update the list items. """
        if not self.input_view:
            return
        setattr(self.command, '_items', items)
        text = self.input_view.substr(sublime.Region(0, self.input_view.size()))
        setattr(self.command, '_text', text)
        self.command.window.run_command('chain', {
            'commands': [
                # Note that the command palette changes its width after the update, due to the hide_overlay command
                ['hide_overlay', {}],
                [self.command.name(), self.args]
            ]
        })


class InputListener(sublime_plugin.TextChangeListener):

    def __init__(self, handler: DynamicListInputHandler) -> None:
        super().__init__()
        self.weakhandler = weakref.ref(handler)

    @classmethod
    def is_applicable(cls, buffer: sublime.Buffer) -> bool:
        return False

    @debounced
    def on_text_changed(self, changes: list[sublime.TextChange]) -> None:
        handler = self.weakhandler()
        if not handler:
            return
        view = self.buffer.primary_view()
        if view and view.id():
            handler.on_modified(view.substr(sublime.Region(0, view.size())))
