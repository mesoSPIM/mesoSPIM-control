''' Worker object in a separate file '''

import time
import copy

from PyQt5 import QtWidgets, QtCore

class WorkerObject(QtCore.QObject):
    '''
    Worker object which has a few time-intensive methods, can signal
    its status and is able to listen to stop events.
    '''
    started = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    status = QtCore.pyqtSignal(int)

    def __init__(self, parent):
        super().__init__()

        ''' Here, I'm referencing the parent '''
        # print(id(parent))
        self.parent = parent
        # print(id(self.parent))
        ''' The IDs are the same'''

        ''' Here, I can connect signals from the parent in the child

        This is a form of callbacks
        '''
        self.parent.sig_start.connect(self.start)

        self.cfg = copy.deepcopy(self.parent.cfg)

        print(id(self.parent.cfg))
        print(id(self.cfg))

    @QtCore.pyqtSlot()
    def start(self):
        '''
        Execute some time intensive (sleepy) operation.
        '''
        self.started.emit()
        for i in range(0,101):
            time.sleep(0.02)
            QtWidgets.QApplication.processEvents()
            self.status.emit(i)
        self.finished.emit()

        self.parent.print_sth('hi from your thread')

class AnotherWorkerObject(WorkerObject):
    ''' Another, simpler worker object '''

    def __init__(self, parent):
        super().__init__(parent)

    @QtCore.pyqtSlot()
    def start(self):
        for i in range(0,101):
            time.sleep(0.02)
            if i % 10 == 0:
                print(i)
