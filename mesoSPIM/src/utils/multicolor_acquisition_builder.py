''' Classes that define acquisition builders:

Take a dict with information and return an acquisition list
'''
from .acquisitions import Acquisition, AcquisitionList
import numpy as np

class AcquisitionListBuilder():
    '''
    Generic Acquisition List Builder as parent class?

    TODO: Write this class
    '''
    pass

class MulticolorTilingAcquisitionListBuilder():
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
        self. ScanMatrix = self.dict['checked_tile']

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
        Core loop: Create an acquisition list for all x & y & channel values
        '''
        tilecount = 0
        LoopOrderList = self.dict['loop_order']

        if LoopOrderList[2] == 0:
            range1 = range(0,self.dict['x_image_count'])
            evalStr1 = 'self.x_pos = eval(\'round(self.x_start + i * self.x_offset,2)\')'        
        elif LoopOrderList[2] == 1:
            range1 = range(0,self.dict['y_image_count'])
            evalStr1 = 'self.y_pos = eval(\'round(self.y_start + i * self.y_offset,2)\')'
        elif LoopOrderList[2] == 2: 
            range1 = range(0, len(self.dict['channels']))
            evalStr1 = 'channeldict = Allchannel[i]'
        
        if LoopOrderList[1] == 0:
            range2 = range(0,self.dict['x_image_count'])
            evalStr2 = 'self.x_pos = eval(\'round(self.x_start + j * self.x_offset,2)\')'
        elif LoopOrderList[1] == 1:
            range2 = range(0,self.dict['y_image_count'])
            evalStr2 = 'self.y_pos = eval(\'round(self.y_start + j * self.y_offset,2)\')'
        elif LoopOrderList[1] == 2: 
            range2 = range(0, len(self.dict['channels']))
            evalStr2 = 'channeldict = Allchannel[j]'
  

        if LoopOrderList[0] == 0:
            range3 = range(0,self.dict['x_image_count'])
            evalStr3 = 'self.x_pos = eval(\'round(self.x_start + c * self.x_offset,2)\')'
        elif LoopOrderList[0] == 1:
            range3 = range(0,self.dict['y_image_count'])
            evalStr3 = 'self.y_pos = eval(\'round(self.y_start + c * self.y_offset,2)\')'
        elif LoopOrderList[0] == 2: 
            range3 = range(0, len(self.dict['channels']))
            evalStr3 = 'channeldict = Allchannel[c]'
           
        ldict = {'channeldict' : {}, 'Allchannel' : self.dict['channels']}
        ldict.update(locals())

        # following if clause formulate the loop for left-right illumination
        if self.dict['illumination'] == 2: # 1:sequentially two-side illumination,interleaved
            illumination_side = ['Left','Right']
        elif self.dict['illumination'] == 0:
            illumination_side = ['Left']
        elif self.dict['illumination'] == 1:
            illumination_side = ['Right']          
        else:
            pass

        variable_positions = {"0":"c", "1":"j", "2":"i"}
        x = LoopOrderList.index(0)
        y = LoopOrderList.index(1)
        m = variable_positions[str(x)]
        n = variable_positions[str(y)]

        if LoopOrderList[0] == 2:
            channelcount = 0
        for i in range1:
            ldict['i'] = i
            exec(evalStr1,globals(),ldict)

            if LoopOrderList[1] == 2:
                channelcount = 0     
            for j in range2:
                ldict['j'] = j
                exec(evalStr2,globals(),ldict)

                if LoopOrderList[2] == 2:
                    channelcount = 0
                for c in range3:
                    ''' Get a single channeldict out of the list of dicts '''
                    ldict['c'] = c
                    exec(evalStr3,globals(),ldict)                   
                    channeldict = ldict['channeldict']
                    
                    if self.dict['illumination'] == 3:
                        illumination_side = self.determine_light_side()
                    
                    range4 = range(0,len(illumination_side))
                    
                    for d in range4:
                        #if max(range4) > 1:
                        self.dict['shutterconfig'] = illumination_side[d]
                        #else:
                        #    self.dict['shutterconfig'] = illumination_side
                    
                        acq = Acquisition(  x_pos=self.x_pos,
                                            y_pos=self.y_pos,
                                            z_start=self.dict['z_start'],
                                            z_end=self.dict['z_end'],
                                            z_step=self.dict['z_step'],
                                            theta_pos=self.dict['theta_pos'],
                                            f_start=round(channeldict['f_start'],2),
                                            f_end=round(channeldict['f_end'],2),
                                            laser=channeldict['laser'],
                                            intensity=channeldict['intensity'],
                                            filter=channeldict['filter'],
                                            zoom=self.dict['zoom'],
                                            shutterconfig=self.dict['shutterconfig'],
                                            folder=self.dict['folder'],
                                            filename='tiling_file_t'+str(tilecount)+'_c'+str(channelcount)+'.raw',
                                            etl_l_offset=channeldict['etl_l_offset'],
                                            etl_l_amplitude=channeldict['etl_l_amplitude'],
                                            etl_r_offset=channeldict['etl_r_offset'],
                                            etl_r_amplitude=channeldict['etl_r_amplitude'],
                                            to_scan = self.ScanMatrix[vars()[m],vars()[n]]
                                )
                        ''' Update number of planes as this is not done by the acquisition 
                        object itself '''
                        acq['planes']=acq.get_image_count()

                        self.acq_prelist.append(acq)
                        
                        if LoopOrderList[2] == 2:
                            channelcount +=1
                        

                    tilecount += 1

    def get_acquisition_list(self):
        return AcquisitionList(self.acq_prelist)
        
    def determine_light_side(self):
        x_fov = self.dict['x_fov']
        print(x_fov)
        x_start = self.x_pos - x_fov/2
        x_end = self.x_pos + x_fov/2

        if x_start*x_end >= 0 and self.x_pos > 0:
            illumination_side = ["Right"]
        elif x_start*x_end >= 0 and self.x_pos < 0:
            illumination_side = ["Left"]
        elif x_start*x_end < 0:
            illumination_side = ["Left","Right"]
    
        return illumination_side