''' Classes that define acquisition builders:

Take a dict with information and return an acquisition list
'''
from .acquisitions import Acquisition, AcquisitionList

class AcquisitionListBuilder():
    '''
    Generic Acquisition List Builder as parent class?

    TODO: Write this class
    '''
    pass

class TilingAcquisitionListBuilder():
    '''
    TODO: Filename generation

    self.dict['x_start']
    self.dict['x_end']
    self.dict['y_start']
    self.dict['y_end']
    self.dict['z_start']
    self.dict['z_end']
    self.dict['z_step']
    self.dict['theta_pos']
    self.dict['f_pos']
    self.dict['x_offset'] # Offset always larger than 0
    self.dict['y_offset'] # Offset always larger than 0
    self.dict['x_image_count']
    self.dict['y_image_count']
    '''

    def __init__(self, dict):
        self.acq_prelist = []

        self.dict = dict

        self.x_start = self.dict['x_start']
        self.y_start = self.dict['y_start']
        self.x_end = self.dict['x_end']
        self.y_end = self.dict['y_end']

        ''' 
        Reverse direction of the offset if pos_end < pos_start
        '''
        if self.x_start < self.x_end:
            self.x_offset = self.dict['x_offset']
        else:
            self.x_offset = -self.dict['x_offset']
            
        if self.y_start < self.y_end:
            self.y_offset = self.dict['y_offset']
        else:
            self.y_offset = -self.dict['y_offset']

        '''
        Core loop: Create an acquisition list for all x & y values
        '''
        tilecount = 0
        for i in range(0,self.dict['x_image_count']):
            self.x_pos = round(self.x_start + i * self.x_offset,2)
            for j in range(0,self.dict['y_image_count']):
                self.y_pos = round(self.y_start + j * self.y_offset,2)


                acq = Acquisition(   x_pos=self.x_pos,
                                     y_pos=self.y_pos,
                                     z_start=self.dict['z_start'],
                                     z_end=self.dict['z_end'],
                                     z_step=self.dict['z_step'],
                                     theta_pos=self.dict['theta_pos'],
                                     f_start=round(self.dict['f_start'],2),
                                     f_end=round(self.dict['f_end'],2),
                                     laser=self.dict['laser'],
                                     intensity=self.dict['intensity'],
                                     filter=self.dict['filter'],
                                     zoom=self.dict['zoom'],
                                     shutterconfig=self.dict['shutterconfig'],
                                     folder=self.dict['folder'],
                                     filename='tiling_file_'+str(tilecount)+'.raw',
                                     etl_l_offset=self.dict['etl_l_offset'],
                                     etl_l_amplitude=self.dict['etl_l_amplitude'],
                                     etl_r_offset=self.dict['etl_r_offset'],
                                     etl_r_amplitude=self.dict['etl_r_amplitude'],
                                     )
                ''' Update number of planes as this is not done by the acquisition 
                object itself '''
                acq['planes']=acq.get_image_count()

                self.acq_prelist.append(acq)
                tilecount += 1

    def get_acquisition_list(self):
        return AcquisitionList(self.acq_prelist)
