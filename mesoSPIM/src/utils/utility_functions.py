'''
Contains a variety of mesoSPIM utility functions
'''

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
    Converts bytes into human-readable format (kb, MB, GB)
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
            return "%.1f GB" % (G)
        else:
            return "%.1f MB" % (M)
    else:
        return "%.1f kb" % (kb)


def write_line(file, key='', value=''):
    ''' Little helper method to write a single line with a key and value for metadata
    Adds a line break at the end.
    '''
    if key != '':
        file.write('['+str(key)+'] '+str(value) + '\n')
    else:
        file.write('\n')

def gb_size_of_array_shape(shape):
        '''Given a tuple of array shape, return the size in GB of at uint16 array'''
        for idx,ii in enumerate(shape):
            if idx == 0:
                total = ii
            else:
                total *= ii
        total = total * 16 / 8
        return total / 1024**3


def replace_with_underscores(string):
    ''' Replaces spaces and slashes with underscores '''
    s = string.replace(' ', '_').replace('/', '_')
    return s