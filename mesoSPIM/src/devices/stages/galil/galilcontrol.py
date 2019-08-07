"""
mesoSPIM Module for controlling Galil-Stages (by Steinmayer-Mechatronik/Feinmess)

Author: Fabian Voigt

#TODO
"""
import copy
import time
import traceback

from PyQt5 import QtWidgets, QtCore, QtGui

import gclib

import logging
logger = logging.getLogger(__name__)

class StageControlGalil(QtCore.QObject):
    '''
    Class to control the Galil stage with 3 axes

    TODO
    * correct tracking of the internal and external absolute positions: Do everything via the Galil controller
    * is it truly a good idea to set the stage to zero for each new instantiation?

    '''

    def __init__(self,
                 COMport,
                 baudrate='19200',
                 timeout='60000',
                 x_encodercounts_per_um = 0,
                 y_encodercounts_per_um = 2,
                 z_encodercounts_per_um = 2):
        super().__init__()

        self.xpos = 0
        self.ypos = 0
        self.zpos = 0
        self.initflag = True
        self.x_encodercounts_per_um = x_encodercounts_per_um
        self.y_encodercounts_per_um = y_encodercounts_per_um
        self.z_encodercounts_per_um = z_encodercounts_per_um
        self.unit = 'micron'
        self.COMport = COMport
        self.baudrate = baudrate
        self.timeout = timeout # in ms

        self.g = gclib.py()
        #Typical connectionstring: 'COM1 --baud 19200 --subscribe ALL --timeout 60000'
        #self.connectionstring = self.COMport + ' --baud ' + self.baudrate + ' --subscribe ALL --timeout ' + self.timeout
        '''Dirty hack to get IP connection going:'''
        self.connectionstring = self.COMport + ' --direct'

        self.g.GOpen(self.connectionstring)

        # Set absolute position to zero - risky at the limits of the movement range...
        #self.g.GCommand('DPX=0')
        #self.g.GCommand('DPY=0')
        #self.g.GCommand('DPZ=0')

        self.read_position('x')
        self.read_position('y')
        self.read_position('z')
        self.initflag = False

    def close_stage(self):
        self.g.GClose()

    def stage_info(self):
        self.message = self.g.GInfo()
        return self.message

    def read_position(self, axis):
        self.axisstring = copy.copy(axis)
        self.axis = axis.capitalize()
        try:
            self.position = self.g.GCommand('RP'+self.axis)
        except Exception as error:
            logger.exception(error)
        '''Float and try & except added here to solve weird bug with

        "ValueError: invalid literal for int() with base 10: '' "
        Returning a large negative value as an error signal
        '''
        if self.axisstring == 'x':
            try:
                xpos = int(float(self.position)) / self.x_encodercounts_per_um
                if abs(self.xpos - xpos) < 2000 or self.initflag == True:
                    self.xpos = xpos
                    return self.xpos
                else:
                    return self.xpos
            except Exception as error:
                logger.exception(error)
                return self.xpos
        elif self.axisstring == 'y':
            try:
                ypos = int(float(self.position)) / self.y_encodercounts_per_um
                if abs(self.ypos - ypos) < 2000 or self.initflag == True:
                    self.ypos = ypos
                    return self.ypos
                else:
                    return self.ypos
            except Exception as error:
                logger.exception(error)
                return self.ypos
        else:
            try:
                zpos = int(float(self.position)) / self.z_encodercounts_per_um
                if abs(self.zpos - zpos) < 2000 or self.initflag == True:
                    self.zpos = zpos
                    return self.zpos
                else:
                    return self.zpos
            except Exception as error:
                logger.exception(error)
                return self.zpos
        
    def read_x_position_um(self):
        return self.read_position('x')

    def read_y_position_um(self):
        return self.read_position('y')

    def read_z_position_um(self):
        return self.read_position('z')

    def set_axis_to_zero(self, axis):
        if axis == 'x':
            self.xpos = 0
        elif axis == 'y':
            self.ypos = 0
        else:
            self.zpos = 0

        self.axis = axis.capitalize()
        self.g.GCommand('DP'+self.axis+'=0')

    def move_relative(self, xrel = 0, yrel = 0, zrel = 0):
        '''Move relative method

        Movements larger than 250 microns should be slower

        Values are taken from the default (delivery) settings of the Galil controller.
        '''
        if abs(xrel) > 250:
            self.g.GCommand('SPX=5000')
        else:
            self.g.GCommand('SPX=20000')

        if abs(yrel) > 250:
            self.g.GCommand('SPY=5000')
        else:
            self.g.GCommand('SPY=20000')

        if abs(zrel) > 250:
            self.g.GCommand('SPZ=5000')
        else:
            self.g.GCommand('SPZ=50000')

        # Send movement commands
        try:
            '''z command comes first so that there is no slice loss '''
            self.g.GCommand('PRZ='+str(int(zrel*self.z_encodercounts_per_um)))
            self.g.GCommand('PRX='+str(int(xrel*self.x_encodercounts_per_um)))
            self.g.GCommand('PRY='+str(int(yrel*self.y_encodercounts_per_um)))
            self.g.GCommand('BG')
        except Exception as error:
            logger.exception(error)

        # Update internal values
        self.xpos += xrel
        self.ypos += yrel
        self.zpos += zrel

    def move_absolute(self, xabs = None, yabs = None, zabs = None):
        '''Move absolution function, implementation is ugly.

        The default none as an argument is dangerous. Very dangerous:
        If you run move_absolute once with e.g. zabs = 0, the others get
        nonetype which leads to type erros

        There is also no speed control apart from some z adaptation
        '''

        # Send movement commands
        if xabs != None:
            ''' Adapt speed to distance '''
            position = self.read_x_position_um()
            if abs(xabs-position) > 250:
                self.g.GCommand('SPX=5000')
            else:
                self.g.GCommand('SPX=50000')

            string = 'PAX='+str(int(xabs*self.x_encodercounts_per_um))
            #print(string)
            self.g.GCommand(string)  
            self.xpos = xabs
               
        if yabs != None:
            ''' Adapt speed to distance '''
            position = self.read_y_position_um()
            if abs(yabs-position) > 250:
                self.g.GCommand('SPY=5000')
            else:
                self.g.GCommand('SPY=50000')

            string = 'PAY='+str(int(yabs*self.y_encodercounts_per_um))
            #print(string)   
            self.g.GCommand(string)  
            self.ypos = yabs
               
        if zabs != None:
            ''' Adapt speed to distance '''
            position = self.read_z_position_um()
            if abs(zabs-position) > 250:
                self.g.GCommand('SPZ=5000')
            else:
                self.g.GCommand('SPZ=50000')

            string = 'PAZ='+str(int(zabs*self.z_encodercounts_per_um))
            #print(string)
            self.g.GCommand(string)
            self.zpos = zabs
        
        try:
            self.g.GCommand('BG')
        except:
            print('Error occured')

    def move_absolute_in_z(self, zabs):
        '''get current position and adapt speed accordingly'''

        position = self.read_z_position_um()
        if abs(zabs-position) > 250:
            self.g.GCommand('SPZ=5000')
        else:
            self.g.GCommand('SPZ=50000')

        self.g.GCommand('PAZ='+str(int(zabs*self.z_encodercounts_per_um)))
        self.g.GCommand('BG')
        self.zpos = zabs

    def set_speed(self, axis, speed):
        '''Sets the movement speed via the Galil SP command'''
        if axis == 'x':
            self.g.GCommand('SPX='+str(int(speed)))
        elif axis == 'y':
            self.g.GCommand('SPY='+str(int(speed)))
        else:
            self.g.GCommand('SPZ='+str(int(speed)))

    def set_acceleration(self, axis, acceleration):
        '''Sets the acceleration via the Galil AC command'''
        if axis == 'x':
            self.g.GCommand('ACX='+str(int(acceleration)))
        elif axis == 'y':
            self.g.GCommand('ACY='+str(int(acceleration)))
        else:
            self.g.GCommand('ACZ='+str(int(acceleration)))

    def set_deceleration(self, axis, deceleration):
        '''Sets the deceleration via the Galil DC command'''
        if axis == 'x':
            self.g.GCommand('DCX='+str(int(acceleration)))
        elif axis == 'y':
            self.g.GCommand('DCY='+str(int(acceleration)))
        else:
            self.g.GCommand('DCZ='+str(int(acceleration)))

    def stop_all_movements(self):
        self.g.GCommand('ST')
        '''After ST, also program execution stops -- this is risky, here it 
        is assumed that any program runs only the handcontroller and does 
        not induce any movement.'''
        self.execute_program()

    def wait_until_done(self, axis):
        self.g.GMotionComplete(axis.upper())

    def execute_program(self):
        '''Executes program stored on the Galil controller'''
        self.g.GCommand('XQ')