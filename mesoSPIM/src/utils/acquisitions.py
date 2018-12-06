'''
acquisitions.py
========================================

Helper classes for mesoSPIM acquisitions
'''

import indexed
import os.path

class Acquisition(indexed.IndexedOrderedDict):
    '''
    Custom acquisition dictionary. Contains all the information to run a single
    acquisition.

    Args:
        x_pos (float): X start position in microns
        y_pos (float): Y start position in microns
        z_start (float): Z start position in microns
        z_end (float): Z end position in microns
        z_step (float): Z stepsize in microns ,
        theta_pos (float): Rotation angle in microns
        f_pos (float): Focus position in microns
        laser (str): Laser designation
        intensity (int): Laser intensity in 0-100
        filter (str): Filter designation (has to be in the config)
        zoom (str): Zoom designation
        filename (str): Filename for the file to be saved

    Attributes:

    Note:
        Getting keys: ``keys = [key for key in acq1.keys()]``

    Example:
        Getting keys: ``keys = [key for key in acq1.keys()]``

    Todo:
        Testtodo-Entry

    '''

    def __init__(self,
                 x_pos=0,
                 y_pos=0,
                 z_start=0,
                 z_end=100,
                 z_step=10,
                 planes=10,
                 theta_pos=0,
                 f_pos=0,
                 laser = '488 nm',
                 intensity=0,
                 filter= 'Empty-Alignment',
                 zoom= '1x',
                 shutterconfig='Left',
                 folder='E:/tmp',
                 filename='one.raw',
                 etl_l_offset = 0,
                 etl_l_amplitude =0,
                 etl_r_offset = 0,
                 etl_r_amplitude = 0):

        super().__init__()

        self['x_pos']=x_pos
        self['y_pos']=y_pos
        self['z_start']=z_start
        self['z_end']=z_end
        self['z_step']=z_step
        self['planes']=planes
        self['rot']=theta_pos
        self['f_pos']=f_pos
        self['laser']=laser
        self['intensity']=intensity
        self['filter']=filter
        self['zoom']=zoom
        self['shutterconfig']=shutterconfig
        self['folder']=folder
        self['filename']=filename
        self['etl_l_offset']=etl_l_offset
        self['etl_l_amplitude']=etl_l_amplitude
        self['etl_r_offset']=etl_r_offset
        self['etl_r_amplitude']=etl_r_amplitude


    def __setitem__(self, key, value):
        super().__setitem__(key, value)

    def __call__(self, index):
        ''' This way the dictionary is callable with an index '''
        return self.values()[index]

    def get_keylist(self):
        ''' A list keys is returned for usage as a table header '''
        return [key for key in self.keys()]

    def get_capitalized_keylist(self):
        ''' Here, a list of capitalized keys is returned for usage as a table header '''
        return [key.capitalize() for key in self.keys()]

    def get_image_count(self):
        '''
        Method to return the number of planes in the acquisition
        '''
        image_count = abs(int((self['z_end'] - self['z_start'])/self['z_step']))

        return image_count

    def get_acquisition_time(self):
        '''
        Method to return the time the acquisition will take

        Returns:
            float: Acquisition time in seconds

        TODO: What if sweeptime changes?
        '''
        sweeptime = 0.2
        return sweeptime * self.get_image_count()

    def get_delta_z_dict(self):
        ''' Returns relative movement dict for z-steps '''
        if self['z_end'] > self['z_start']:
            z_rel = abs(self['z_step'])
        else:
            z_rel = -abs(self['z_step'])

        return {'z_rel' : z_rel}

    def get_startpoint(self):
        '''
        Provides a dictionary with the startpoint coordinates
        '''
        return {'x_abs': self['x_pos'],
                'y_abs': self['y_pos'],
                'z_abs': self['z_start'],
                'theta_abs': self['rot'],
                'f_abs': self['f_pos'],
                }

    def get_endpoint(self):
        return {'x_abs': self['x_pos'],
                'y_abs': self['y_pos'],
                'z_abs': self['z_end'],
                'theta_abs': self['rot'],
                'f_abs': self['f_pos'],
                }

    def get_midpoint(self):
        return {'x_abs': self['x_pos'],
                'y_abs': self['y_pos'],
                'z_abs': int((self['z_end']-self['z_start'])/2),
                'theta_abs': self['rot'],
                'f_abs': self['f_pos'],
                }

class AcquisitionList(list):
    '''
    Class for a list of acquisition objects

    Examples: "([acq1,acq2,acq3])" is due to the fact that list takes only a single argument
    acq_list = AcquisitionList([acq1,acq2,acq3])
    acq_list.time()
    > 3600
    acq_list.planes()
    > 18000

    acq_list[2](2)
    >10
    acq_list[2]['y_pos']
    >10
    acq_list[2]['y_pos'] = 34


    '''
    def __init__(self, *args):
        list.__init__(self, *args)

        ''' If no arguments are provided, create a
        default acquistion in the list '''

        if len(args) == 0:
            ''' Use a default acquistion '''
            self.append(Acquisition())

        # '''
        # In addition to the list of acquisition objects, the AcquisitionList also 
        # contains a rotation point that is save to rotate the sample to the target 
        # value.
        # '''
        # self.rotation_point = {'x_abs' : None, 'y_abs' : None, 'z_abs' : None}

    def get_capitalized_keylist(self):
        return self[0].get_capitalized_keylist()

    def get_keylist(self):
        '''
        Here, a list of capitalized keys is returnes for usage as a table header
        '''
        return self[0].get_keylist()

    def get_acquisition_time(self):
        '''
        Returns total time in seconds of a list of acquisitions
        '''
        time = 0

        for i in range(len(self)):
            time += self[i].get_acquisition_time()

        return time

    def get_image_count(self):
        '''
        Returns the total number of planes for a list of acquistions
        '''
        image_count = 0
        for i in range(len(self)):
            image_count += self[i].get_image_count()

        return image_count

    def get_startpoint(self):
        return self[0].get_startpoint()

    # def set_rotation_point(self, dict):
    #     self.rotation_point = {'x_abs' : dict['x_abs'], 'y_abs' : dict['y_abs'], 'z_abs':dict['z_abs']}

    # def delete_rotation_point(self):
    #     self.rotation_point = {'x_abs' : None, 'y_abs' : None, 'z_abs' : None}

    # def get_rotation_point_status(self):
    #     ''' Returns True if an rotation point was set, otherwise False '''
    #     if self.rotation_point['x_abs'] == None :
    #         return False
    #     else: 
    #         return True

    # def get_rotation_point(self):
    #     return self.rotation_point

    def has_rotation(self):
        '''
        Returns true if there is a single rotation in the acq_list.

        TODO: Better method name
        '''
        delta_rot = 0
        for i in range(len(self)-1):
            ''' self[i] is a acq_list element - an acquisition
                get_startpoint() returns the startpoint dict
                dict['theta_abs'] returns the start angle
            '''
            delta_rot = self[i+1].get_startpoint()['theta_abs']-self[i].get_startpoint()['theta_abs']
            if delta_rot != 0:
                return True
                break
        return False

    def check_for_existing_filenames(self):
        for i in range(len(self)):
            filename = self[i]['folder']+'/'+self[i]['filename']
            file_exists = os.path.isfile(filename)
            if file_exists:
                print('Attention: Existing file: ', filename)
                return True 
            else:
                return False

    def check_for_duplicated_filenames(self):
        duplicates = []
        filenames = []

        ''' Create a list of full file paths'''
        for i in range(len(self)):
            filename = self[i]['folder']+'/'+self[i]['filename']
            filenames.append(filename)

        duplicates = self.get_duplicates_in_list(filenames)

        if len(duplicates)==0:
            return False 
        else:
            print('Attention: Duplicated filename: ', duplicates)
            return True

    def get_duplicates_in_list(self, list):
        duplicates = []
        unique = set(list)
        for each in unique:
            count = list.count(each)
            if count > 1:
                duplicates.append(each)
        return duplicates