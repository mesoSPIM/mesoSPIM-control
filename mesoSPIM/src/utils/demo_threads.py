import logging 
logger = logging.getLogger(__name__)
import time

from PyQt5 import QtWidgets, QtCore, QtGui

class mesoSPIM_DemoThread(QtCore.QObject):
    def __init__(self):
        super().__init__()

        logger.info('Demo Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot()
    def report_thread_id(self):
        logger.info('Demo Thread ID while running: '+str(int(QtCore.QThread.currentThreadId())))


