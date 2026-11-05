# Migrating from non-async LspPlugin to async LspPlugin

The LSP package now uses [`asyncio`](https://docs.python.org/3/library/asyncio.html). Many methods have been refactored to use `async` constructs, and your `LspPlugin` gains asynchronous capabilities too.

!!! note
    This is a migration guide for packages that are using the `LspPlugin` class instead of the `AbstractPlugin` class. For migrating from `AbstractPlugin` to `LspPlugin`, please follow [this guide first](migrating_to_lsp_plugin.md).

## Overview of changes

Most methods of the `LspPlugin` class now have an asynchronous counterpart. You can opt into each one **individually**, so there is no need to migrate all of your method implementations at once. In the table below, the left column lists the old method and the right column lists its asynchronous counterpart. Existing blocking methods that have an asynchronous alternative are marked `@deprecated`.

| non-asynchronous `LspPlugin` | asynchronous `LspPlugin` |
|---|---|
| `on_pre_start_async(context)` | `async on_pre_start(context)` |
| `on_initialized_async()` | `async on_initialized()` |
| `on_pre_send_request_async(request, view)` | `async on_pre_send_request(request, view)` |
| `on_pre_send_response_async(response)` | `async on_pre_send_response(response)` |
| `on_pre_send_notification_async(notification)` | `async on_pre_send_notification(notification)` |
| `on_server_request_async(request)` | `async on_server_request(request)` |
| `on_server_response_async(response)` | `async on_server_response(response)` |
| `on_server_notification_async(notification)` | `async on_server_notification(notification)` |
| `on_text_changed_async(session_buffer)` | `async on_text_changed(session_buffer)` |
| `on_session_end_async(exit_code, exception)` | `async on_session_end(exit_code, exception)` |
| *(not present)* | `async on_transport_ready(reader, writer)` |

Beyond these methods, there are also migration paths for existing `@command_handler`, `@request_handler`, and `@uri_handler` methods, described below.

## Migration Suggestions

Unlike the migration from `AbstractPlugin` to `LspPlugin`, various components of your plugin may be migrated at different times. We predict there will be concerns that will be common around the `on_pre_start_async` method, which we'll describe below in a subsection.

### Realize `Session.request` exists

You may send a request payload to the language server using one of these four methods on the `Session` class:

- `Session.send_request`
- `Session.send_request_async`
- `Session.send_request_task`
- `Session.send_request_task_2`

All of these methods are `@deprecated`.

Use `Session.request` instead; see its docstring for details. Because it is an asynchronous method, you must call it from another `async` function or method. You can do that by replacing various `LspPlugin` methods with their asynchronous counterparts, or by using one of the two utility functions described in the next section.

### Replace `sublime.set_timeout_async` with `run_coroutine` or `run_on_asyncio_thread`

Before the LSP package used `asyncio` and `async` functions, the common pattern to use a `Session` object and its methods was to run code on Sublime's worker thread (the thread that [`sublime.set_timeout_async`](https://www.sublimetext.com/docs/api_reference.html#sublime.set_timeout_async) targets).

The pattern used to be:

```python
from LSP.plugin import LspTextCommand
import sublime

class SomeCustomCommand(LspTextCommand):

    def run(self, **kwargs: Any) -> None:
        # This block of code runs on the *ST main* thread.
        sublime.set_timeout_async(self.run_async, **kwargs)

    def run_async(self, **kwargs: Any) -> None:
        # This block of code runs on the *ST worker* thread.
        if session := self.session_by_name("some-language-server-name"):
            session.send_request(Request(...), self.handle_response, self.handle_error)

    def handle_response(self, payload: LSPAny) -> None:
        # This block of code runs on the *ST worker thread*.
        pass

    def handle_error(self, error: ResponseError) -> None:
        # This block of code runs on the *ST worker thread*.
        pass
```

Above, there was heavy use of the ST worker thread, by design. Most code of the LSP package ran there, to keep the main thread free for rendering text.

Since the use of `asyncio` in the LSP package, the ST worker thread is almost completely eschewed.

Instead, a new thread, provided by the `sublime_aio` library, is used heavily instead. This thread is central to your package as well.

There are two ways to "get on the asyncio thread":

1. Use `LSP.plugin.run_coroutine`: this utility function can be called from any thread, and schedules a new _coroutine object_, i.e. a function or method declared with the `async def` keywords:
    ```python
    from LSP.plugin import Error, LspTextCommand, run_coroutine

    class SomeCustomCommand(LspTextCommand):

        def run(self, **kwargs: Any) -> None:
            # This block of code runs on the *ST main* thread.
            run_coroutine(self._run(**kwargs))

        async def _run(self, **kwargs: Any) -> None:
            # This block of code runs on the *sublime_aio* thread.
            if session := self.session_by_name("some-language-server-name"):
                # Note the use of the `await` keyword. No need to set up callbacks.
                response = await session.request(Request(...))
                if isinstance(response, Error):
                    # handle error
                    return
                # handle response
    ```
2. Use `LSP.plugin.run_on_asyncio_thread`: this utility function can be called from any thread, and schedules a new _function_:
    ```python
    from LSP.plugin import run_on_asyncio_thread

    def some_func_that_is_not_async_but_has_to_run_on_asyncio_context():
        pass

    run_on_asyncio_thread(some_func_that_is_not_async_but_has_to_run_on_asyncio_context)
    ```

### Replace `Session.open_uri_async` and `Session.open_location_async`

The Promise-based `Session.open_uri_async` and `Session.open_location_async` methods are deprecated in favor of the `async` methods `Session.open_uri` and `Session.open_location`. Note that the new methods return `False` instead of `None` when the URI can't be handled.

```python
# Before
session.open_location_async(location).then(on_opened)
```

```python
# After
on_opened(await session.open_location(location) or None)
```

`Session.open_scratch_buffer` still returns a `Promise`, which can be both chained with `.then()` and awaited.

### Replace `purge_changes_async` with `purge_changes`

The view listener's `purge_changes_async` method, used to send pending document changes to the server before making a request, is deprecated in favor of the `async` method `purge_changes`. The deprecated method only schedules the changes to be sent and returns before they are, while awaiting `purge_changes` guarantees that they have been sent.

```python
# Before
view_listener.purge_changes_async()
session.send_request_task(request).then(on_result)
```

```python
# After
await view_listener.purge_changes()
on_result(await session.request(request))
```

`SessionBuffer.purge_changes_async` was removed. Use the view listener's `purge_changes` instead.

### Replace usage of `Promise` with `async` in `@command_handler`

Command handlers used to return a `Promise` object. They can be readily replaced with `async` counterparts:

```python
# Before
from LSP.plugin import command_handler
from LSP.plugin import LSPAny

@command_handler('typescript.rename')
def on_foo_bar(self, arguments: list[LSPAny] | None) -> Promise[LSPAny]:
    return Promise.resolve(handle_command(arguments))
```

```python
# After
from LSP.plugin import command_handler
from LSP.plugin import LSPAny

@command_handler('typescript.rename')
async def on_foo_bar(self, arguments: list[LSPAny] | None) -> LSPAny:
    return handle_command(arguments)
```

### Replace usage of `Promise` with `async` in `@request_handler`

Request handlers used to return a `Promise` object. They can be readily replaced with `async` counterparts:

```python
# Before
from LSP.plugin import request_handler

@request_handler('eslint/openDoc')
def on_eslint_open_doc(self, params: TextDocumentIdentifier) -> Promise[bool]:
    ...
```

```python
# After
from LSP.plugin import request_handler

@request_handler('eslint/openDoc')
async def on_eslint_open_doc(self, params: TextDocumentIdentifier) -> bool:
    ...
```

### Replace usage of `Promise` with `async` in `@uri_handler`

URI handlers for language-server-specific URI schemes used to return a `Promise` object. They can be readily replaced with `async` counterparts:

```python
# Before
from LSP.plugin import uri_handler

@uri_handler('foo')
def on_open_foo_uri(self, uri: DocumentUri, flags: sublime.NewFileFlags) -> Promise[sublime.Sheet | None]:
    title, content, syntax = render_foo_uri(uri)
    if session := self.weaksession():
        return session.open_scratch_buffer(title, content, syntax, flags).then(lambda view: view.sheet())
    return Promise.resolve(None)
```

```python
# After
from LSP.plugin import uri_handler

@uri_handler('foo')
async def on_open_foo_uri(self, uri: DocumentUri, flags: sublime.NewFileFlags) -> sublime.Sheet | None:
    title, content, syntax = render_foo_uri(uri)
    if session := self.weaksession():
        view = await session.open_scratch_buffer(title, content, syntax, flags)
        return view.sheet()
    return None
```

### Don't run long-running functions in a coroutine function

Some functions may block for a while. Because `asyncio` is single-threaded, running such a function on its loop thread prevents all other tasks from making progress. To run such functions, use either:

- `LSP.plugin.run_on_threadpool`: utility coroutine function to use the asyncio loop's [default executor](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor).
- `LSP.plugin.run_on_worker_thread`: utility coroutine function to use Sublime's worker thread.

Note that these are both _coroutine functions_ and they _must be awaited_.

### Defer migration of `LspPlugin.on_pre_start_async`

The `on_pre_start_async` method of `LspPlugin` is supposed to download and unzip a language server binary, or it may have to run NPM, uv, or some other package manager tool for installing the language server files. The functions needed for these operations were all blocking:

- Downloading was usually done with the [`urllib.request.urlretrieve`](https://docs.python.org/3/library/urllib.request.html#urllib.request.urlretrieve) function.
- Unzipping was usually done with the [`zipfile`](https://docs.python.org/3/library/zipfile.html) module. Or perhaps [`tarfile`](https://docs.python.org/3/library/tarfile.html).
- Running a tool was usually done with the [`subprocess`](https://docs.python.org/3/library/subprocess.html) module.

There exist asynchronous counterparts to these functions, but they're not trivial to replace. Here is a non-exhaustive replacement list:

- Downloading a file asynchronously can be done with the [`aiosonic`](https://aiosonic.readthedocs.io/en/latest/examples.html#download-file) library. To use aiosonic in ST, follow the instructions [in this git commit of packagecontrol/channel](https://github.com/packagecontrol/channel/commit/e433f8bbc42d2a318f1e2073c2e0f8473d6680ec). Alternatively, [Package Control may soon vendor the `httpx2` library](https://github.com/sublimehq/package_control/tree/five-point-oh/httpx2-py314/package_control/vendor/httpx2), in which case [`httpx2`](https://pydantic.dev/docs/httpx2/guides/async/) may be used.
- Unzipping/untarring: use the `tarfile` or `zipfile` module like you normally would, but invoke them via `LSP.plugin.run_on_threadpool`.
- Running a tool: use [`asyncio.subprocess`](https://docs.python.org/3/library/asyncio-subprocess.html).

The best practices for replacing these blocking functions with asynchronous counterparts are still in flux, so we suggest to delay this refactoring. Also note:

- The old `on_pre_start_async` method will run via `LSP.plugin.run_on_threadpool`.
- The new `async on_pre_start` will run in the `sublime_aio` / `asyncio` thread. So definitely do not run long, blocking functions in that case!

### Dispatching additional background tasks

Previously, when you needed to dispatch a function to be run in the background or some time later, you would use `sublime.set_timeout_async`. While that's still possible, you cannot run a coroutine function using `sublime.set_timeout_async`.

To dispatch a coroutine in the background, the `asyncio` module offers the function `asyncio.create_task`. However, the loop implementation internally only keeps a _weak reference_ to the spawned task. It is the responsibility of the caller to keep the returned `asyncio.Task` handle around in some data structure.

To ease creating background tasks with coroutines, there is the `Session.create_task` method. This method will keep a strong reference to the spawned task, and moreover automatically remove the reference once the task is done.

```python
import asyncio

# Some background task that needs to run in response to a notification from the server.
async def _my_background_task(self) -> None:
    ...
    await asyncio.sleep(1)
    ...

# The notification handler.
@notification_handler('some/custom/notification')
def on_some_custom_notification(self, params: str) -> None:
    if session := self.weaksession():
        # Spawn the background task, not having to care about the returned asyncio.Task handle.
        session.create_task(self._my_background_task())
```
