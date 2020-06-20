from .core.typing import Callable, List, Type
from abc import ABCMeta, abstractmethod
import sublime
import sublime_plugin


class SaveTask(metaclass=ABCMeta):
    """
    Base class for tasks that run on save.

    Takes care of timing out lask after specified timeout provided that base run() is called.
    """

    DEFAULT_TASK_TIMEOUT = 1000

    @classmethod
    @abstractmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        pass

    def __init__(self, view: sublime.View, on_done: Callable[[], None]):
        self._view = view
        self._on_done = on_done
        self._completed = False
        self._cancelled = False
        self._status_key = 'lsp_save_task_timeout'

    def run(self) -> None:
        self._erase_view_status()
        sublime.set_timeout(self._on_timeout, self.get_task_timeout_ms())

    def _on_timeout(self) -> None:
        if not self._completed and not self._cancelled:
            self._set_view_status('LSP: Timeout processing {}'.format(self.__class__.__name__))
            self._cancelled = True
            self._on_done()

    def get_task_timeout_ms(self) -> int:
        return self.DEFAULT_TASK_TIMEOUT

    def cancel(self) -> None:
        self._cancelled = True

    def _set_view_status(self, text: str) -> None:
        self._view.set_status(self._status_key, text)
        sublime.set_timeout(self._erase_view_status, 5000)

    def _erase_view_status(self) -> None:
        self._view.erase_status(self._status_key)

    def _on_complete(self) -> None:
        assert not self._completed
        self._completed = True
        if not self._cancelled:
            self._on_done()

    def _purge_changes_if_needed(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self._view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes()  # type: ignore
                break


class LspSaveCommand(sublime_plugin.TextCommand):
    """
    A command used as a substitute for native save command. Runs code actions and document
    formatting before triggering the native save command.
    """
    SKIP_ON_PRE_SAVE_KEY = 'lsp-skip-pre-save'
    _tasks = []  # type: List[Type[SaveTask]]

    @classmethod
    def register_task(cls, task: Type[SaveTask]) -> None:
        assert task not in cls._tasks
        cls._tasks.append(task)

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._pending_tasks = []  # type: List[SaveTask]

    def run(self, edit: sublime.Edit) -> None:
        if self._pending_tasks:
            for task in self._pending_tasks:
                task.cancel()
            self._pending_tasks = []
        for Task in self._tasks:
            if Task.is_applicable(self.view):
                self._pending_tasks.append(Task(self.view, self._on_task_completed))
        if self._pending_tasks:
            self._trigger_on_pre_save()
            # Ensure that the next "on_pre_save" that runs on native save is skipped.
            self.view.settings().set(self.SKIP_ON_PRE_SAVE_KEY, '1')
            self._run_next_task()
        else:
            self._trigger_native_save()

    def _trigger_on_pre_save(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self.view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.on_pre_save()  # type: ignore
                break

    def _run_next_task(self) -> None:
        current_task = self._pending_tasks[0]
        current_task.run()

    def _on_task_completed(self) -> None:
        self._pending_tasks.pop(0)
        if self._pending_tasks:
            self._run_next_task()
        else:
            self._trigger_native_save()

    def _trigger_native_save(self) -> None:
        # Triggered from set_timeout to preserve original semantics of on_pre_save handling
        sublime.set_timeout(lambda: self.view.run_command('save', {"async": True}))
