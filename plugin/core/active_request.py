from .sessions import SessionViewProtocol
from .progress import ProgressReporter
from .progress import ViewProgressReporter
from .progress import WindowProgressReporter
from .protocol import Request
from typing import Any, Dict, Optional
from weakref import ref
import sublime


class ActiveRequest:
    """
    Holds state per request.
    """

    def __init__(self, sv: SessionViewProtocol, request_id: int, request: Request) -> None:
        # sv is the parent object; there is no need to keep it alive explicitly.
        self.weaksv = ref(sv)
        self.request_id = request_id
        self.request = request
        self.progress = None  # type: Optional[ProgressReporter]
        # `request.progress` is either a boolean or a string. If it's a boolean, then that signals that the server does
        # not support client-initiated progress. However, for some requests we still want to notify some kind of
        # progress to the end-user. This is communicated by the boolean value being "True".
        # If `request.progress` is a string, then this string is equal to the workDoneProgress token. In that case, the
        # server should start reporting progress for this request. However, even if the server supports workDoneProgress
        # then we still don't know for sure whether it will actually start reporting progress. So we still want to
        # put a line in the status bar if the request takes a while even if the server promises to report progress.
        if request.progress:
            # Keep a weak reference because we don't want this delayed function to keep this object alive.
            weakself = ref(self)

            def show() -> None:
                this = weakself()
                # If the server supports client-initiated progress, then it should have sent a "progress begin"
                # notification. In that case, `this.progress` should not be None. So if `this.progress` is None
                # then the server didn't notify in a timely manner and we will start putting a line in the status bar
                # about this request taking a long time (>200ms).
                if this is not None and this.progress is None:
                    # If this object is still alive then that means the request hasn't finished yet after 200ms,
                    # so put a message in the status bar to notify that this request is still in progress.
                    this.progress = this._start_progress_reporter_async(this.request.method)

            sublime.set_timeout_async(show, 200)

    def _start_progress_reporter_async(
        self,
        title: str,
        message: Optional[str] = None,
        percentage: Optional[float] = None
    ) -> Optional[ProgressReporter]:
        sv = self.weaksv()
        if not sv:
            return None
        if self.request.view is not None:
            key = "lspprogressview-{}-{}-{}".format(sv.session.config.name, self.request.view.id(), self.request_id)
            return ViewProgressReporter(self.request.view, key, title, message, percentage)
        else:
            key = "lspprogresswindow-{}-{}-{}".format(sv.session.config.name, sv.session.window.id(), self.request_id)
            return WindowProgressReporter(sv.session.window, key, title, message, percentage)

    def update_progress_async(self, params: Dict[str, Any]) -> None:
        value = params['value']
        kind = value['kind']
        message = value.get("message")
        percentage = value.get("percentage")
        if kind == 'begin':
            title = value["title"]
            # This would potentially overwrite the "manual" progress that activates after 200ms, which is OK.
            self.progress = self._start_progress_reporter_async(title, message, percentage)
        elif kind == 'report':
            if self.progress:
                self.progress(message, percentage)
