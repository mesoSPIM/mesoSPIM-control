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
logging.basicConfig(filename='log/'+logging_filename, level=logging.INFO, format='%(asctime)-8s:%(levelname)s:%(threadName)s:%(thread)d:%(module)s:%(message)s')
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

def main():
    """
    Main function
    """
    logging.info('mesoSPIM Program started.')
    cfg = load_config()
    app = QtWidgets.QApplication(sys.argv)
    ex = mesoSPIM_MainWindow(cfg)
    ex.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
