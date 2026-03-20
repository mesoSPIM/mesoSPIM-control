# mesospim/plugins/utils.py
import inspect
import sys
import subprocess
import importlib.metadata
import logging
logger = logging.getLogger(__name__)
import numpy as np
import types
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.manager import MESOSPIM_PLUGIN_MODULE_PREFIX
from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter
from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor


def count_domain_to_uint16(image: np.ndarray) -> np.ndarray:
    """Convert count-domain image data to uint16 with clipping."""
    image = np.asarray(image)
    image = np.nan_to_num(image, nan=0.0, posinf=65535.0, neginf=0.0)
    image = np.clip(np.rint(image), 0, 65535)
    return image.astype(np.uint16, copy=False)


def normalized_to_uint16(image: np.ndarray) -> np.ndarray:
    """Convert normalized float data in the range [0, 1] to uint16."""
    image = np.asarray(image)
    image = np.nan_to_num(image, nan=0.0, posinf=1.0, neginf=0.0)
    image = np.clip(image, 0.0, 1.0)
    image = np.rint(image * 65535.0)
    return image.astype(np.uint16, copy=False)

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
    '''Return the name attribute of the writer for the given a compatible file extension.

    Returns ``None`` if no registered writer supports the given extension.
    '''
    writer = get_image_writer_for_file_extension(file_extension)
    return writer['name'] if writer is not None else None

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
#                                      ImageProcessor Plugin-specific utilities                                      #
# ------------------------------------------------------------------------------------------------------------------- #

def list_image_processor_plugins():
    '''Return a list of all registered image processor plugins'''
    classes = []
    modules = list_all_registered_mesospim_plugin_modules(prefix=MESOSPIM_PLUGIN_MODULE_PREFIX)
    for mod in modules:
        current_classes = list_plugin_classes_of_type(mod, type=ImageProcessor)
        classes += current_classes
    return classes

def get_image_processor_plugins():
    '''Return a list of dict of all registered processor plugins with names, descriptions, capabilities and callable class'''
    processors = []
    processor_classes = list_image_processor_plugins()
    for processor in processor_classes:
        current_processor = {
            'name': processor.name(),
            'description': processor.description(),
            'capabilities': processor.capabilities(),
            'processor_class': processor
        }
        processors.append(current_processor)
    return processors

def get_image_processor_from_name(name: str):
    '''
    Return the processor dict given its name attribute
    Structure of processor is determined by function get_processor_plugins()
    '''
    for processor in get_image_processor_plugins():
        if name == processor['name']:
            return processor

def get_image_processor_class_from_name(name: str):
    '''
    Return the processor class given its name attribute
    This processor class is used directly for processing images
    processor = processor_class()
    processed_image = processor.process_frame(image)
    '''
    for processor in get_image_processor_plugins():
        if name == processor['name']:
            return processor['processor_class']

def create_processor(name: str, params: dict = None):
    '''
    Factory function to create a processor instance by name.
    
    Args:
        name: Processor name (from ImageProcessor.name())
        params: Optional configuration parameters
        
    Returns:
        Instance of the requested processor
    '''
    processor_class = get_image_processor_class_from_name(name)
    if processor_class is None:
        raise ValueError(f"Unknown processor: {name}")
    
    processor = processor_class()
    if params:
        processor.configure(params)
    return processor


# ------------------------------------------------------------------------------------------------------------------- #
#                                      Helpers to ensure functioning plugins                                          #
# ------------------------------------------------------------------------------------------------------------------- #

# def install_and_import(package_name, version=None):
#     """
#     Attempts to import a package. If not found, attempts to install
#     a specific version (if specified) or the latest version.
#     """
#
#     # Format the installation target
#     install_target = f"{package_name}=={version}" if version else package_name
#
#     try:
#         __import__(package_name)
#         # print(f"'{package_name}' already imported (version check might be needed).")
#     except ImportError:
#         print(f"'{package_name}' not found. Attempting to install {install_target}...")
#         try:
#             # Use the same Python executable to ensure pip installs into the correct environment
#             subprocess.check_call([sys.executable, "-m", "pip", "install", install_target])
#             print(f"'{install_target}' installed successfully.")
#             __import__(package_name)  # Import the newly installed package
#         except subprocess.CalledProcessError as e:
#             print(f"Failed to install '{install_target}'. Error: {e}")
#             sys.exit(1)
#         except Exception as e:
#             print(f"An unexpected error occurred during installation: {e}")
#             sys.exit(1)


def install_and_import(package_name, version=None, index_url=None, force_reinstall=False):
    """
    Import a package if available; otherwise install it.
    If index_url is provided, pip installs from that index.
    """

    install_target = f"{package_name}=={version}" if version else package_name

    need_install = force_reinstall
    if not need_install:
        try:
            __import__(package_name)
            print(f"'{package_name}' already importable.")
            return
        except ImportError:
            need_install = True

    if need_install:
        print(f"Installing {install_target} ...")
        cmd = [sys.executable, "-m", "pip", "install"]
        if force_reinstall:
            cmd += ["--force-reinstall"]
        if index_url:
            cmd += ["--index-url", index_url]
        cmd += [install_target]

        subprocess.check_call(cmd)
        __import__(package_name)
        print(f"Installed '{install_target}' successfully.")
