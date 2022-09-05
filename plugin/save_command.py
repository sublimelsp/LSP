from .core.registry import LspTextCommand
from .core.settings import userprefs
from .core.typing import Callable, List, Type
from abc import ABCMeta, abstractmethod
import sublime
import sublime_plugin


class SaveTask(metaclass=ABCMeta):
    """
    Base class for tasks that run on save.

    Note: The whole task runs on the async thread.
    """

    @classmethod
    @abstractmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        pass

    def __init__(self, task_runner: LspTextCommand, on_done: Callable[[], None]):
        self._task_runner = task_runner
        self._on_done = on_done
        self._completed = False
        self._cancelled = False
        self._status_key = type(self).__name__

    def run_async(self) -> None:
        self._erase_view_status()
        sublime.set_timeout_async(self._on_timeout, userprefs().on_save_task_timeout_ms)

    def _on_timeout(self) -> None:
        if not self._completed and not self._cancelled:
            self._set_view_status('LSP: Timeout processing {}'.format(self.__class__.__name__))
            self._cancelled = True
            self._on_done()

    def cancel(self) -> None:
        self._cancelled = True

    def _set_view_status(self, text: str) -> None:
        self._task_runner.view.set_status(self._status_key, text)
        sublime.set_timeout_async(self._erase_view_status, 5000)

    def _erase_view_status(self) -> None:
        self._task_runner.view.erase_status(self._status_key)

    def _on_complete(self) -> None:
        assert not self._completed
        self._completed = True
        if not self._cancelled:
            self._on_done()

    def _purge_changes_async(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self._task_runner.view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes_async()  # type: ignore
                break


class LspSaveCommand(LspTextCommand):
    """
    A command used as a substitute for native save command. Runs code actions and document
    formatting before triggering the native save command.
    """
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
        sublime.set_timeout_async(self._trigger_on_pre_save_async)
        for Task in self._tasks:
            if Task.is_applicable(self.view):
                self._pending_tasks.append(Task(self, self._on_task_completed_async))
        if self._pending_tasks:
            sublime.set_timeout_async(self._run_next_task_async)
        else:
            self._trigger_native_save()

    def _trigger_on_pre_save_async(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self.view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.trigger_on_pre_save_async()  # type: ignore
                break

    def _run_next_task_async(self) -> None:
        current_task = self._pending_tasks[0]
        current_task.run_async()

    def _on_task_completed_async(self) -> None:
        self._pending_tasks.pop(0)
        if self._pending_tasks:
            self._run_next_task_async()
        else:
            self._trigger_native_save()

    def _trigger_native_save(self) -> None:
        # Triggered from set_timeout to preserve original semantics of on_pre_save handling
        sublime.set_timeout(lambda: self.view.run_command('save', {"async": True}))


class LspSaveAllCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        done = set()
        for view in self.window.views():
            buffer_id = view.buffer_id()
            if buffer_id in done:
                continue
            if not view.is_dirty():
                continue
            done.add(buffer_id)
            view.run_command("lsp_save", None)
