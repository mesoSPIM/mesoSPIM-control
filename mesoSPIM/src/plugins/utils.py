# mesospim/plugins/utils.py
import inspect

def find_writer_classes(mod, writer_base):
    """Return all valid Writer subclasses in a module."""
    writers = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if obj.__module__ != mod.__name__:
            continue
        try:
            if issubclass(obj, writer_base):
                writers.append(obj)
        except TypeError:
            # Protocols or old-style ABCs may raise
            if isinstance(obj, writer_base):
                writers.append(obj)
    return writers
