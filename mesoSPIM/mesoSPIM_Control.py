'''
mesoSPIM_control.py
========================================
The core module of the mesoSPIM software
'''

__author__ = "Fabian Voigt"
__license__ = "GPL v3"
__maintainer__ = "Nikita Vladimirov"


''' Configuring the logging module before doing anything else'''
import time
import logging
import argparse
import glob
timestr = time.strftime("%Y%m%d-%H%M%S")
logging_filename = timestr + '.log'
logging.basicConfig(filename='log/'+logging_filename, level=logging.INFO, format='%(asctime)-8s:%(levelname)s:%(threadName)s:%(thread)d:%(module)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
logger.info('mesoSPIM-control started')

import os
import sys
import importlib.util

from PyQt5 import QtWidgets

from src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

logger.info('Modules loaded')

def load_config_UI(current_path):
    '''
    Bring up a GUI that allows the user to select a microscope configuration to import
    '''
    cfg_app = QtWidgets.QApplication(sys.argv)
    current_path = os.path.abspath('./config')
    global_config_path = ''
    global_config_path , _ = QtWidgets.QFileDialog.getOpenFileName(None,
                                                                   'Open microscope configuration file',current_path)

    if global_config_path != '':
        config = load_config_from_file(global_config_path)
        return config
    else:
        ''' Application shutdown '''
        warning = QtWidgets.QMessageBox.warning(None,'Shutdown warning',
                'No configuration file selected - shutting down!',
                QtWidgets.QMessageBox.Ok)
        sys.exit()

    sys.exit(cfg_app.exec_())

def load_config_from_file(path_to_config):
    '''
    Load a microscope configuration from a file using importlib
    '''
    spec = importlib.util.spec_from_file_location('module.name', path_to_config)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    logger.info(f'Configuration file loaded: {path_to_config}')
    return config

def stage_referencing_check(cfg):
    '''
    Due to problems with some PI stages loosing reference information
    after restarting the mesoSPIM software, some stage configurations require
    a reference movement to be carried out before starting the rest of the software.

    As reference movements can damage the instrument, this function warns users
    about this problem by message boxes and asks them to reach a safe state.
    '''
    if cfg.stage_parameters['stage_type'] == 'PI_rotzf_and_Galil_xy' or cfg.stage_parameters['stage_type'] == 'PI_rotz_and_Galil_xyf':
        warning = QtWidgets.QMessageBox.warning(None,'Sample z reference movement necessary!',
                'Please move the XYZ stage to position where a reference z movement (to the midpoint of the movement range) is safe!',
                QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok)
        if warning == QtWidgets.QMessageBox.Cancel:
            shutdown_message = QtWidgets.QMessageBox.warning(None,'Shutdown warning',
                    'No reference movement - shutting down!',
                    QtWidgets.QMessageBox.Ok)
            sys.exit()
        else:
            return True
    else:
        return True

def get_parser():
    """
    Parse command-line input arguments
    :return: The argparse parser object
    """
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-C', '--console', action='store_true',  # store_true makes it False by default
                        help='Start a ipython console')
    parser.add_argument('-D', '--demo', action='store_true',
                        help='Start in demo mode')
    return parser
  
def dark_mode_check(cfg, app):
    if (hasattr(cfg, 'dark_mode') and cfg.dark_mode) or (hasattr(cfg, 'ui_options') and cfg.ui_options['dark_mode']):
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))


def main(embed_console=False, demo_mode=False):
    """
    Load a configuration file according to the following rules:
    1. If the user asked for demo mode, load the `demo_config.py` file
    2. Else, ff the user did not ask for demo mode:
     - if there is only one non-demo config file, load that.
     - if there are multiple config files, bring up the UI loader.
    """
    print('Starting control software')
    logging.info('mesoSPIM Program started.')
    current_path = os.path.abspath('./config')

    demo_fname = current_path + "/demo_config.py"
    if not os.path.exists(demo_fname):
        raise ValueError(f"Demo file not found: {demo_fname}")

    if demo_mode:
            cfg = load_config_from_file(demo_fname)
            print(f"Loaded config from demo file: {demo_fname}")
    else:
        all_configs = glob.glob(os.path.join(current_path, '*.py')) # All possible config files
        all_configs_no_demo = list(filter(lambda f: str.find(f, 'demo_') < 0, all_configs))
        if len(all_configs_no_demo) == 0:
            cfg = load_config_from_file(demo_fname)
            print(f"Loaded config from demo file: {demo_fname}")
        elif len(all_configs_no_demo) == 1:
            config_fname = os.path.join(current_path, all_configs_no_demo[0])
            cfg = load_config_from_file()
            print(f"Loaded config from {config_fname}")
        else:
            cfg = load_config_UI(current_path)

    app = QtWidgets.QApplication(sys.argv)
    dark_mode_check(cfg, app)
    stage_referencing_check(cfg)
    ex = mesoSPIM_MainWindow(cfg)
    ex.show()
    ex.display_icons()

    if embed_console:
        from traitlets.config import Config
        cfg = Config()
        cfg.InteractiveShellApp.gui = 'qt5'
        import IPython
        IPython.start_ipython(config=cfg, argv=[], user_ns=dict(mSpim=ex, app=app))
    else:
        sys.exit(app.exec_())


def run():
    args = get_parser().parse_args()
    main(embed_console=args.console,demo_mode=args.demo)


if __name__ == '__main__':
    run()
