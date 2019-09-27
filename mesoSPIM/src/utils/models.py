from PyQt5 import QtWidgets, QtGui, QtCore, QtDesigner

from .acquisitions import Acquisition, AcquisitionList

from ..mesoSPIM_State import mesoSPIM_StateSingleton

import copy
import pickle

class AcquisitionModel(QtCore.QAbstractTableModel):
    '''
    Model class containing a AcquisitionList

    The headers are derived from the keys of the first acquisition
    dictionary.

    TODO: Typecheck in __init__ for AcquisitionList as table
    '''
    def __init__(self, table = None, parent = None):
        super().__init__(parent)
        
        if table == None:
            self._table = AcquisitionList()
        else:
            self._table = table

        ''' Get the headers as the capitalized keys from the first acquisition '''
        self._headers = self._table.get_capitalized_keylist()

        self.state = mesoSPIM_StateSingleton()

        self.dataChanged.connect(self.updatePlanes)

    def rowCount(self, parent = QtCore.QModelIndex()):
        ''' Tells the view how many items this model contains '''
        return len(self._table)

    def columnCount(self, parent = QtCore.QModelIndex()):
        return len(self._table[0])

    def flags(self, index):
        ''' Return Editability for arbitrary elements
        Drag and drop flags are also set here
        '''

        # What does | actually mean?
        '''
        Attention: Here, it is hardcoded that column 5 (# Planes is not editable) If acquistions.py changes, this will 
        require a change here as well
        '''
        if index.column() == self._headers.index('Planes'):
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled
        else: 
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled

    def headerData(self, section, orientation, role):
        '''
        What to display in the table headers

        Orientation: Row part or column part
        Section: Which index

        '''
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._headers[section]
            if orientation == QtCore.Qt.Vertical:
                return 'Stack ' + str(section)

    def data(self, index, role):
        ''' Data allows to fetch one item'''

        row = index.row()
        column = index.column()

        if role == QtCore.Qt.EditRole:
            ''' What is shown when the editing (double click)
            is selected: A line edit is transiently created
            '''
            return self._table[row](column)

        if role == QtCore.Qt.DisplayRole:
            ''' What is displayed '''
            return self._table[row](column)

        if role == QtCore.Qt.ToolTipRole:
            ''' Tooltip: Text that is display when mouse hovers '''
            return "Table entry: " + str(self._table[row](column))

    def setData(self, index, value, role = QtCore.Qt.EditRole):
        ''' Method used to write data

        Here, a single table entry is set.

        Has to return True when the change was successful
        '''
        if role == QtCore.Qt.EditRole:
            _ = self.columnCount()
            row = index.row()
            column = index.column()

            try:
                '''
                self._table[row] is the Acquisition object
                out of which a column entry needs to be accessed
                - this can only happen via the key
                - if d is the indexed dict, then
                - d[d.keys()[column]] = new_value allow that
                '''
                self._table[row][self._table[row].keys()[column]] = value
                self.dataChanged.emit(index, index)
                #print('Data changed')
                return True
            except:
                #print('Data NOT changed')
                return False

    def setDataFromState(self, row, state_parameter):
        column = self._table.get_keylist().index(state_parameter)

        if state_parameter in ('x_pos','y_pos','z_pos','f_pos'):
            new_value = round(self.state['position'][state_parameter],2)
        elif state_parameter == 'rot':
            new_value = round(self.state['position']['theta_pos'],2)
        else:
            new_value = self.state[state_parameter]

        index = self.createIndex(row, column)

        self.setData(index, new_value)        

    def updatePlanes(self, index, index2):
        ''' Checks if z_planes need to be updated and updates them'''
        column = index.column()

        keylist = self._table.get_keylist()

        z_start_column = keylist.index('z_start')
        z_end_column = keylist.index('z_end')
        z_step_column = keylist.index('z_step')

        if column in (z_start_column ,z_end_column, z_step_column):
            row = index.row()
            planes = self._table[row].get_image_count()
            planes_column = keylist.index('planes')

            index = self.createIndex(row, planes_column)
            self.setData(index, planes)
        
        

    def insertRows(self, position, rows, parent = QtCore.QModelIndex()):
        ''' Method to add entries to the model

        Rows: how many rows are inserted at once.

        The views expect a zero-based index

        self.beginInsertRows(index, first, last) to send signals
        '''
        self.beginInsertRows(parent, position, position + rows - 1)

        for i in range(rows):
            # defaultValues = ['Default' for i in range(self.columnCount(parent))]
            # defaultValues = ['Default',1,'One',50,56]
            self._table.insert(position, Acquisition())

        ''' Sending the required signal '''
        self.endInsertRows()

        return True

    def removeRows(self, position, rows, parent = QtCore.QModelIndex()):
        self.beginRemoveRows(parent, position, position + rows - 1)

        for i in range(rows):
            del self._table[position]

        self.endRemoveRows()
        return True

    def copyRow(self, row):
        ''' Copies a row '''
        old_row = copy.deepcopy(self._table[row])
        self.insertRow(row)
        self._table[row] = old_row
        self.send_data_changed()

    # def supportedDropActions(self):
    #     pass
    #     return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction

    def mimeData(self, indices):
        '''
        Here, the model needs to provide a serialization of the entries
        in a QMimeData object
        '''
        #print('MimeData called')
        mimeData = super().mimeData(indices)

        # print(indices[0].row())
        #
        # mimeData = QtCore.QMimeData()
        mimeData.setText(str(self._table[indices[0].row()](0)))
        return mimeData

    def dropMimeData(self, data, action, row, col, parent):
        '''
        Here, the model needs to deserialize the entries
        in a QMimeData object

        Always move the entire row, and don't allow column "shifting"
        '''
        #print('MimeData dropped')
        if action == QtCore.Qt.MoveAction:
            pass
            #print('Row: ', row)
            #print('Col: ', col)
            #print('Data:', data.text())
            #print('HTML:', data.html())
            # print()
            # self.insertRow(row)
            # print('Data methods: ', dir(data))
            # return super().dropMimeData(data, action, row, col, parent)
        if action == QtCore.Qt.CopyAction:
            #print('Copy action detected.')
            pass

        return True

    def moveRows(self, source_parent, source_row, count, destination_parent, destination_row):
        self.rowsAboutToBeMoved.emit(source_parent, source_row, source_row+count-1, destination_parent, destination_row)

        #print('Moving rows: ', source_row, ' #Rows ', count, ' to destination ', destination_row)

        extracted_list = []
        try:
            ''' Remove the sublist from the list '''
            for i in range(count):
                extracted_list.append(self._table.pop(source_row))

            ''' Go through the sublist and add its items '''
            for i in range(count):
                ''' As the _table was shortened during modification, the destination_row has to
                be adapted for insertion as well. '''
                if destination_row > source_row:
                    self._table.insert(destination_row-count+1,extracted_list.pop(len(extracted_list)-1))
                else:
                    self._table.insert(destination_row,extracted_list.pop(len(extracted_list)-1))

            self.send_data_changed()
            return True
        except:
            #print('moveRows failed')
            return False

        self.rowsMoved.emit(source_parent, source_row, source_row+count-1, destination_parent, destination_row)

    def send_data_changed(self):
        ''' Helper method that allows to send a dataChanged Signal for the whole table'''
        top_left_index = self.createIndex(0,0)
        bottom_right_index = self.createIndex(self.rowCount(),self.columnCount())
        self.dataChanged.emit(top_left_index,bottom_right_index)

    def getName(self, row):
        ''' Here, I assume that the filename is the name of the process'''
        return self._table[row]['filename']

    def getFilenameColumn(self):
        return self._headers.index('Filename')

    def getStartFocusColumn(self):
        return self._headers.index('F_start')

    def getEndFocusColumn(self):
        return self._headers.index('F_end')

    def getColumnByName(self, name):
        return self._headers.index(name)

    def getTime(self, row):
        return int(self._table[row].get_acquisition_time())

    def getFilter(self, row):
        return self._table[row]['filter']

    def getLaser(self, row):
        return self._table[row]['laser']

    def getShutterconfig(self, row):
        return self._table[row]['shutterconfig']

    def getZoom(self, row):
        return self._table[row]['zoom']

    def getImageCount(self, row):
        return self._table[row].get_image_count()

    def getXPosition(self, row):
        return self._table[row]['x_pos']

    def getYPosition(self, row):
        return self._table[row]['y_pos']

    def getZStartPosition(self, row):
        return self._table[row]['z_start']

    def getZEndPosition(self, row):
        return self._table[row]['z_end']

    def getRotationPosition(self, row):
        return self._table[row]['rot']

    def getTotalImageCount(self):
        ''' gets the total number of planes from the model '''
        return self._table.get_image_count()

    def get_acquisition_list(self, row=None):
        if row is None:
            return self._table
        else:
            return AcquisitionList([self._table[row]])

    def saveModel(self, filename):
        ''' Allows to serialize a model via pickle '''
        pickle.dump(self._table, open(filename, "wb" ))

    def setTable(self, table):
        self.modelAboutToBeReset.emit()
        self._table = table
        self.modelReset.emit()

    def loadModel(self, filename):
        self.modelAboutToBeReset.emit()
        self._table = pickle.load(open(filename, "rb" ))
        self.modelReset.emit()

    def deleteTable(self):
        self.modelAboutToBeReset.emit()
        self._table = AcquisitionList()
        self.modelReset.emit()
