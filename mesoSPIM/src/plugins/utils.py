# mesospim/plugins/utils.py
import inspect
import sys
import types
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.manager import MESOSPIM_PLUGIN_MODULE_PREFIX
from mesoSPIM.src.plugins.ImageWriterApi import Writer

def list_plugin_classes_of_type(mod: types.ModuleType, type: Protocol):
    """Return all valid subclasses of 'type' in a module."""
    class_list = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if obj.__module__ != mod.__name__:
            continue
        try:
            if issubclass(obj, type):
                class_list.append(obj)
        except TypeError:
            # Protocols or old-style ABCs may raise
            if isinstance(obj, type):
                class_list.append(obj)
    return class_list

def list_all_registered_mesospim_plugin_modules(prefix=MESOSPIM_PLUGIN_MODULE_PREFIX) -> List[types.ModuleType]:
    '''Return a list of all registered mesospim plugin modules'''
    return [value for key, value in sys.modules.items() if key.startswith(prefix)]


def list_writer_plugins():
    '''Return a list of all registered writer plugins'''
    classes = []
    modules = list_all_registered_mesospim_plugin_modules(prefix=MESOSPIM_PLUGIN_MODULE_PREFIX)
    for mod in modules:
        current_classes = list_plugin_classes_of_type(mod, type=Writer)
        classes += current_classes
    return classes

def get_writer_plugins():
    '''Return a list of dict of all registered writer plugins with names, file_extensions, capabilities and callable class'''
    writers = []
    writer_classes = list_writer_plugins()
    for writer in writer_classes:
        current_writer = {
            'name': writer.name(),
            'file_extensions': writer.file_extensions(),
            'capabilities': writer.capabilities(),
            'file_names': writer.file_names(),
            'writer_class': writer
        }
        writers.append(current_writer)
    return writers

def get_writer_for_file_extension(file_extension: str):
    '''Return a writer class for the given file extension'''
    for writer in get_writer_plugins():
        file_ext = file_extension[1:] if file_extension.startswith('.') else file_extension
        if file_ext in writer['file_extensions']:
            return writer

def get_writer_name_for_file_extension(file_extension: str):
    writer = get_writer_for_file_extension(file_extension)
    return writer['name']

def get_writer_from_name(name: str):
    for writer in get_writer_plugins():
        if name == writer['name']:
            return writer

def get_writer_class_from_name(name: str):
    for writer in get_writer_plugins():
        if name == writer['name']:
            return writer['writer_class']