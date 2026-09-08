'''
ETL (electrically tunable lens) configuration.

The zoom-dependent ETL offsets/amplitudes live in the CSV file referenced by
'ETL_cfg_file' (path relative to the working directory, see config/etl_parameters/).
The values below are the initial state before that file is applied.
'''
startup = {
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
'etl_l_delay_%' : 7.5,
'etl_l_ramp_rising_%' : 85,
'etl_l_ramp_falling_%' : 2.5,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.3,
'etl_r_delay_%' : 2.5,
'etl_r_ramp_rising_%' : 5,
'etl_r_ramp_falling_%' : 85,
'etl_r_amplitude' : 0.65,
'etl_r_offset' : 2.36,
}
