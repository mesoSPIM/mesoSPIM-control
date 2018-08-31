'''
main.py
====================================
The core module of my example project
'''

import sys

from PyQt5 import QtWidgets

from .src.window import Window
from .config.config import my_config as cfg

def main():
    """
        Main function
        Parameters
        ---------
        name
            A string to assign to the `name` instance attribute.
    """
    app = QtWidgets.QApplication(sys.argv)
    ex = Window(cfg)
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
