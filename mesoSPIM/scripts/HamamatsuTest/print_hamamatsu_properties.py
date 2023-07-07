import hamamatsu_camera as cam
import ctypes

paraminit = cam.DCAMAPI_INIT(0, 0, 0, 0, None, None)
paraminit.size = ctypes.sizeof(paraminit)
error_code = cam.dcam.dcamapi_init(ctypes.byref(paraminit))
if error_code != cam.DCAMERR_NOERROR:
    raise cam.DCAMException("DCAM initialization failed with error code " + str(error_code))

n_cameras = paraminit.iDeviceCount
print("found:", n_cameras, "cameras")

if n_cameras > 0:
    cam_handle = cam.HamamatsuCameraMR(camera_id=0)
    print("camera 0 model:", cam_handle.getModelInfo(0))
    print("Supported properties:")
    props = cam_handle.getProperties()
    for i, id_name in enumerate(sorted(props.keys())):
        [p_value, p_type] = cam_handle.getPropertyValue(id_name)
        p_rw = cam_handle.getPropertyRW(id_name)
        read_write = ""
        if p_rw[0]:
            read_write += "read"
        if p_rw[1]:
            read_write += ", write"
        print("  ", i, ")", id_name, " = ", p_value, " type is:", p_type, ",", read_write)
        text_values = cam_handle.getPropertyText(id_name)
        if len(text_values) > 0:
            print("          option / value")
            for key in sorted(text_values, key = text_values.get):
                print("         ", key, "/", text_values[key])
