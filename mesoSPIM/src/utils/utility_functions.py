'''
Contains a variety of mesoSPIM utility functions
'''

import numpy as np

def convert_seconds_to_string(delta_t):
    '''
    Converts an input value in seconds into a string in the format hh:mm:ss

    Interestingly, a variant using np.divmod is around 4-5x slower in initial tests.
    '''
    if delta_t <= 0:
        return '--:--:--'
    else:
        hours, remainder = divmod(delta_t, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
