from .typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from .typing import cast
from .typing import final
from abc import ABCMeta
from abc import abstractmethod
import functools
import sublime
import sublime_plugin
import threading
import weakref


ST_VERSION = int(sublime.version())

ListItemsReturn = Union[List[str], Tuple[List[str], int], List[Tuple[str, Any]], Tuple[List[Tuple[str, Any]], int],
                        List[sublime.ListInputItem], Tuple[List[sublime.ListInputItem], int]]

T_Callable = TypeVar('T_Callable', bound=Callable[..., Any])


def debounced(user_function: T_Callable) -> T_Callable:
    """ Yet another debounce implementation :-) """
    DEBOUNCE_TIME = 0.5  # seconds

    @functools.wraps(user_function)
    def wrapped_function(*args: Any, **kwargs: Any) -> None:
        def call_function():
            if hasattr(wrapped_function, '_timer'):
                delattr(wrapped_function, '_timer')
            return user_function(*args, **kwargs)
        timer = getattr(wrapped_function, '_timer', None)
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(DEBOUNCE_TIME, call_function)
        timer.start()
        setattr(wrapped_function, '_timer', timer)
    setattr(wrapped_function, '_timer', None)
    return cast(T_Callable, wrapped_function)


class PreselectedListInputHandler(sublime_plugin.ListInputHandler, metaclass=ABCMeta):
    """
    Similar to ListInputHandler, but allows to preselect a value like some of the input overlays in Sublime Merge.
    Inspired by https://github.com/sublimehq/sublime_text/issues/5507.

    Subclasses of PreselectedListInputHandler must not implement the `list_items` method, but instead `get_list_items`,
    i.e. just prepend `get_` to the regular `list_items` method.

    When an instance of PreselectedListInputHandler is created, it must be given the window as an argument.
    An optional second argument `initial_value` can be provided to preselect a value.
    """

    def __init__(
        self, window: sublime.Window, initial_value: Optional[Union[str, sublime.ListInputItem]] = None
    ) -> None:
        super().__init__()
        self._window = window
        self._initial_value = initial_value

    @final
    def list_items(self) -> ListItemsReturn:
        if self._initial_value is not None:
            sublime.set_timeout(self._select_and_reset)
            return [self._initial_value], 0  # pyright: ignore[reportGeneralTypeIssues]
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

    Derive from this class and override the `get_list_items` method for the initial list items, but don't implement
    `list_items`. Then you can call the `update` method with a list of `ListInputItem`s from within `on_modified`,
    which will be called after changes have been made to the input (with a small delay).

    To create an instance of the derived class pass the command instance and the command arguments to the constructor,
    like this:

    def input(self, args):
        return MyDynamicListInputHandler(self, args)

    For now, the type of the command must be a WindowCommand, but maybe it can be generalized later if needed.
    This class will set and modify `_items` and '_text' attributes of the command, so make sure that those attribute
    names are not used in another way in the command's class.
    """

    def __init__(self, command: sublime_plugin.WindowCommand, args: Dict[str, Any]) -> None:
        super().__init__()
        self.command = command
        self.args = args
        self.text = getattr(command, '_text', '')
        self.listener = None  # type: Optional[sublime_plugin.TextChangeListener]
        self.input_view = None  # type: Optional[sublime.View]

    def attach_listener(self) -> None:
        for buffer in sublime._buffers():  # type: ignore
            view = buffer.primary_view()
            # TODO what to do if there is another command palette open in the same window but in another group?
            if view.element() == 'command_palette:input' and view.window() == self.command.window:
                self.input_view = view
                break
        else:
            raise RuntimeError('Could not find the Command Palette input field view')
        self.listener = InputListener(self)
        self.listener.attach(buffer)
        # --- Hack needed because the initial_selection method is not supported on Python 3.3 API
        selection = self.input_view.sel()
        selection.clear()
        selection.add(len(self.text))
        # --- End of hack

    @final
    def list_items(self) -> List[sublime.ListInputItem]:
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
            return [sublime.ListInputItem('No Symbol found: "{}"'.format(self.text), "")]

    def _select_first_row(self) -> None:
        self.command.window.run_command('move', {'by': 'lines', 'forward': True})

    def initial_text(self) -> str:
        setattr(self.command, '_text', '')
        sublime.set_timeout(self.attach_listener)
        return self.text

    # Not supported on Python 3.3 API :-(
    def initial_selection(self) -> List[Tuple[int, int]]:
        pt = len(self.text)
        return [(pt, pt)]

    def validate(self, text: str) -> bool:
        return bool(text)

    def cancel(self) -> None:
        if self.listener and self.listener.is_attached():
            self.listener.detach()

    def confirm(self, text: str) -> None:
        if self.listener and self.listener.is_attached():
            self.listener.detach()

    def on_modified(self, text: str) -> None:
        """ Called after changes have been made to the input, with the text of the input field passed as argument. """
        pass

    def get_list_items(self) -> List[sublime.ListInputItem]:
        """ The list items which are initially shown. """
        return []

    def update(self, items: List[sublime.ListInputItem]) -> None:
        """ Call this method to update the list items. """
        if not self.input_view:
            return
        setattr(self.command, '_items', items)
        text = self.input_view.substr(sublime.Region(0, self.input_view.size()))
        setattr(self.command, '_text', text)
        self.command.window.run_command('chain', {
            'commands': [
                # TODO is there a way to run the command again without having to close the overlay first, so that the
                # command palette won't change its width?
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
    def on_text_changed(self, changes: List[sublime.TextChange]) -> None:
        handler = self.weakhandler()
        if not handler:
            return
        view = self.buffer.primary_view()
        if view and view.id():
            handler.on_modified(view.substr(sublime.Region(0, view.size())))
