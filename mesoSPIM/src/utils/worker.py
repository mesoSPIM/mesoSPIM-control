import time

from PyQt5 import QtCore, QtWidgets

from .models import AcquisitionModel
from .config import config as cfg

class WorkerObject(QtCore.QObject):
    '''
    Worker object which has a few time-intensive methods, can signal
    its status and is able to listen to stop events.
    '''
    finished = QtCore.pyqtSignal()
    statusMessage = QtCore.pyqtSignal(str)

    progress = QtCore.pyqtSignal(dict)

    model_changed = QtCore.pyqtSignal(AcquisitionModel)

    position = QtCore.pyqtSignal(dict)

    def __init__(self, model):
        super(WorkerObject, self).__init__()

        ''' Set the table & view and model up '''
        self.model = model

        # self.mic = DemoMicroscope()

        self.stopflag = False

        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0
        self.theta_pos = 0
        self.f_pos = 0
        self.filter = ''
        self.zoom = ''
        self.laser = ''
        self.intensity = 0

        self.speed = 1000 # in um/s

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)

    @QtCore.pyqtSlot()
    def stop(self):
        self.stopflag = True

    def send_progress(self,
                      cur_acq,
                      tot_acqs,
                      cur_image,
                      images_in_acq,
                      total_image_count,
                      image_counter):

        dict = {'current_acq':cur_acq,
                'total_acqs' :tot_acqs,
                'current_image_in_acq':cur_image,
                'images_in_acq': images_in_acq,
                'total_image_count':total_image_count,
                'image_counter':image_counter,
        }
        self.progress.emit(dict)

    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(int)
    def start(self, row=None):
        if row==None:
            acq_list = self.model.get_acquisition_list()
        else:
            acq_list = self.model.get_acquisition_list(row)

        if acq_list.has_rotation() is True:
            print('Attention: Has rotation!')

        self.prepare_acquisition_list(acq_list)
        self.run_acquisition_list(acq_list)
        self.close_acquisition_list(acq_list)

    def prepare_acquisition(self, acq):
        '''
        Housekeeping: Preparre the acquisition
        '''

        print('Running Acquisition #', self.acquisition_count,
                ' with Filename: ', acq.get_filename())
        self.move_absolute(acq.get_startpoint())
        print('Setting Filter to: ', acq.get_filter())
        print('Setting Laser to: ', acq.get_laser())
        print('Setting Intensity to: ', acq.get_intensity())


    def run_acquisition(self, acq):
        steps = acq.get_image_count()

        for i in range(steps):
            if self.stopflag is True:
                break
            self.image_count += 1
            time.sleep(cfg.sweeptime)
            self.move_relative(acq.get_delta_z_dict())
            QtWidgets.QApplication.processEvents()
            self.send_progress(self.acquisition_count,
                               self.total_acquisition_count,
                               i,
                               steps,
                               self.total_image_count,
                               self.image_count)

    def close_acquisition(self, acq):
        self.acquisition_count += 1

    def prepare_acquisition_list(self, acq_list):
        self.stopflag = False
        self.image_count = 0
        self.acquisition_count = 0
        self.total_acquisition_count = len(acq_list)
        self.total_image_count = acq_list.get_image_count()

    def run_acquisition_list(self, acq_list):
        for acq in acq_list:
            name = acq.get_filename()
            _time = int(acq.get_acquisition_time())
            filter = acq.get_filter()
            total_steps = acq.get_image_count()

            displaystring = "Running acquisition with name: " + name + " for " + str(_time) + " seconds and filter:" + filter

            self.statusMessage.emit(displaystring)

            self.prepare_acquisition(acq)
            self.run_acquisition(acq)
            self.close_acquisition(acq)

    def close_acquisition_list(self, acq_list):
        if not self.stopflag:
            self.move_absolute(acq_list.get_startpoint())
        self.finished.emit()
        self.statusMessage.emit('Done')

    @QtCore.pyqtSlot()
    def add_row(self):
        self.model.insertRows(self.model.rowCount(),1)
        self.model_changed.emit(self.model)

    @QtCore.pyqtSlot()
    def delete_row(self):
        if self.model.rowCount() > 1:
            self.model.removeRows(self.model.rowCount()-1,1)
        else:
            self.statusMessage.emit("Can't delete last row!", 2)
        self.model_changed.emit(self.model)

    @QtCore.pyqtSlot(AcquisitionModel)
    def update_model_from_GUI(self, model=None):
        self.model = model
        print('Model in worker thread updated via GUI signal')

    def update_model_data(self):
        print('Model in Worker thread updated, sending signal')
        self.model_changed.emit(self.model)

    def move_relative(self, dict):
        if 'x_rel' in dict:
            self.x_pos += round(dict['x_rel'],2)

        if 'y_rel' in dict:
            self.y_pos += round(dict['y_rel'],2)

        if 'z_rel' in dict:
            self.z_pos += round(dict['z_rel'],2)

        if 'theta_rel' in dict:
            self.theta_pos += round(dict['theta_rel'],2)

        if 'f_rel' in dict:
            self.f_pos += round(dict['f_rel'],2)

    def move_absolute(self, dict):
        if 'x_abs' in dict:
            self.x_pos = dict['x_abs']

        if 'y_abs' in dict:
            self.y_pos = dict['y_abs']

        if 'z_abs' in dict:
            self.z_pos = dict['z_abs']

        if 'theta_abs' in dict:
            self.theta_pos = dict['theta_abs']

        if 'f_abs' in dict:
            self.f_pos = dict['f_abs']

    def report_position(self):
        ''' Emit a position dictionary for the GUI '''
        dict = {'x_pos': round(self.x_pos,2),
                'y_pos': round(self.y_pos,2),
                'z_pos': round(self.z_pos,2),
                'theta_pos': round(self.theta_pos,2),
                'f_pos': round(self.f_pos,2),
                }

        self.position.emit(dict)

    def zero_xy(self):
        self.x_pos = 0
        self.y_pos = 0

    def zero_z(self):
        self.z_pos = 0

    def zero_focus(self):
        self.f_pos = 0

    def zero_rot(self):
        self.theta_pos = 0

    def set_filter(self, filter):
        self.filter = filter

    def set_zoom(self, zoom):
        self.zoom = zoom

    def set_laser_and_intensity(self, laser, intensity):
        self.laser = laser
        self.intensity = intensity
