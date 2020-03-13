'''
Classes to create XMLs for Bigstitcher out of mesoSPIM-Datasets.
'''
import os.path

from ..mesoSPIM_State import mesoSPIM_StateSingleton

from lxml import etree

class mesoSPIM_XMLexporter:
    '''
    Class to take a mesoSPIM acquisitionlist object and turn it into a Bigdataviewer/
    Bigstitcher XML file.

    TODO:
    * a single stack goes into a single view setup
    * everything has to be converted to string...
    * have the correct image loader: tif
    * <size>399 494 1256</size>
    * if the coordinates match and the channels (laser or filter) are different: same tile, but different channels 
    * angle can be taken directly from acqlist
    * every acq is a viewSetup 
    * acqs with matching X,Y,and Z_start, Z_end and angle positions positions are the same tile
        * create a tile list?
    * assign channels by order of appearance
        * different lasers are definitely different channels 
        * same lasers: check if filters are different --> if yes then channels 
        * case: 
    * angles not supported
    '''

    def __init__(self, parent=None):
        self.parent = parent
        self.state = mesoSPIM_StateSingleton()
        self.cfg = parent.cfg

        self.xmlwriter = mesoSPIM_BDVXMLwriter()

        self.xy_pixelsize = 1
        self.z_size = 1
        self.length_unit = 'micron'

    def generate_xml_from_acqlist(self, acqlist, path):
        channeldict = self.generate_channeldict(acqlist)
        tiledict = self.generate_tiledict(acqlist)
        illuminationdict = self.generate_illuminationdict(acqlist)

        num_channels = len(channeldict)
        num_tiles = len(tiledict)
        num_illuminations = len(illuminationdict)

        if num_channels > 1:
            layout_channels = 1
        else:
            layout_channels = 0 
        
        if num_tiles > 1:
            layout_tiles = 1
        else:
            layout_tiles = 0

        if num_illuminations > 1:
            layout_illuminations = 1
        else:
            layout_illuminations = 0

        channellist = [c for c in range(num_channels)]
        illuminationlist = [i for i in range(num_illuminations)]
        tilelist = [t for t in range(num_tiles)]
        anglelist = [0]

        self.xmlwriter.setLayout(filepattern='tiling_file_t{x}_c{c}.raw.tif',
                                timepoints=0,
                                channels=layout_channels,
                                illuminations=layout_illuminations,
                                angles = 0,
                                tiles = layout_tiles,
                                imglibcontainer="ArrayImgFactory") #or CellImgFactory
                                
        id = 0
        for acq in acqlist:
            channelstring = self.generate_channelstring(acq)
            illuminationstring = self.generate_illuminationstring(acq)
            tilestring = self.generate_tilestring(acq)
            calibrationstring = self.create_calibration_string(acq)
            
            self.xmlwriter.addviewsetup(id=str(id), 
                                        name=str(acq['filename']),
                                        size=self.create_size_string(acq),
                                        vosize_unit = 'micron',
                                        vosize = self.create_voxelsize_string(acq),
                                        illumination = illuminationdict[illuminationstring],
                                        channel = channeldict[channelstring],
                                        tile = tiledict[tilestring],
                                        angle = self.create_angle_string(acq))

            self.xmlwriter.addCalibrationRegistration(tp='0', view=str(id), calibrationstring=calibrationstring)
            id += 1
        
        self.xmlwriter.addAttributes(illuminations=illuminationlist,
                                    channels=channellist,
                                    tiles=tilelist,
                                    angles=anglelist)

        self.xmlwriter.addTimepoints('')
            
        self.xmlwriter.write(path)

    def generate_channeldict(self, acqlist):
        '''
        Takes the acqlist and returns a dictionary of channels 
        Channels are defined as:
        * different lasers in different acqs are definitely different channels 
        * same lasers: check if filters are different --> if yes then channels 
        '''
        channeldict = {}
        c = 0

        for acq in acqlist:
            channelstring = self.generate_channelstring(acq)
            if not channelstring in channeldict:
                channeldict.update({channelstring:str(c)})
                c+=1

        return channeldict
        

    def generate_tiledict(self, acqlist):
        '''
        Takes the acqlist and returns an assignment of 

        Idea: Take an ACQ and create a hash/hashable datatype (e.g. string)
        out of:
            * X_pos
            * Y_pos 
            * Z_start
            * Z_end
            * Angle

        Use this tilehash as keys for a dictionary 
        Later on, you can use it to assign tiles
        '''
        tiledict = {}
        t=0

        for acq in acqlist:
            tilestring = self.generate_tilestring(acq)
            if not tilestring in tiledict:
                tiledict.update({tilestring:str(t)})
                t+=1

        return tiledict

    def generate_illuminationdict(self, acqlist):
        illuminationdict = {}
        i = 0

        for acq in acqlist:
            illuminationstring = self.generate_illuminationstring(acq)
            if not illuminationstring in illuminationdict:
                illuminationdict.update({illuminationstring: str(i)})
                i+=1

        return illuminationdict            

    def generate_channelstring(self, acq):
        return str(acq['laser']) + ' ' + str(acq['filter'])

    def generate_tilestring(self, acq):
        return str(acq['x_pos'])+' '+str(acq['y_pos'])+' '+str(acq['z_start'])+' '+str(acq['rot'])

    def generate_illuminationstring(self, acq):
        return str(acq['shutterconfig'])
    
    def write(self, path):
        self.xmlwriter.write(path)

    def create_size_string(self, acq):
        ''' Creates the necessary XYZ #pixels string'''

        binning_string = self.cfg.camera_parameters['binning']
        x_binning = int(binning_string[0])
        y_binning = int(binning_string[2])

        y_pixels = int(self.cfg.camera_parameters['y_pixels'] / y_binning)
        x_pixels = int(self.cfg.camera_parameters['x_pixels'] / x_binning)

        z_pixels = acq['planes']

        ''' X and Y flipped due to image rotation '''
        return str(y_pixels) + ' ' + str(x_pixels) + ' ' + str(z_pixels)

    def update_pixelsizes(self, acq):
        self.xy_pixelsize = self.convert_zoom_to_pixelsize(acq['zoom'])
        self.z_pixelsize = acq['z_step']

    def create_voxelsize_string(self, acq):
        ''' Assumes square pixels'''
        self.update_pixelsizes(acq)
        return str(self.xy_pixelsize) + ' ' + str(self.xy_pixelsize) + ' ' + str(self.z_pixelsize)

    def convert_zoom_to_pixelsize(self, zoom):
        ''' Don't forget the binning!'''
        return self.cfg.pixelsize[zoom]

    def create_angle_string(self, acq):
        return str(int(acq['rot']))

    def create_calibration_string(self, acq):
        '''
        XY pixelsize: 15
        Z:pixelsize: 8
        15/8 = 1.875

        Result:
        1.875 0.0 0.0 0.0 0.0 1.875 0.0 0.0 0.0 0.0 1.0 0.0

        if 
        XY pixelsize: 8
        Z:pixelsize: 15
        15/8 = 1.875

        Result:
        1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 1.875 0.0
        '''
        self.update_pixelsizes(acq)

        if self.xy_pixelsize > self.z_pixelsize:
            factor = self.xy_pixelsize/self.z_pixelsize
            calibration_string = str(factor) + ' 0.0 0.0 0.0 0.0 ' + str(factor) + ' 0.0 0.0 0.0 0.0 1.0 0.0'
        elif self.xy_pixelsize < self.z_pixelsize:
            factor = self.z_pixelsize/self.xy_pixelsize
            calibration_string = '1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 '+ str(factor) +' 0.0'
        else:
            calibration_string = '1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 1.0 0.0'

        return calibration_string

class mesoSPIM_BDVXMLwriter:
    '''
    mesoSPIM bigdataviewer-XML-writer
    
    Based on the code posted by https://github.com/Xqua here: 
    https://github.com/bigdataviewer/bigdataviewer-core/issues/5
    '''
    
    def __init__(self):
        
        self.xml = etree.Element('SpimData', version="0.2")
        self.doc = etree.ElementTree(self.xml)

        self.BasePath = etree.SubElement(self.xml, 'BasePath', type="relative")
        self.BasePath.text = "."

        self.SequenceDescription = etree.SubElement(self.xml, 'SequenceDescription')
        self.ImageLoader = etree.SubElement(self.SequenceDescription, 'ImageLoader', format="spimreconstruction.stack.ij")
        
        self.ImageDirectory = etree.SubElement(self.ImageLoader, 'imagedirectory', type="relative")
        


        self.ViewSetups = etree.SubElement(self.SequenceDescription, 'ViewSetups')
        self.ViewRegistrations = etree.SubElement(self.xml, 'ViewRegistrations')

        etree.SubElement(self.xml, "ViewInterestPoints")
        etree.SubElement(self.xml, "BoundingBoxes")
        etree.SubElement(self.xml, "PointSpreadFunctions")
        etree.SubElement(self.xml, "StitchingResults")
        etree.SubElement(self.xml, "IntensityAdjustments")

    def write(self, path):
        out = str(etree.tostring(self.xml, pretty_print=True, encoding=str))
        # out = str(etree.tostring(self.xml, pretty_print=True, encoding='UTF-8'))
        
        
        with open(path, 'w') as file:
            file.write(out)
        
    def addFile(self, path):
        image = etree.SubElement(self.ImageLoader, 'hdf5', type="relative")
        image.text = path

    def addviewsetup(self, id, name, size, vosize_unit, vosize, illumination, channel, tile, angle):
        V = etree.SubElement(self.ViewSetups, 'ViewSetup')

        Id =  etree.SubElement(V, 'id')
        Id.text = str(id)
        Name =  etree.SubElement(V, 'name')
        Name.text = str(name)
        Size =  etree.SubElement(V, 'size')
        Size.text = str(size)

        VoxelSize =  etree.SubElement(V, 'voxelSize')
        Unit =  etree.SubElement(VoxelSize, 'unit')
        Unit.text = str(vosize_unit)
        Size =  etree.SubElement(VoxelSize, 'size')
        Size.text = str(vosize)

        Attributes =  etree.SubElement(V, 'attributes')
        Ilum =  etree.SubElement(Attributes, 'illumination')
        Ilum.text = str(illumination)
        Chan =  etree.SubElement(Attributes, 'channel')
        Chan.text = str(channel)
        Tile =  etree.SubElement(Attributes, 'tile')
        Tile.text = str(tile)
        Ang =  etree.SubElement(Attributes, 'angle')
        Ang.text = str(angle)

    def setLayout(self, filepattern="tiling_file_{x}_c{c}.raw.tif", timepoints=0, channels=0, illuminations=0, angles=0, tiles=1,imglibcontainer="ArrayImgFactory"):
        '''
        Layout entries according to: 
        https://scijava.org/javadoc.scijava.org/Fiji/spim/fiji/spimdata/imgloaders/LegacyStackImgLoader.html

        layoutTP - - 0 == one, 1 == one per file, 2 == all in one file
        layoutChannels - - 0 == one, 1 == one per file, 2 == all in one file
        layoutIllum - - 0 == one, 1 == one per file, 2 == all in one file
        layoutAngles - - 0 == one, 1 == one per file, 2 == all in one file
        '''
        self.FilePattern = etree.SubElement(self.ImageLoader,'filePattern')
        self.FilePattern.text = filepattern
        self.LayoutTimepoints = etree.SubElement(self.ImageLoader, 'layoutTimepoints')
        self.LayoutTimepoints.text = str(timepoints)
        self.LayoutChannels = etree.SubElement(self.ImageLoader, 'layoutChannels')
        self.LayoutChannels.text = str(channels)
        self.LayoutIlluminations = etree.SubElement(self.ImageLoader, 'layoutIlluminations')
        self.LayoutIlluminations.text = str(illuminations)
        self.LayoutAngles = etree.SubElement(self.ImageLoader, 'layoutAngles')
        self.LayoutAngles.text = str(angles)
        self.LayoutTiles = etree.SubElement(self.ImageLoader, 'layoutTiles')
        self.LayoutTiles.text = str(tiles)

        self.Imglib2container = etree.SubElement(self.ImageLoader, 'imglib2container')
        self.Imglib2container.text = imglibcontainer

    def setViewSize(self, Id, size):
        trigger = False
        for child in self.ViewSetups:
            for el in child:
                if el.tag == 'id':
                    if el.text == Id:
                        trigger = True
                if el.tag == 'size' and trigger:
                    el.text = ' '.join(size)
                    trigger = False
                    return True
        return False

    def addAttributes(self, illuminations, channels, tiles, angles):
        illum = etree.SubElement(self.ViewSetups, 'Attributes', name="illumination")
        chan = etree.SubElement(self.ViewSetups, 'Attributes', name="channel")
        til = etree.SubElement(self.ViewSetups, 'Attributes', name="tile")
        ang = etree.SubElement(self.ViewSetups, 'Attributes', name="angle")

        for illumination in illuminations:
            I = etree.SubElement(illum, 'Illumination')
            Id = etree.SubElement(I, 'id')
            Id.text = str(illumination)
            Name = etree.SubElement(I, 'name')
            Name.text = str(illumination)

        for channel in channels:
            I = etree.SubElement(chan, 'Channel')
            Id = etree.SubElement(I, 'id')
            Id.text = str(channel)
            Name = etree.SubElement(I, 'name')
            Name.text = str(channel)

        for tile in tiles:
            I = etree.SubElement(til, 'Tile')
            Id = etree.SubElement(I, 'id')
            Id.text = str(tile)
            Name = etree.SubElement(I, 'name')
            Name.text = str(tile)

        for angle in angles:
            I = etree.SubElement(ang, 'Angle')
            Id = etree.SubElement(I, 'id')
            Id.text = str(angle)
            Name = etree.SubElement(I, 'name')
            Name.text = str(angle)

    def addTimepoints(self, timepoints):
        TP = etree.SubElement(self.SequenceDescription, 'Timepoints', type="pattern")
        I = etree.SubElement(TP, 'integerpattern')
        I.text = ', '.join(timepoints)

    def addRegistration(self, tp, view):
        V = etree.SubElement(self.ViewRegistrations, 'ViewRegistration', timepoint=tp, setup=view)
        VT = etree.SubElement(V, 'ViewTransform', type="affine")
        name = etree.SubElement(VT, 'Name')
        name.text = "calibration"
        affine = etree.SubElement(VT, 'affine')
        affine.text = '1.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.0 1.0 0.0'

    def addCalibrationRegistration(self, tp, view, calibrationstring):
        V = etree.SubElement(self.ViewRegistrations, 'ViewRegistration', timepoint=str(tp), setup=str(view))
        VT = etree.SubElement(V, 'ViewTransform', type="affine")
        name = etree.SubElement(VT, 'Name')
        name.text = "calibration"
        affine = etree.SubElement(VT, 'affine')
        affine.text = calibrationstring