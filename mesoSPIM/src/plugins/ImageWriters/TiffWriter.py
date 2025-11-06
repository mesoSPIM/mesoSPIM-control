import os
import time
import numpy as np
import tifffile
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import Writer, WriterCapabilities, WriteRequest, API_VERSION

print(f"{'TIFFWRITER__'*10}")

class TiffWriter(Writer):
    '''Write Images as Tiff Files'''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'TiffWriter'

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
        return ['tif', 'tiff']

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), 'URI suffix not compatible with TiffWriter'
        self.write_request = req
        self.writer = tifffile.TiffWriter(self.write_request.uri, bigtiff=True)

    def write_frame(self, image: memoryview | Any) -> None:
        self.writer.write(image[np.newaxis, ...], contiguous=True, resolution=self.write_request.x_res,
                       metadata={'spacing': self.write_request.z_res, 'unit': 'um'}) # Determine units programmatically

    def finalize(self) -> None:
        try:
            self.writer.close()
            self.writer = None
        except Exception as e:
            logger.error(f'{e}')

    def abort(self) -> None:
        self.finalize()