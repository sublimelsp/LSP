# Stubs for sublime_plugin.py
from sublime import Buffer, CompletionItem, CompletionList, Edit, Html, ListInputItem, Settings, TextChange, View, Window
from typing import Any


view_event_listeners: dict[int, list[ViewEventListener]]  # undocumented


class CommandInputHandler:

    def name(self) -> str:
        """
        The command argument name this input handler is editing. Defaults to `foo_bar` for an input handler named
        `FooBarInputHandler`.
        """
        ...

    def placeholder(self) -> str:
        """
        Placeholder text is shown in the text entry box before the user has entered anything. Empty by default.
        """
        ...

    def initial_text(self) -> str:
        """
        Initial text shown in the text entry box. Empty by default.
        """
        ...

    def initial_selection(self) -> list[tuple[int, int]]:
        """
        A list of 2-element tuples, defining the initially selected parts of the initial text.
        """
        ...

    def preview(self, text: str) -> str | Html:
        """
        Called whenever the user changes the text in the entry box. The returned value (either plain text or HTML) will
        be shown in the preview area of the Command Palette.
        """
        ...

    def validate(self, text: str) -> bool:
        """
        Called whenever the user presses enter in the text entry box. Return `False` to disallow the current value.
        """
        ...

    def cancel(self) -> None:
        """
        Called when the input handler is canceled, either by the user pressing backspace or escape.
        """
        ...

    def confirm(self, text: str) -> None:
        """
        Called when the input is accepted, after the user has pressed enter and the text has been validated.
        """
        ...

    def next_input(self, args: Any) -> CommandInputHandler | None:
        """
        Return the next input after the user has completed this one. May return
        :py:`None` to indicate no more input is required, or
        `sublime_plugin.BackInputHandler()` to indicate that the input handler
        should be popped off the stack instead.
        """
        ...

    def want_event(self) -> bool:
        """
        Whether the `validate()` and `confirm()` methods should received a second `Event` parameter. Returns `False` by
        default.
        """
        ...


class BackInputHandler(CommandInputHandler):
    ...


class TextInputHandler(CommandInputHandler):
    """
    TextInputHandlers can be used to accept textual input in the Command Palette. Return a subclass of this from
    `Command.input()`.

    For an input handler to be shown to the user, the command returning the input handler MUST be made available in the
    Command Palette by adding the command to a `Default.sublime-commands` file.
    """
    def description(self, text: str) -> str:
        """
        The text to show in the Command Palette when this input handler is not at the top of the input handler stack.
        Defaults to the text the user entered.
        """
        ...


class ListInputHandler(CommandInputHandler):
    """
    ListInputHandlers can be used to accept a choice input from a list items in the Command Palette. Return a subclass
    of this from `Command.input()`.

    For an input handler to be shown to the user, the command returning the input handler MUST be made available in the
    Command Palette by adding the command to a `Default.sublime-commands` file.
    """
    def list_items(self) -> list[str] | tuple[list[str], int] | list[tuple[str, Any]] | \
            tuple[list[tuple[str, Any]], int] | list[ListInputItem] | tuple[list[ListInputItem], int]:
        """
        This method should return the items to show in the list.

        The returned value may be a `list` of items, or a 2-element `tuple` containing a list of items, and an `int`
        index of the item to pre-select.

        Each item in the list may be one of:

        * A string used for both the row text and the value passed to the command
        * A 2-element tuple containing a string for the row text, and a `Value` to pass to the command
        * A `sublime.ListInputItem` object
        """
        ...

    def description(self, value: Any, text: str) -> str:
        """
        The text to show in the Command Palette when this input handler is not at the top of the input handler stack.
        Defaults to the text of the list item the user selected.
        """
        ...


class Command:

    def name(self) -> str:
        """
        Return the name of the command. By default this is derived from the name of the class.
        """
        ...

    def is_enabled(self, **kwargs: dict[str, Any]) -> bool:
        """
        Return whether the command is able to be run at this time. Command arguments are passed as keyword arguments.
        The default implementation simply always returns `True`.
        """
        ...

    def is_visible(self, **kwargs: dict[str, Any]) -> bool:
        """
        Return whether the command should be shown in the menu at this time. Command arguments are passed as keyword
        arguments. The default implementation always returns `True`.
        """
        ...

    def is_checked(self, **kwargs: dict[str, Any]) -> bool:
        """
        Return whether a checkbox should be shown next to the menu item. Command arguments are passed as keyword
        arguments. The `.sublime-menu` file must have the `"checkbox"` key set to `true` for this to be used.
        """
        ...

    def description(self, **kwargs: dict[str, Any]) -> str | None:
        """
        Return a description of the command with the given arguments. Command arguments are passed as keyword arguments.
        Used in the menu, if no caption is provided. Return `None` to get the default description.
        """
        ...

    def want_event(self) -> bool:
        """
        Return whether to receive an `Event` argument when the command is triggered by a mouse action. The event
        information allows commands to determine which portion of the view was clicked on. The default implementation
        returns `False`.
        """
        ...

    def input(self, args: dict[str, Any]) -> CommandInputHandler | None:
        """
        If this returns something other than `None`, the user will be prompted for an input before the command is run in
        the Command Palette.
        """
        ...

    def input_description(self) -> str:
        """
        Allows a custom name to be show to the left of the cursor in the input box, instead of the default one generated
        from the command name.
        """
        ...

    def run(self, **kwargs: dict[str, Any]) -> None:
        """
        Called when the command is run. Command arguments are passed as keyword arguments.
        """
        ...


class ApplicationCommand(Command):
    """
    A `Command` instantiated just once.
    """
    ...


class WindowCommand(Command):
    """
    A `Command` instantiated once per window. The `Window` object may be retrieved via `self.window`.
    """
    window: Window
    """The `Window` this command is attached to."""

    def __init__(self, window: Window) -> None:
        ...


class TextCommand(Command):
    """
    A `Command` instantiated once per `View`. The `View` object may be retrieved
    via `self.view <view>`.
    """
    view: View
    """The `View` this command is attached to."""

    def __init__(self, view: View) -> None:
        ...

    def run(self, edit: Edit, **kwargs: dict[str, Any]) -> None:  # type: ignore[override]
        """
        Called when the command is run. Command arguments are passed as keyword arguments.
        """
        ...


class EventListener:

    def on_init(self, views: list[View]) -> None:
        """
        Called once with a list of views that were loaded before the EventListener was instantiated.
        """
        ...

    def on_exit(self) -> None:
        """
        Called once after the API has shut down, immediately before the plugin_host process exits.
        """
        ...

    def on_new(self, view: View) -> None:
        """
        Called when a new file is created.
        """
        ...

    def on_new_async(self, view: View) -> None:
        """
        Called when a new buffer is created. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_associate_buffer(self, buffer: Buffer) -> None:
        """
        Called when a buffer is associated with a file. `buffer` will be a `Buffer` object.
        """
        ...

    def on_associate_buffer_async(self, buffer: Buffer) -> None:
        """
        Called when a buffer is associated with file. Runs in a separate thread, and does not block the application.
        `buffer` will be a `Buffer` object.
        """
        ...

    def on_clone(self, view: View) -> None:
        """
        Called when a view is cloned from an existing one.
        """
        ...

    def on_clone_async(self, view: View) -> None:
        """
        Called when a view is cloned from an existing one. Runs in a separate thread, and does not block the
        application.
        """
        ...

    def on_load(self, view: View) -> None:
        """
        Called when the file is finished loading.
        """
        ...

    def on_load_async(self, view: View) -> None:
        """
        Called when the file is finished loading. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_reload(self, view: View) -> None:
        """
        Called when the View is reloaded.
        """
        ...

    def on_reload_async(self, view: View) -> None:
        """
        Called when the View is reloaded. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_revert(self, view: View) -> None:
        """
        Called when the View is reverted.
        """
        ...

    def on_revert_async(self, view: View) -> None:
        """
        Called when the View is reverted. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_pre_move(self, view: View) -> None:
        """
        Called right before a view is moved between two windows, passed the `View` object.
        """
        ...

    def on_post_move(self, view: View) -> None:
        """
        Called right after a view is moved between two windows, passed the `View` object.
        """
        ...

    def on_post_move_async(self, view: View) -> None:
        """
        Called right after a view is moved between two windows, passed the `View` object. Runs in a separate thread, and
        does not block the application.
        """
        ...

    def on_pre_close(self, view: View) -> None:
        """
        Called when a view is about to be closed. The view will still be in the window at this point.
        """
        ...

    def on_close(self, view: View) -> None:
        """
        Called when a view is closed (note, there may still be other views into the same buffer).
        """
        ...

    def on_pre_save(self, view: View) -> None:
        """
        Called just before a view is saved.
        """
        ...

    def on_pre_save_async(self, view: View) -> None:
        """
        Called just before a view is saved. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_post_save(self, view: View) -> None:
        """
        Called after a view has been saved.
        """
        ...

    def on_post_save_async(self, view: View) -> None:
        """
        Called after a view has been saved. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_modified(self, view: View) -> None:
        """
        Called after changes have been made to a view.
        """
        ...

    def on_modified_async(self, view: View) -> None:
        """
        Called after changes have been made to a view. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_selection_modified(self, view: View) -> None:
        """
        Called after the selection has been modified in a view.
        """
        ...

    def on_selection_modified_async(self, view: View) -> None:
        """
        Called after the selection has been modified in a view. Runs in a separate thread, and does not block the
        application.
        """
        ...

    def on_activated(self, view: View) -> None:
        """
        Called when a view gains input focus.
        """
        ...

    def on_activated_async(self, view: View) -> None:
        """
        Called when a view gains input focus. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_deactivated(self, view: View) -> None:
        """
        Called when a view loses input focus.
        """
        ...

    def on_deactivated_async(self, view: View) -> None:
        """
        Called when a view loses input focus. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_hover(self, view: View, point: int, hover_zone: int) -> None:
        """
        Called when the user's mouse hovers over the view for a short period.

        - `view` - The view.
        - `point` - The closest point in the view to the mouse location. The mouse may not actually be located adjacent
            based on the value of `hover_zone`.
        - `hover_zone` - Which element in Sublime Text the mouse has hovered over.
        """
        ...

    def on_query_context(self, view: View, key: str, operator: int, operand: str, match_all: bool) -> bool | None:
        """
        Called when determining to trigger a key binding with the given context key. If the plugin knows how to respond
        to the context, it should return either `True` of `False`. If the context is unknown, it should return `None`.

        - `key` - The context key to query. This generally refers to specific state held by a plugin.
        - `operator` - The operator to check against the operand; whether to check equality, inequality, etc.
        - `operand` - The value against which to check using the `operator`.
        - `match_all` - This should be used if the context relates to the selections: does every selection have to
            match (`True`), or is at least one matching enough (`False`)?
        """
        ...

    def on_query_completions(
        self,
        view: View,
        prefix: str,
        locations: list[int]
    ) -> list[str] | tuple[list[str], int] | list[tuple[str, str]] | tuple[list[tuple[str, str]], int] | \
            list[CompletionItem] | tuple[list[CompletionItem], int] | CompletionList | None:
        """
        Called whenever completions are to be presented to the user.

        - `prefix` - The text already typed by the user.
        - `locations` - The list of points being completed. Since this method is called for all completions no matter
            the syntax, `self.view.match_selector(point, relevant_scope)` should be called to determine if the point is
            relevant.

        Returns a list of completions in one of the valid formats or `None` if no completions are provided.
        """
        ...

    def on_text_command(self, view: View, command_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        """
        Called when a text command is issued. The listener may return a (command, arguments) tuple to rewrite the
        command, or `None` to run the command unmodified.
        """
        ...

    def on_window_command(
        self,
        window: Window,
        command_name: str,
        args: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """
        Called when a window command is issued. The listener may return a (command, arguments) tuple to rewrite the
        command, or `None` to run the command unmodified.
        """
        ...

    def on_post_text_command(self, view: View, command_name: str, args: dict[str, Any]) -> None:
        """
        Called after a text command has been executed.
        """
        ...

    def on_post_window_command(self, window: Window, command_name: str, args: dict[str, Any]) -> None:
        """
        Called after a window command has been executed.
        """
        ...

    def on_new_window(self, window: Window) -> None:
        """
        Called when a window is created, passed the Window object.
        """
        ...

    def on_new_window_async(self, window: Window) -> None:
        """
        Called when a window is created, passed the Window object. Runs in a separate thread, and does not block the
        application.
        """
        ...

    def on_pre_close_window(self, window: Window) -> None:
        """
        Called right before a window is closed, passed the Window object.
        """
        ...

    def on_new_project(self, window: Window) -> None:
        """
        Called right after a new project is created, passed the Window object.
        """
        ...

    def on_new_project_async(self, window: Window) -> None:
        """
        Called right after a new project is created, passed the Window object. Runs in a separate thread, and does not
        block the application.
        """
        ...

    def on_load_project(self, window: Window) -> None:
        """
        Called right after a project is loaded, passed the Window object.
        """
        ...

    def on_load_project_async(self, window: Window) -> None:
        """
        Called right after a project is loaded, passed the Window object. Runs in a separate thread, and does not block
        the application.
        """
        ...

    def on_pre_save_project(self, window: Window) -> None:
        """
        Called right before a project is saved, passed the Window object.
        """
        ...

    def on_post_save_project(self, window: Window) -> None:
        """
        Called right after a project is saved, passed the Window object.
        """
        ...

    def on_post_save_project_async(self, window: Window) -> None:
        """
        Called right after a project is saved, passed the Window object. Runs in a separate thread, and does not block
        the application.
        """
        ...

    def on_pre_close_project(self, window: Window) -> None:
        """
        Called right before a project is closed, passed the Window object.
        """
        ...


class ViewEventListener:
    """
    A class that provides similar event handling to `EventListener`, but bound to a specific view. Provides class
    method-based filtering to control what views objects are created for.
    """
    view: View

    @classmethod
    def is_applicable(cls, settings: Settings) -> bool:
        """
        Whether this listener should apply to a view with the given `Settings`.
        """
        ...

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        """
        Whether this listener should apply only to the primary view for a file or all of its clones as well.
        """
        ...

    def __init__(self, view: View) -> None:
        ...

    def on_load(self) -> None:
        """
        Called when the file is finished loading.
        """
        ...

    def on_load_async(self) -> None:
        """
        Same as `on_load` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_reload(self) -> None:
        """
        Called when the file is reloaded.
        """
        ...

    def on_reload_async(self) -> None:
        """
        Same as `on_reload` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_revert(self) -> None:
        """
        Called when the file is reverted.
        """
        ...

    def on_revert_async(self) -> None:
        """
        Same as `on_revert` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_pre_move(self) -> None:
        """
        Called right before a view is moved between two windows.
        """
        ...

    def on_post_move(self) -> None:
        """
        Called right after a view is moved between two windows.
        """
        ...

    def on_post_move_async(self) -> None:
        """
        Same as `on_post_move` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_pre_close(self) -> None:
        """
        Called when a view is about to be closed. The view will still be in the window at this point.
        """
        ...

    def on_close(self) -> None:
        """
        Called when a view is closed (note, there may still be other views into the same buffer).
        """
        ...

    def on_pre_save(self) -> None:
        """
        Called just before a view is saved.
        """
        ...

    def on_pre_save_async(self) -> None:
        """
        Same as `on_pre_save` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_post_save(self) -> None:
        """
        Called after a view has been saved.
        """
        ...

    def on_post_save_async(self) -> None:
        """
        Same as `on_post_save` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_modified(self) -> None:
        """
        Called after changes have been made to the view.
        """
        ...

    def on_modified_async(self) -> None:
        """
        Same as `on_modified` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_selection_modified(self) -> None:
        """
        Called after the selection has been modified in the view.
        """
        ...

    def on_selection_modified_async(self) -> None:
        """
        Called after the selection has been modified in the view. Runs in a separate thread, and does not block the
        application.
        """
        ...

    def on_activated(self) -> None:
        """
        Called when a view gains input focus.
        """
        ...

    def on_activated_async(self) -> None:
        """
        Called when the view gains input focus. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_deactivated(self) -> None:
        """
        Called when the view loses input focus.
        """
        ...

    def on_deactivated_async(self) -> None:
        """
        Called when the view loses input focus. Runs in a separate thread, and does not block the application.
        """
        ...

    def on_hover(self, point: int, hover_zone: int) -> None:
        """
        Called when the user's mouse hovers over the view for a short period.

        - `point` - The closest point in the view to the mouse location. The mouse may not actually be located adjacent
            based on the value of `hover_zone`.
        - `hover_zone` - Which element in Sublime Text the mouse has hovered over.
        """
        ...

    def on_query_context(self, key: str, operator: int, operand: str, match_all: bool) -> bool | None:
        """
        Called when determining to trigger a key binding with the given context key. If the plugin knows how to respond
        to the context, it should return either `True` of `False`. If the context is unknown, it should return `None`.

        - `key` - The context key to query. This generally refers to specific state held by a plugin.
        - `operator` - The operator to check against the operand; whether to check equality, inequality, etc.
        - `operand` - The value against which to check using the `operator`.
        - `match_all` - This should be used if the context relates to the selections: does every selection have to match
            (`True`), or is at least one matching enough (`False`)?
        """
        ...

    def on_query_completions(
        self,
        prefix: str,
        locations: list[int]
    ) -> list[str] | tuple[list[str], int] | list[tuple[str, str]] | tuple[list[tuple[str, str]], int] | \
            list[CompletionItem] | tuple[list[CompletionItem], int] | CompletionList | None:
        """
        Called whenever completions are to be presented to the user.

        - `prefix` - The text already typed by the user.
        - `locations` - The list of points being completed. Since this method is called for all completions no matter
            the syntax, `self.view.match_selector(point, relevant_scope)` should be called to determine if the point is
            relevant.

        Returns a list of completions in one of the valid formats or `None` if no completions are provided.
        """
        ...

    def on_text_command(self, command_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        """
        Called when a text command is issued. The listener may return a `(command, arguments)` tuple to rewrite the
        command, or `None` to run the command unmodified.
        """
        ...

    def on_post_text_command(self, command_name: str, args: dict[str, Any]) -> None:
        """
        Called after a text command has been executed.
        """
        ...


class TextChangeListener:
    """
    A class that provides event handling about text changes made to a specific `Buffer`. Is separate from
    `ViewEventListener` since multiple views can share a single buffer.
    """
    buffer: Buffer

    @classmethod
    def is_applicable(cls, buffer: Buffer) -> bool:
        """
        Whether this listener should apply to the provided buffer.
        """
        ...

    def __init__(self) -> None:
        ...

    def detach(self) -> None:
        """
        Remove this listener from the buffer.

        Async callbacks may still be called after this, as they are queued separately.

        Raises `ValueError` if the listener is not attached.
        """
        ...

    def attach(self, buffer: Buffer) -> None:
        """
        Attach this listener to a buffer.

        Raises `ValueError` if the listener is already attached.
        """
        ...

    def is_attached(self) -> bool:
        """
        Whether the listener is receiving events from a buffer. May not be called from `__init__`.
        """
        ...

    def on_text_changed(self, changes: list[TextChange]) -> None:
        """
        Called once after changes has been made to a buffer, with detailed information about what has changed.
        """
        ...

    def on_text_changed_async(self, changes: list[TextChange]) -> None:
        """
        Same as `on_text_changed` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_revert(self) -> None:
        """
        Called when the buffer is reverted.

        A revert does not trigger text changes. If the contents of the buffer are required here use `View.substr`.
        """
        ...

    def on_revert_async(self) -> None:
        """
        Same as `on_revert` but runs in a separate thread, not blocking the application.
        """
        ...

    def on_reload(self) -> None:
        """
        Called when the buffer is reloaded.

        A reload does not trigger text changes. If the contents of the buffer are required here use `View.substr`.
        """
        ...

    def on_reload_async(self) -> None:
        """
        Same as `on_reload` but runs in a separate thread, not blocking the application.
        """
        ...
