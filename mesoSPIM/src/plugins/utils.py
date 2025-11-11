# mesospim/plugins/utils.py
import inspect
import sys
import subprocess
import logging
logger = logging.getLogger(__name__)
import types
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.manager import MESOSPIM_PLUGIN_MODULE_PREFIX
from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter

# ------------------------------------------------------------------------------------------------------------------- #
#                                        General Plugin-discovery utilities                                           #
# ------------------------------------------------------------------------------------------------------------------- #

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

# ------------------------------------------------------------------------------------------------------------------- #
#                                      ImageWriter Plugin-specific utilities                                          #
# ------------------------------------------------------------------------------------------------------------------- #

def list_image_writer_plugins():
    '''Return a list of all registered writer plugins'''
    classes = []
    modules = list_all_registered_mesospim_plugin_modules(prefix=MESOSPIM_PLUGIN_MODULE_PREFIX)
    for mod in modules:
        current_classes = list_plugin_classes_of_type(mod, type=ImageWriter)
        classes += current_classes
    return classes

def get_image_writer_plugins():
    '''Return a list of dict of all registered writer plugins with names, file_extensions, capabilities and callable class'''
    writers = []
    writer_classes = list_image_writer_plugins()
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

def get_image_writer_for_file_extension(file_extension: str):
    '''Return a writer class for the given file extension'''
    for writer in get_image_writer_plugins():
        file_ext = file_extension[1:] if file_extension.startswith('.') else file_extension
        if file_ext in writer['file_extensions']:
            return writer

def get_image_writer_name_for_file_extension(file_extension: str):
    '''Return the name attribute of the writer for the given a compatible file extension'''
    writer = get_image_writer_for_file_extension(file_extension)
    return writer['name']

def get_image_writer_from_name(name: str):
    '''
    Return the writer dict given its name attribute
    Structure of writer is determined by function get_writer_plugins()
    '''
    for writer in get_image_writer_plugins():
        if name == writer['name']:
            return writer

def get_image_writer_class_from_name(name: str):
    '''
    Return the writer class given its name attribute
    This writer class is used directly for writing data
    writer = writer_class()
    writer.open(WriteRequest)
    writer.write_frame(image)
    '''
    for writer in get_image_writer_plugins():
        if name == writer['name']:
            return writer['writer_class']


# ------------------------------------------------------------------------------------------------------------------- #
#                                      Helpers to ensure functioning plugins                                          #
# ------------------------------------------------------------------------------------------------------------------- #

def install_and_import(package_name, version=None):
    """
    Attempts to import a package. If not found, attempts to install
    a specific version (if specified) or the latest version.
    """

    # Format the installation target
    install_target = f"{package_name}=={version}" if version else package_name

    try:
        __import__(package_name)
        # print(f"'{package_name}' already imported (version check might be needed).")
    except ImportError:
        print(f"'{package_name}' not found. Attempting to install {install_target}...")
        try:
            # Use the same Python executable to ensure pip installs into the correct environment
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_target])
            print(f"'{install_target}' installed successfully.")
            __import__(package_name)  # Import the newly installed package
        except subprocess.CalledProcessError as e:
            print(f"Failed to install '{install_target}'. Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred during installation: {e}")
            sys.exit(1)

