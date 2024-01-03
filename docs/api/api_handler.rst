API Handler
===========

ApiWrapperInterface
-------------------

.. autoclass:: LSP.api.ApiWrapperInterface

API Decorators
--------------

Decorators can be used as an alternative to attaching listeners to the :class:`LSP.api.ApiWrapperInterface` instance obtained through :meth:`LSP.api.GenericClientHandler.on_ready()`.

To use, attach the decorator to a function and call it with the name of the notification or the request that you want to handle. It can also be called with a list of names, if you want to use the same handler to handle multiple requests.

Example usage:

.. code:: py

    @notification_handler('eslint/status')
    def handle_status(self, params: Any) -> None:
        print(status)

    @request_handler('eslint/openDoc')
    def handle_open_doc(self, params: Any, respond: Callable[[Any], None]) -> None:
        webbrowser.open(params['url'])
        respond({})

.. autoclass:: LSP.api.request_handler
.. autoclass:: LSP.api.notification_handler
