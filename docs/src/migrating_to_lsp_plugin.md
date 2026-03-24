# Migrating from AbstractPlugin to LspPlugin

`LspPlugin` is the modern base class for LSP helper packages. It replaces `AbstractPlugin` with a cleaner, context-based API that reduces boilerplate and consolidates the server lifecycle into fewer override points.

!!! note
    `AbstractPlugin` is still supported. You only need to migrate when you are ready to adopt the new API.

---

## Overview of changes

| AbstractPlugin | LspPlugin |
|---|---|
| `name()` | Removed - derived automatically from the package name |
| `configuration()` | Removed - settings file located automatically |
| `storage_path()` | `plugin_storage_path` class attribute (derived automatically) |
| `needs_update_or_installation()` + `install_or_update()` | `install_async(context)` |
| `can_start(window, view, folders, config)` | Raise `PluginStartError` from `install_async` (or other `@classmethod`) |
| `on_pre_start(window, view, folders, config)` | `command(context)`, `working_directory(context)`, `initialization_options(context)` |
| `on_post_start(window, view, folders, config)` | `__init__(weaksession, context)` |
| `is_applicable(view, config)` | `is_applicable(context)` |
| `additional_variables()` | `additional_variables(context)` |
| `on_pre_server_command(command, done_callback)` | `on_execute_command(command)` - return a `Promise` instead of invoking a callback |
| `on_pre_send_request_async(request_id, request)` | `on_pre_send_request_async(request, view)` |
| `on_server_response_async(method, response)` | `on_server_response_async(response)` |

All other instance methods (`on_settings_changed`, `on_workspace_configuration`,
`on_pre_send_notification_async`, `on_server_notification_async`, `on_open_uri_async`,
`on_session_buffer_changed_async`, `on_selection_modified_async`, `on_session_end_async`)
are available in `LspPlugin` with the same name and the same signature.

---

## Step-by-step migration

### 1. Change the base class

```python
# Before
from LSP.plugin import AbstractPlugin

class LspFoo(AbstractPlugin):
    ...
```

```python
# After
from LSP.plugin import LspPlugin

class LspFoo(LspPlugin):
    ...
```

`LspPlugin` also exposes `register()` and `unregister()` convenience classmethods, so you can call them directly on the class instead of importing the standalone functions:

```python
# Before
from LSP.plugin import register_plugin, unregister_plugin

def plugin_loaded() -> None:
    register_plugin(LspFoo)


def plugin_unloaded() -> None:
    unregister_plugin(LspFoo)
```

```python
# After
def plugin_loaded() -> None:
    LspFoo.register()


def plugin_unloaded() -> None:
    LspFoo.unregister()
```

---

### 2. Remove `name()` and `configuration()`

`LspPlugin` derives the session name from the top-level package name automatically (i.e. `__module__.split('.')[0]`). The settings file is expected at `Packages/<PackageName>/<PackageName>.sublime-settings`, also without any manual configuration.

Remove both overrides:

```python
# Before - remove these
@classmethod
def name(cls) -> str:
    return "foo"

@classmethod
def configuration(cls) -> tuple[sublime.Settings, str]:
    basename = "LSP-foo.sublime-settings"
    return sublime.load_settings(basename), f"Packages/LSP-foo/{basename}"
```

---

### 3. Replace `storage_path()` with `plugin_storage_path`

The storage path is now a class attribute set automatically to `$DATA/Package Storage/<PackageName>`. Replace calls to `cls.storage_path()` with `cls.plugin_storage_path`:

```python
# Before
server_dir = os.path.join(cls.storage_path(), cls.name(), "server")

# After
server_dir = cls.plugin_storage_path / "server"
```

---

### 4. Merge `needs_update_or_installation` and `install_or_update` into `install_async`

`install_async` is always called before the server starts and runs on a worker thread. Combine your install check and install logic there. To abort startup with a user-visible message, raise `PluginStartError` (this replaces returning a string from `can_start`):

```python
# Before
@classmethod
def needs_update_or_installation(cls) -> bool:
    return not server_binary().exists()

@classmethod
def install_or_update(cls) -> None:
    download_server(server_binary())

@classmethod
def can_start(cls, window, initiating_view, workspace_folders, configuration) -> str | None:
    if not server_binary().exists():
        return "Server binary missing"
    return None
```

```python
# After
from LSP.plugin import PluginStartError

@classmethod
def install_async(cls, context: PluginContext) -> None:
    if not server_binary().exists():
        download_server(server_binary())
    if not server_binary().exists():
        raise PluginStartError("Server binary missing after installation attempt")
```

---

### 5. Migrate `on_pre_start` overrides

`on_pre_start` was used to customise the command, working directory, and initialization options, often by mutating the passed-in `configuration`. `LspPlugin` provides dedicated override points for each concern:

```python
# Before
@classmethod
def on_pre_start(cls, window, initiating_view, workspace_folders, configuration) -> str | None:
    configuration.command = [str(server_binary()), "--stdio"]
    return str(workspace_folders[0].path) if workspace_folders else None
```

```python
# After
@classmethod
def command(cls, context: PluginContext) -> list[str]:
    return [str(cls.plugin_storage_path / "server"), "--stdio"]

@classmethod
def working_directory(cls, context: PluginContext) -> str | None:
    return context.workspace_folders[0].path if context.workspace_folders else None
```

For initialization options, override `initialization_options` instead of mutating `configuration.initialization_options` in `on_pre_start`:

```python
# After
@classmethod
def initialization_options(cls, context: PluginContext) -> dict[str, Any]:
    options = context.configuration.initialization_options.get()
    options["myCustomKey"] = "value"
    return options
```

---

### 6. Replace `on_post_start` with `__init__`

`on_post_start` ran after the subprocess started but before the `initialize` handshake. In `LspPlugin`, `__init__` is called after a successful `initialize` response, which is the more useful point to run post-start logic. The `context` argument gives you access to the same information that was previously passed to `on_post_start`:

```python
# Before
@classmethod
def on_post_start(cls, window, initiating_view, workspace_folders, configuration) -> None:
    log_start(window, configuration)
```

```python
# After
def __init__(self, weaksession, context: PluginContext) -> None:
    super().__init__(weaksession, context)
    log_start(context.window, context.configuration)
```

---

### 7. Update `is_applicable` and `additional_variables`

Both methods now receive a single `PluginContext` argument instead of individual parameters.
`context.view` and `context.configuration` replace the former `view` and `config` arguments:

```python
# Before
@classmethod
def is_applicable(cls, view: sublime.View, config: ClientConfig) -> bool:
    return super().is_applicable(view, config) and my_condition(view)

@classmethod
def additional_variables(cls) -> dict[str, str] | None:
    return {"server_version": SERVER_VERSION}
```

```python
# After
@classmethod
def is_applicable(cls, context: PluginContext) -> bool:
    return super().is_applicable(context) and my_condition(context.view)

@classmethod
def additional_variables(cls, context: PluginContext) -> dict[str, str] | None:
    return {"server_version": SERVER_VERSION}
```

---

### 8. Replace `on_pre_server_command` with `on_execute_command`

The callback-based approach is replaced by returning a `Promise`:

```python
# Before
def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
    if command["command"] == "foo/bar":
        handle_command(command)
        done_callback()
        return True
    return False
```

```python
# After
from LSP.plugin import Promise

def on_execute_command(self, command: ExecuteCommandParams) -> Promise[None] | None:
    if command["command"] == "foo/bar":
        return Promise.resolve(handle_command(command))
    return None
```

---

### 9. Update `on_pre_send_request_async` and `on_server_response_async`

Both methods have had their signatures simplified.

`on_pre_send_request_async` no longer receives the numeric request ID and the `view` argument is now passed explicitly:

```python
# Before
def on_pre_send_request_async(self, request_id: int, request: Request) -> None:
    log(f"[{request_id}] {request.method}")
```

```python
# After
def on_pre_send_request_async(self, request: ClientRequest, view: sublime.View | None) -> None:
    log(request['method'])
```

`on_server_response_async` no longer receives the method name separately:

```python
# Before
def on_server_response_async(self, method: str, response: Response) -> None:
    if method == 'textDocument/hover':
        process(response.result)
```

```python
# After
def on_server_response_async(self, response: ServerResponse) -> None:
    process(response.get('result'))
```

---

### 10. Use `@notification_handler` and `@request_handler` for custom messages

`LspPlugin` introduces decorators to handle non-standard server-to-client notifications and requests. These replace manual approach with method names transformed using logic from `method2attr`:

```python
# Before
def m__eslint_status(self, params: str) -> None:
    self.handle_status(notification.params)
```

```python
# After
from LSP.plugin import notification_handler

@notification_handler('eslint/status')
def on_eslint_status(self, params: str) -> None:
    self.handle_status(params)
```

```python
# Similarly for requests
from LSP.plugin import request_handler

@request_handler('eslint/openDoc')
def on_eslint_open_doc(self, params: TextDocumentIdentifier) -> Promise[bool]:
    ...
```

---

## Complete before/after example

```python
# Before - AbstractPlugin
from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import unregister_plugin


class LspFoo(AbstractPlugin):

    @classmethod
    def name(cls) -> str:
        return "foo"

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        return not (cls.storage_path() / "foo" / "server").exists()

    @classmethod
    def install_or_update(cls) -> None:
        download_server()

    @classmethod
    def on_pre_start(cls, window, initiating_view, workspace_folders, configuration) -> str | None:
        configuration.command = [str(cls.storage_path() / "foo" / "server"), "--stdio"]
        return None


def plugin_loaded() -> None:
    register_plugin(LspFoo)


def plugin_unloaded() -> None:
    unregister_plugin(LspFoo)
```

```python
# After - LspPlugin
from LSP.plugin import LspPlugin
from LSP.plugin import PluginContext
from LSP.plugin import PluginStartError


class LspFoo(LspPlugin):

    @classmethod
    def install_async(cls, context: PluginContext) -> None:
        if not (cls.plugin_storage_path / "server").exists():
            download_server()
        if not (cls.plugin_storage_path / "server").exists():
            raise PluginStartError("Failed to install foo language server")

    @classmethod
    def command(cls, context: PluginContext) -> list[str]:
        return [str(cls.plugin_storage_path / "server"), "--stdio"]


def plugin_loaded() -> None:
    LspFoo.register()


def plugin_unloaded() -> None:
    LspFoo.unregister()
```
