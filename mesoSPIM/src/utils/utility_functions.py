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


def format_data_size(bytes):
    '''
    Converts bytes into human-readable format (kb, M, G)
    '''
    try:
        bytes = float(bytes)
        kb = bytes / 1024
    except Exception as e:
        print(f"{e}")
        return None
    if kb >= 1024:
        M = kb / 1024
        if M >= 1024:
            G = M / 1024
            return "%.1fG" % (G)
        else:
            return "%.1fM" % (M)
    else:
        return "%.1fkb" % (kb)