from threading import Timer


def debounce(seconds):
    """ Decorator that will debounce a function call for the given amount of seconds. """
    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                fn(*args, **kwargs)
            try:
                debounced.t.cancel()  # type: ignore
            except(AttributeError):
                pass
            debounced.t = Timer(seconds, call_it)  # type: ignore
            debounced.t.start()  # type: ignore
        return debounced
    return decorator
