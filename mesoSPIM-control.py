'''
mesoSPIM Control software

Author: Fabian Voigt
'''

import sys

from PyQt5 import QtWidgets

from src.window import Window
from config.config import my_config as cfg

def main():
    app = QtWidgets.QApplication(sys.argv)
    ex = Window(cfg)
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
