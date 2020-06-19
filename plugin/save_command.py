from .core.typing import Callable, List, Type
from abc import ABCMeta, abstractmethod
import sublime
import sublime_plugin


class SaveTask(metaclass=ABCMeta):
    """
    Base class for tasks that are run on save.
    """

    @classmethod
    @abstractmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        pass

    def __init__(self, view: sublime.View, on_done: Callable[[], None]):
        self._view = view
        self._on_done = on_done
        self._cancelled = False

    def _on_complete(self) -> None:
        if not self._cancelled:
            self._on_done()

    def cancel(self) -> None:
        self._cancelled = True

    def _is_canceled(self) -> bool:
        return self._cancelled

    @abstractmethod
    def run(self) -> None:
        pass


class LspSaveCommand(sublime_plugin.TextCommand):
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
        for Task in self._tasks:
            if Task.is_applicable(self.view):
                self._pending_tasks.append(Task(self.view, self._on_task_completed))
        if self._pending_tasks:
            self._run_next_task()
        else:
            self._trigger_native_save()

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
