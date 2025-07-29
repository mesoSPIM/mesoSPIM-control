'''
acquisitions.py
========================================

Helper classes for mesoSPIM acquisitions
'''

import indexed
import os.path
import logging
logger = logging.getLogger(__name__)


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
                 f_start=0,
                 f_end=0,
                 laser='488 nm',
                 intensity=0,
                 filter='Empty',
                 zoom='1x',
                 shutterconfig='Left',
                 folder='tmp',
                 filename='one.tif',
                 etl_l_offset=0,
                 etl_l_amplitude=0,
                 etl_r_offset=0,
                 etl_r_amplitude=0,
                 processing='MAX'):

        super().__init__()

        self['x_pos']=x_pos
        self['y_pos']=y_pos
        self['z_start']=z_start
        self['z_end']=z_end
        self['z_step']=z_step
        self['planes']=planes
        self['rot']=theta_pos
        self['f_start']=f_start
        self['f_end']=f_end
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
        self['processing']=processing


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
        return abs(round((self['z_end'] - self['z_start'])/self['z_step'])) + 1

    def get_acquisition_time(self, framerate):
        '''
        Method to return the time the acquisition will take at a certain 
        framerate.

        Args:
            float: framerate of the microscope 

        Returns:
            float: Acquisition time in seconds
        '''
        return self.get_image_count()/framerate

    def get_delta_z_and_delta_f_dict(self, inverted=False):
        ''' Returns relative movement dict for z- and f-steps '''
        if self['z_end'] > self['z_start']:
            z_rel = abs(self['z_step'])
        else:
            z_rel = -abs(self['z_step'])

        ''' Calculate f-step '''
        image_count = self.get_image_count()
        if image_count >= 1:
            f_rel = abs((self['f_end'] - self['f_start'])/image_count)
        else:
            f_rel = 0
        if self['f_end'] < self['f_start']:
            f_rel = -f_rel
        
        if not inverted:
            return {'x_rel' : 0, 'y_rel': 0, 'z_rel' : z_rel, 'f_rel' : f_rel, 'theta_rel': 0}
        else:
            return {'x_rel' : 0, 'y_rel': 0, 'z_rel' : -z_rel, 'f_rel' : -f_rel, 'theta_rel': 0}

    def get_delta_dict(self):
        ''' Returns relative movement dict for z-steps and f-steps'''

        ''' Calculate z-step '''
        if self['z_end'] > self['z_start']:
            z_rel = abs(self['z_step'])
        else:
            z_rel = -abs(self['z_step'])

        ''' Calculate f-step
        image_count = self.get_image_count()
        f_rel = abs((self['f_end'] - self['f_start'])/image_count)
        if self['f_end'] < self['f_start']:
            f_rel = -f_rel
        '''

        return {'z_rel' : z_rel}

    def get_startpoint(self):
        '''
        Provides a dictionary with the startpoint coordinates
        '''
        return {'x_abs': self['x_pos'],
                'y_abs': self['y_pos'],
                'z_abs': self['z_start'],
                'theta_abs': self['rot'],
                'f_abs': self['f_start'],
                }

    def get_endpoint(self):
        return {'x_abs': self['x_pos'],
                'y_abs': self['y_pos'],
                'z_abs': self['z_end'],
                'theta_abs': self['rot'],
                'f_abs': self['f_end'],
                }

    def get_focus_stepsize_generator(self, f_stage_min_step_um=0.25):
        ''''
        Provides a generator object to correct rounding errors for focus tracking acquisitions.

        The focus stage has to travel a shorter distance than the sample z-stage, ideally only
        a fraction of the z-step size. However, due to the limited minimum step size of the focus stage,
        rounding errors can accumulate over thousands of steps.

        Therefore, the generator tracks the rounding error and applies correcting steps here and there
        to minimize the error.

        This assumes a minimum step size of around 0.25 micron that the focus stage is capable of.

        This method contains lots of round functions to keep residual rounding errors at bay.
        '''
        steps = self.get_image_count()
        f_step = abs((self['f_end'] - self['f_start'])/steps)
        logger.debug(f"Focus interpolation: f_start, f_end, f_step, steps: {self['f_start'], self['f_end'], f_step, steps}")
        feasible_f_step = max(f_stage_min_step_um * (f_step // f_stage_min_step_um),
                              f_stage_min_step_um)  # Round to nearest multiple of f_stage_min_step_um
        if self['f_end'] < self['f_start']:
            f_step = -f_step
            feasible_f_step = -feasible_f_step

        expected_focus = 0
        focus = 0
        for i in range(steps):
            focus_error = round(expected_focus - focus, 5)
            new_step = round(focus_error / f_stage_min_step_um) * f_stage_min_step_um + feasible_f_step # this can be zero, and it is correct
            yield new_step
            logger.debug(f"Relative focus: new_step, actual, expected, error: {new_step, focus, expected_focus, focus_error}, um")
            focus += new_step
            focus = round(focus, 5)
            expected_focus += f_step


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
        Here, a list of capitalized keys is returned for usage as a table header
        '''
        return self[0].get_keylist()

    def get_acquisition_time(self, framerate):
        '''
        Returns total time in seconds of a list of acquisitions
        '''
        time = 0
        for i in range(len(self)):
            time += self[i].get_acquisition_time(framerate)

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

    def get_all_filenames(self):
        ''' Returns a list of all filenames '''
        filename_list = []
        for i in range(len(self)):
            filename = self[i]['folder']+'/'+self[i]['filename']
            filename_list.append(filename)
        return filename_list

    def check_for_existing_filenames(self):
        ''' Returns a list of existing filenames '''
        filename_list = []
        for i in range(len(self)):
            filename = self[i]['folder']+'/'+self[i]['filename']
            file_exists = os.path.isfile(filename)
            if file_exists:
                filename_list.append(filename)
        return filename_list

    def check_filename_extensions(self):
        '''Returns files that have no extension, so their format is undefined.'''
        filename_list = []
        for i in range(len(self)):
            filename = self[i]['filename']
            ext = os.path.splitext(filename)[1]
            if ext == '':
                filename_list.append(filename)
        return filename_list

    def check_for_duplicated_filenames(self):
        ''' Returns a list of duplicated filenames '''
        filenames = []
        # Create a list of full file paths
        for i in range(len(self)):
            if self[i]['filename'][-3:] != '.h5':
                filename = self[i]['folder']+'/'+self[i]['filename']
                filenames.append(filename)
        duplicates = self.get_duplicates_in_list(filenames)

        return duplicates

    def check_for_nonexisting_folders(self):
        ''' Returns a list of nonexisting folders '''
        nonexisting_folders = []
        for i in range(len(self)):
            folder = self[i]['folder']
            if not os.path.isdir(folder):
                nonexisting_folders.append(folder)
        
        return nonexisting_folders

    def get_duplicates_in_list(self, in_list):
        duplicates = []
        unique = set(in_list)
        for each in unique:
            count = in_list.count(each)
            if count > 1:
                duplicates.append(each)
        return duplicates

    def get_n_shutter_configs(self):
        """Get the number of unique shutter configs (1 or 2)"""
        sconfig_list = [a['shutterconfig'] for a in self]
        sconfig_set = set(sconfig_list)
        return len(sconfig_set)

    def get_n_angles(self):
        """Get the number of unique angles"""
        angle_list = [a['rot'] for a in self]
        angle_set = set(angle_list)
        return len(angle_set)

    def get_n_lasers(self):
        """Get the number of unique laser lines"""
        laser_list = [a['laser'] for a in self]
        laser_set = set(laser_list)
        return len(laser_set)

    def get_n_tiles(self):
        """Get the number of tiles as unique (x,y,z_start,rot) combinations"""
        tile_list = []
        for a in self:
            tile_str = f"{a['x_pos']}{a['y_pos']}{a['z_start']}{a['rot']}"
            if not tile_str in tile_list:
                tile_list.append(tile_str)
        return len(tile_list)

    def get_tile_index(self, acq):
        """Get the the tile index for given acquisition"""
        acq_str = f"{acq['x_pos']}{acq['y_pos']}{acq['z_start']}{acq['rot']}"
        tile_list = []
        for a in self:
            tile_str = f"{a['x_pos']}{a['y_pos']}{a['z_start']}{a['rot']}"
            if not tile_str in tile_list:
                tile_list.append(tile_str)
        return tile_list.index(acq_str)

    def get_unique_attr_list(self, key: str = 'laser') -> list:
        """Return ordered list of acquisition attributes.

        Parameters:
        -----------
            key: str
                One of ('laser', 'shutterconfig', 'rot')

        Returns:
        --------
            List of strings, e.g. ('488', '561') for key='laser', in the order of acquisition.
        """
        attributes = ('laser', 'shutterconfig', 'rot')
        assert key in attributes, f'Key {key} must be one of {attributes}.'
        unique_list = []
        for acq in self:
            if acq[key] not in unique_list:
                unique_list.append(acq[key])
        return unique_list

    def find_value_index(self, value: str = '488 nm', key: str = 'laser'):
        """Find the attribute index in the acquisition list.
        Example:
        al = AcquisitionList([Acquisition(), Acquisition(), Acquisition(), Acquisition()])
        al[0]['laser'] = '488 nm' #
        al[1]['laser'] = '488 nm' # gets removed because non-unique
        al[2]['laser'] = '561 nm' #
        al[3]['laser'] = '637 nm' #
        Output:
        al.find_value_index('488 nm', 'laser') # -> 0
        al.find_value_index('561 nm', 'laser') # -> 1
        al.find_value_index('637 nm', 'laser') # -> 2
        """
        unique_list = self.get_unique_attr_list(key)
        assert value in unique_list, f"Value({value}) not found in list {unique_list}"
        return unique_list.index(value)



