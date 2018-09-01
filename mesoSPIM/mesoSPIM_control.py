'''
main.py
====================================
The core module of my example project
'''

import sys

from PyQt5 import QtWidgets

from src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

def main():
    """
        Main function
        Parameters
        ---------
        name
            A string to assign to the `name` instance attribute.
    """
    app = QtWidgets.QApplication(sys.argv)
    ex = mesoSPIM_MainWindow()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
