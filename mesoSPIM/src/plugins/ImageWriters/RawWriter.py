import os
import time
import numpy as np
import tifffile
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter, WriterCapabilities, WriteRequest, API_VERSION, FileNaming, \
    WriteImage, FinalizeImage

class TiffWriter(ImageWriter):
    '''Write Images as RAW memory mapped numpy files'''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'RAW_Writer'

    @classmethod
    def capabilities(cls):
        return WriterCapabilities(
            dtype=["uint16"],
            ndim=[2, 3],
            supports_chunks=False,
            supports_compression=False,
            supports_multiscale=False,
            supports_overwrite=False,
            streaming_safe=True,
        )
    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        return ['raw']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'Individual Raw Files: ~.raw', # Selection Box Test when selecting file format
            WindowTitle = "Autogenerate RAW filenames",
            WindowSubTitle = "Names can be customized:\n {Description}_Mag{}_Tile{}_Ch{}_Sh{}_Rot{}.raw",
            WindowDescription = cls.name(), # Unique description to register with ui
            IncludeMag = True,
            IncludeTile = True,
            IncludeChannel = True,
            IncludeShutter = True,
            IncludeRotation = True,
            IncludeSuffix = None,
            SingleFileFormat = False,  # Will all tiles be written into 1 file (.h5 for example)
            IncludeAllChannelsInSingleFileFormat = True,  # Will put all channels in name if SingleFileFormat==True
        )

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), f'URI suffix not compatible with {self.name()}'
        self.fsize = req.shape[1] * req.shape[2]
        self.xy_stack = np.memmap(req.uri, mode="write", dtype=np.uint16, shape=self.fsize * req.shape[0])

    def write_frame(self, data: WriteImage) -> None:
        self.xy_stack[data.current_image_counter * self.fsize:(data.current_image_counter + 1) * self.fsize] = data.image.flatten()

    def finalize(self, finalize_image=FinalizeImage) -> None:
        try:
            del self.xy_stack
        except Exception as e:
            logger.error(f'{e}')

    def abort(self) -> None:
        del self.xy_stack