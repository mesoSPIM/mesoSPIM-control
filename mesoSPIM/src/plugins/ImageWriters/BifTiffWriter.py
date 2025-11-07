import os
import time
import numpy as np
import tifffile
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import Writer, WriterCapabilities, WriteRequest, API_VERSION, FileNaming, \
    WriteImage, FinalizeImage


class TiffWriter(Writer):
    '''Write Images as Tiff Files'''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'Big_Tiff_Writer'

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
        return ['btf', 'tf2', 'tf8']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'BigTIFF files: ~.btf', # Selection Box Test when selecting file format
            WindowTitle = "Autogenerate BigTIFF filenames",
            WindowSubTitle = "Names will be in BigStitcher auto-loader format:\n {Description}_Mag{}_Tile{}_Ch{}_Sh{}_Rot{}.tiff",
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
        uri = self.ensure_path(req.uri)
        self.writer = tifffile.TiffWriter(uri, bigtiff=True)

    def write_frame(self, data: WriteImage):
        self.writer.write(data.image[np.newaxis, ...], contiguous=False, resolution=data.x_res,
                    metadata={'spacing': data.z_res, 'unit': 'um'}) # Determine units programmatically

    def finalize(self, finalize_image=FinalizeImage) -> None:
        try:
            self.writer.close()
            self.writer = None
        except Exception as e:
            logger.error(f'{e}')

    def abort(self) -> None:
        self.finalize()