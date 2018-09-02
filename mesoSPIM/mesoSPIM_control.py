'''
mesoSPIM_control.py
========================================
The core module of the mesoSPIM software
'''

import os
import sys
import importlib.util

from PyQt5 import QtWidgets

from src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

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
        return config
    else:
        ''' Application shutdown '''
        warning = QtWidgets.QMessageBox.warning(None,'Shutdown warning',
                'No configuration file selected - shutting down!',
                QtWidgets.QMessageBox.Ok)
        sys.exit()

def main():
    """
    Main function
    """
    cfg = load_config()
    app = QtWidgets.QApplication(sys.argv)
    ex = mesoSPIM_MainWindow(cfg)
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
