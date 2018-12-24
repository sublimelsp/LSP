from threading import Timer


def debounce(seconds):
    """ Decorator that will debounce a function call for the given amount of seconds. """
    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                fn(*args, **kwargs)
            try:
                debounced.t.cancel()
            except(AttributeError):
                pass
            debounced.t = Timer(seconds, call_it)
            debounced.t.start()
        return debounced
    return decorator
