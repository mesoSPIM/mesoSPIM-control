import os
import time
import numpy as np
import tifffile
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter, WriterCapabilities, WriteRequest, API_VERSION, FileNaming, \
    WriteImage, FinalizeImage
from pprint import pprint

class ShamWriter(ImageWriter):
    '''Do not write data, just a sham writer for testing and debugging purposes'''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'Sham_Writer'

    @classmethod
    def capabilities(cls):
        return WriterCapabilities(
            dtype=["uint8", "uint16", "float32"],
            ndim=[2, 3],
            supports_chunks=False,
            supports_compression=False,
            supports_multiscale=False,
            supports_overwrite=False,
            streaming_safe=True,
        )
    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        return ['sham']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'Sham Writer - Fake .sham files', # Selection Box Test when selecting file format
            WindowTitle = "Write Sham Writer - no I/O",
            WindowSubTitle = "Name will be inthe following format:\n {Description}_Mag{}_Tile{}_Ch{}_Flt{}_Sh{}_Rot{}.sham",
            WindowDescription = cls.name(), # Unique description to register with ui
            IncludeMag = True,
            IncludeTile = True,
            IncludeChannel = True,
            IncludeFilter = True,
            IncludeShutter = True,
            IncludeRotation = True,
            IncludeSuffix = None,
            SingleFileFormat = False,  # Will all tiles be written into 1 file (.h5 for example)
            IncludeAllChannelsInSingleFileFormat = True,  # Will put all channels in name if SingleFileFormat==True
        )

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), f'URI suffix not compatible with {self.name()}'
        uri = self.ensure_path(req.uri)
        print(f'In ShamWriter.open(), writer would open file at: {uri}')
        print('\n\n--- WriteRequest details ---\n\n')
        pprint(req)

        self.z_depth = req.shape[0]

    def write_frame(self, data: WriteImage) -> None:
        print(f'Frame {data.current_image_counter + 1} of {self.z_depth} received in ShamWriter.write_frame(), shape: {data.image.shape}, tile: {data.tile_number}')

    def finalize(self, finalize_image=FinalizeImage) -> None:
        try:
            print(f'ShamWriter.finalize()')
        except Exception as e:
            logger.error(f'{e}')

    def abort(self) -> None:
        print('ShamWriter.abort')