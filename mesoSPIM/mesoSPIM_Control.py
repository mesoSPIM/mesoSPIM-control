'''
mesoSPIM_control.py
========================================
The core module of the mesoSPIM software
'''

''' Configuring the logging module before doing anything else'''
import time
import logging
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

def load_config():
    '''
    Import microscope configuration at startup
    '''

    ''' This needs an placeholder QApplication to work '''
    cfg_app = QtWidgets.QApplication(sys.argv)
    current_path = os.path.abspath('./config')

    global_config_path = ''
    global_config_path , _ = QtWidgets.QFileDialog.getOpenFileName(None,\
    'Open microscope configuration file',current_path)

    if global_config_path != '':
        ''' Using importlib to load the config file '''
        spec = importlib.util.spec_from_file_location('module.name', global_config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        logger.info(f'Configuration file loaded: {global_config_path}')
        return config
    else:
        ''' Application shutdown '''
        warning = QtWidgets.QMessageBox.warning(None,'Shutdown warning',
                'No configuration file selected - shutting down!',
                QtWidgets.QMessageBox.Ok)
        sys.exit()

    sys.exit(cfg_app.exec_())

def stage_referencing_check(cfg):
    '''
    Due to problems with some PI stages loosing reference information
    after restarting the mesoSPIM software, some stage configurations require
    a reference movement to be carried out before starting the rest of the softwareself.

    As reference movements can damage the instrument, this function warns users
    about this problem by message boxes and asks them to reach a safe state.
    '''
    if cfg.stage_parameters['stage_type'] == 'PI_rotz_and_Galil_xyf':
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

def main():
    """
    Main function
    """
    logging.info('mesoSPIM Program started.')
    cfg = load_config()
    app = QtWidgets.QApplication(sys.argv)
    stage_referencing_check(cfg)
    ex = mesoSPIM_MainWindow(cfg)
    ex.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
