'''
Galvo configuration.

Make sure that 'galvo_l_amplitude' and 'galvo_r_amplitude' (in V) are correct,
i.e. not above the max input allowed by your galvos.
'''
import numpy as np

'''
Rescale the galvo amplitude when zoom is changed.
For example, if 'galvo_l_amplitude' = 1 V at zoom '1x', it will be 2 V at zoom '0.5x'
'''
scale_galvo_amp_with_zoom = True

startup = {
'galvo_l_frequency' : 99.9,
'galvo_l_amplitude' : 2.5,
'galvo_l_offset' : 0,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : np.pi/2,
'galvo_r_frequency' : 99.9,
#'galvo_r_amplitude' : 0.0, # currently not used
'galvo_r_offset' : 0,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/2,
}
