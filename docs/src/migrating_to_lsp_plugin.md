# Migrating from AbstractPlugin to LspPlugin

`LspPlugin` is the modern base class for LSP helper packages. It replaces `AbstractPlugin` with a cleaner, context-based API that reduces boilerplate and consolidates the server lifecycle into fewer override points.

!!! note
    `AbstractPlugin` is still supported. You only need to migrate when you are ready to adopt the new API.

---

## Overview of changes

| AbstractPlugin | LspPlugin |
|---|---|
| `name()` | Removed - derived automatically from the package name and exposed as a `name` property |
| `configuration()` | Removed - settings file located automatically |
| `storage_path()` | `plugin_storage_path` class attribute (derived automatically) |
| `needs_update_or_installation()` + `install_or_update()` + `can_start()` + `on_pre_start()` + `additional_variables()` | `on_before_start_async(context)` |
| `on_post_start(window, view, folders, config)` | `on_start_async(context)` |
| `on_settings_changed(settings: DottedDict)` | `on_after_initialize_async()` for one-time setup; `on_pre_send_response_async(response)` for dynamic `workspace/configuration` |
| `is_applicable(view, config)` | `is_applicable(context: ContextIsApplicable)` |
| `on_workspace_configuration(params, configuration)` | `on_pre_send_response_async(response)` — intercept `workspace/configuration` response |
| `on_pre_server_command(command, done_callback)` | `@command_handler` decorator |
| `on_pre_send_request_async(request_id, request)` | `on_pre_send_request_async(request, view)` |
| `on_server_response_async(method, response)` | `on_server_response_async(response)` |
| `register_plugin(MyPlugin)` / `unregister_plugin(MyPlugin)` | `MyPlugin.register()` / `MyPlugin.unregister()` - no standalone import needed |
| *(not present)* | `on_before_start_async(context)` — classmethod, replaces several AbstractPlugin hooks |
| *(not present)* | `on_start_async(context)` — replaces `on_before_initialize` |
| *(not present)* | `on_after_initialize_async()` |
| *(not present)* | `on_pre_send_response_async(response)` |

All other instance methods (`on_pre_send_notification_async`, `on_server_notification_async`, `on_open_uri_async`, `on_session_buffer_changed_async`, `on_selection_modified_async`, `on_session_end_async`) are available in `LspPlugin` with the same name and the same signature.

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

`LspPlugin` provides `register()` and `unregister()` classmethods, so `register_plugin` and `unregister_plugin` **no longer need to be imported or called directly**. Replace them with calls on your plugin class:

```python
# Before
from LSP.plugin import AbstractPlugin
from LSP.plugin import register_plugin
from LSP.plugin import unregister_plugin

class LspFoo(AbstractPlugin):
    ...

def plugin_loaded() -> None:
    register_plugin(LspFoo)

def plugin_unloaded() -> None:
    unregister_plugin(LspFoo)
```

```python
# After
from LSP.plugin import LspPlugin

class LspFoo(LspPlugin):
    ...

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

### 4. Consolidate server setup into `on_before_start_async`

`on_before_start_async` is the single hook called just before the server process starts. It runs on a worker thread and replaces `needs_update_or_installation`, `install_or_update`, `can_start`, `on_pre_start`, and `additional_variables` from `AbstractPlugin`.

Mutate `context.configuration`, `context.variables`, and `context.working_directory` to influence how the server is launched. To abort startup with a user-visible message, raise `PluginStartError` with a chosen message:

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

@classmethod
def on_pre_start(cls, window, initiating_view, workspace_folders, configuration) -> str | None:
    configuration.command = [str(server_binary()), "--stdio"]
    return str(workspace_folders[0].path) if workspace_folders else None

@classmethod
def additional_variables(cls) -> dict[str, str] | None:
    return {"server_version": SERVER_VERSION}
```

```python
# After
from LSP.plugin import ContextOnBeforeStart
from LSP.plugin import PluginStartError

@classmethod
def on_before_start_async(cls, context: ContextOnBeforeStart) -> None:
    if not server_binary().exists():
        download_server(server_binary())
    if not server_binary().exists():
        raise PluginStartError("Server binary missing after installation attempt")
    context.configuration.command = [str(server_binary()), "--stdio"]
    context.working_directory = context.workspace_folders[0].path if context.workspace_folders else None
    context.variables["server_version"] = SERVER_VERSION
```

---

### 5. Replace `on_post_start` with `on_start_async`

`on_post_start` ran after the subprocess started but before the `initialize` handshake. `on_start_async` covers the same window — it is called after the transport is established and before the `initialize` request is sent. Use `context.transport` to send any pre-initialization messages your server requires:

```python
# Before
@classmethod
def on_post_start(cls, window, initiating_view, workspace_folders, configuration) -> None:
    log_start(window, configuration)
```

```python
# After
from LSP.plugin import ContextOnStart

def on_start_async(self, context: ContextOnStart) -> None:
    if session := self.weaksession():
        log_start(session.window, session.config)
```

---

### 6. Remove `on_settings_changed`

`LspPlugin` does not provide an `on_settings_changed` override point. The method has been removed because it was only called once right after sending the `initialize` request. Depending on what you were doing in it, one of these replacements applies:

**One-time setup at startup** — move the logic to `on_after_initialize_async`, which is called after a successful `initialize` response:

```python
# After — one-time setup
def on_after_initialize_async(self) -> None:
    if session := self.weaksession():
        session.config.settings.set('foo', 'bar')
```

**Adjusting `workspace/configuration` responses dynamically** — override `on_pre_send_response_async` and filter on the method name. The `response['result']` can be mutated before the value is sent back to the server:

```python
# After — dynamic configuration
def on_pre_send_response_async(self, response: ClientResponse) -> None:
    if response['method'] == 'workspace/configuration':
        for item in response['result']:
            item['myKey'] = 'myValue'
```

---

### 7. Replace `on_workspace_configuration`

`on_workspace_configuration` has been removed from `LspPlugin`. In `AbstractPlugin` it was called each time the server sent a `workspace/configuration` request, allowing the plugin to modify the configuration value for a given section before it was returned to the server.

The same result can be achieved in `LspPlugin` by overriding `on_pre_send_response_async` and intercepting the `workspace/configuration` response. The `response['result']` list contains one entry per requested configuration item and can be mutated before it is sent back to the server:

```python
# Before
def on_workspace_configuration(self, params: ConfigurationItem, configuration: Any) -> Any:
    if params.get('section') == 'myServer':
        configuration['myKey'] = 'myValue'
    return configuration
```

```python
# After
def on_pre_send_response_async(self, response: ClientResponse) -> None:
    if response['method'] == 'workspace/configuration':
        for item in response['result']:
            item['myKey'] = 'myValue'
```

---

### 8. Update `is_applicable`

`is_applicable` now receives a `ContextIsApplicable` argument instead of separate `view` and `config` parameters:

```python
# Before
@classmethod
def is_applicable(cls, view: sublime.View, config: ClientConfig) -> bool:
    return super().is_applicable(view, config) and my_condition(view)
```

```python
# After
from LSP.plugin import ContextIsApplicable

@classmethod
def is_applicable(cls, context: ContextIsApplicable) -> bool:
    return super().is_applicable(context) and my_condition(context.view)
```

---

### 9. Replace `on_pre_server_command` with `@command_handler`

The callback-based `on_pre_server_command` is replaced by the `@command_handler` decorator. Each decorated method handles one specific command by name and receives the command's `arguments` list (or `None`):

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
from LSP.plugin import command_handler
from LSP.plugin import LSPAny

@command_handler('foo/bar')
def on_foo_bar(self, arguments: list[LSPAny] | None) -> Promise[None]:
    return Promise.resolve(handle_command(arguments))
```

---

### 10. Update `on_pre_send_request_async` and `on_server_response_async`

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

### 11. Use `@notification_handler` and `@request_handler` for custom messages

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
