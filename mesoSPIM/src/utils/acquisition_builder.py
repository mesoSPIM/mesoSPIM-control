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
        pass
        self.acq_prelist = []

        self.dict = dict

        self.x_pos = self.dict['x_start']
        self.y_pos = self.dict['y_start']

        for i in range(0,self.dict['x_image_count']):
            self.x_pos = round(self.dict['x_start'] + i * self.dict['x_offset'],2)
            for j in range(0,self.dict['y_image_count']):
                self.y_pos = round(self.dict['y_start'] + j * self.dict['y_offset'],2)

                acq = Acquisition(   x_pos=self.x_pos,
                                     y_pos=self.y_pos,
                                     z_start=self.dict['z_start'],
                                     z_end=self.dict['z_end'],
                                     z_step=self.dict['z_step'],
                                     theta_pos=self.dict['theta_pos'],
                                     f_pos=round(self.dict['f_pos'],2),
                                     laser=self.dict['laser'],
                                     intensity=self.dict['intensity'],
                                     filter=self.dict['filter'],
                                     zoom=self.dict['zoom'],
                                     shutterconfig=self.dict['shutterconfig'],
                                     folder=self.dict['folder'],
                                     filename='tiling_file_'+str(i)+'_'+str(j)+'.raw'
                                     )

                self.acq_prelist.append(acq)

    def get_acquisition_list(self):
        return AcquisitionList(self.acq_prelist)
