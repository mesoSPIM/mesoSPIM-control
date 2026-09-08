'''
ImageWriter plugin parameters for a demo/simulation machine (e.g. a laptop).

Identical to plugins/writers/production_writers.py apart from the shared-memory ring buffer of
MP_OME_Zarr_Writer, which is kept small so that the writer fits in the RAM of a laptop.
'''
include('plugins/writers/production_writers.py')

MP_OME_Zarr_Writer.update({'ring_buffer_size': 16}) # 512 on a production workstation
