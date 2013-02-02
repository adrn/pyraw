# -*- coding: utf-8 -*-

# System libraries
from argparse import ArgumentParser
from copy import deepcopy
import datetime
import logging
import math
import os
import re
import subprocess
import sys

# Third-party required packages
import numpy as np
import pyfits as pf

def read_pgm(filename, byteorder='>'):
    """ Return image data from a raw PGM file as numpy array.

        Format specification: http://netpbm.sourceforge.net/doc/pgm.html
    """
    with open(filename, 'rb') as f:
        buffer = f.read()
    try:
        header, width, height, maxval = re.search(
            b"(^P5\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n]\s)*)", buffer).groups()
    except AttributeError:
        raise ValueError("Not a raw PGM file: '%s'" % filename)
    return np.frombuffer(buffer,
                            dtype='u1' if int(maxval) < 256 else byteorder+'u2',
                            count=int(width)*int(height),
                            offset=len(header)
                            ).reshape((int(height), int(width)))

def read_raw(filename, interpolate=True):
    """ Read in a raw image file by using dcraw to convert it to a Netpbm .pgm 
        file, and then reading in the data from the 16-bit pgm file. 
        
        Parameters
        ----------
        filename : str
            The filename of the RAW file (NEF, CR2) 
    """
    if not os.path.exists(filename):
        raise IOError("File {} does not exist!".format(filename))
    
    if interpolate:
        # Converting the raw to PPM
        p = subprocess.Popen(["dcraw","-q","1","-f","-v","-a",filename]).communicate()[0]
        
        ppm_filename = os.path.splitext(filename)[0] + ".ppm"
        raw_data = np.array(Image.open(ppm_filename))
        
    else:
        # Converting the raw to PGM
        p = subprocess.Popen(["dcraw","-D","-4",filename]).communicate()[0]
        
        pgm_filename = os.path.splitext(filename)[0] + ".pgm"
        raw_data = read_pgm(pgm_filename)
    
    return raw_data

def raw_to_fits(raw_filename, fits_filename=None, split_channels=False, interpolate=True):
    """ Convert a raw image file (e.g. NEF or CR2) to a FITS file 
    
        .. Note:: Right now, this really only supports RGB cameras, like Nikon D40, D90 etc.
                    or Canon Rebel XT, EOS, etc. 
        
        Parameters
        ----------
        raw_filename : str
            The filename of the RAW file (NEF, CR2) to be converted.
        fits_filename : str, optional
            If 'fits_filename' is specified, the function will save the resultant FITS
            file into the specified filename. Otherwise, it will return an HDUList object.
        split_channels : bool, optional
            If split_channels is True, the FITS file will contain 4 HDUs, one per channel
            from the RAW image. Otherwise, it will return an HDUList with a single HDU
            with the same bayer pattern structure. The bayer pattern is read from the 
            EXIF data.
        interpolate : bool, optional
            If True, will interpolate the colors onto the same grid using dcraw's VNG
            4-color interpolator.
    """
    raw_data = read_raw(raw_filename, interpolate=interpolate)
    
    # Getting the EXIF data with dcraw
    p = subprocess.Popen(["dcraw","-i","-v",raw_filename],stdout=subprocess.PIPE)
    rawheader = p.communicate()[0]

    # Get the Timestamp
    m = re.search('(?<=Timestamp:).*',rawheader)
    date1=m.group(0).split()
    months = { 'Jan' : 1, 'Feb' : 2, 'Mar' : 3, 'Apr' : 4, 'May' : 5, 'Jun' : 6, 'Jul' : 7, 'Aug' : 8, 'Sep' : 9, 'Oct' : 10, 'Nov' : 11, 'Dec' : 12 }
    date = datetime.datetime(int(date1[4]),months[date1[1]],int(date1[2]),int(date1[3].split(':')[0]),int(date1[3].split(':')[1]),int(date1[3].split(':')[2]))
    date ='{0:%Y-%m-%d %H:%M:%S}'.format(date)
    logging.debug("Date: {}".format(date))
    
    # Get the Shutter Speed
    m = re.search('(?<=Shutter:).*(?=sec)',rawheader)
    shutter = m.group(0).strip()
    # Get the Aperture
    m = re.search('(?<=Aperture: f/).*',rawheader)
    aperture = m.group(0).strip()
    logging.debug("Aperture: {}".format(aperture))

    # Get the ISO Speed
    m = re.search('(?<=ISO speed:).*',rawheader)
    iso = m.group(0).strip()
    logging.debug("ISO: {}".format(iso))

    # Get the Focal length
    m = re.search('(?<=Focal length: ).*(?=mm)',rawheader)
    focal = m.group(0).strip()
    logging.debug("Focal Length: {}".format(focal))

    # Get the Original Filename of the cr2
    m = re.search('(?<=Filename:).*',rawheader)
    original_file = m.group(0).strip()
    logging.debug("Original File: {}".format(original_file))
    
    # Get the Camera Type
    m = re.search('(?<=Camera:).*',rawheader)
    camera = m.group(0).strip()
    logging.debug("Camera: {}".format(camera))
    
    # Get the bayer pattern
    m = re.search('(?<=Filter pattern:).*',rawheader)
    bayer_str = m.group(0).strip()[:4]
    bayer_pattern = np.array(list(bayer_str)).reshape((2,2))
    logging.debug("Bayer filter structure: \n{}".format(bayer_pattern))
    
    def _update_header(hdu):
        hdu.header.update('OBSTIME',date)
        hdu.header.update('EXPTIME',shutter)
        hdu.header.update('APERTUR',aperture)
        hdu.header.update('ISO',iso)
        hdu.header.update('FOCAL',focal)
        hdu.header.update('ORIGIN',original_file)
        hdu.header.update('CAMERA',camera)
        hdu.header.update('BAYERPA', bayer_str)
        hdu.header.add_comment('EXPTIME is in seconds.')
        hdu.header.add_comment('APERTUR is the ratio as in f/APERTUR')
        hdu.header.add_comment('FOCAL is in mm')
    
    # Split each filter into its own HDU
    
    if interpolate:
        prim_hdu = pf.PrimaryHDU(raw_data)
        _update_header(prim_hdu)
        hdulist = pf.HDUList(hdus=[prim_hdu])
        
    elif split_channels:
        split_map = np.array([[(0,0),(0,1)],[(1,0),(1,1)]])
        
        a,b = split_map[bayer_pattern == "R"][0]
        R_data = raw_data[a::2, b::2]
        R_hdu = pf.PrimaryHDU(R_data)
        _update_header(R_hdu)
        R_hdu.header.update('FILTER',"R")
        
        a,b = split_map[bayer_pattern == "G"][0]
        G1_data = raw_data[a::2, b::2]
        G1_hdu = pf.ImageHDU(G1_data)
        _update_header(G1_hdu)
        G1_hdu.header.update('FILTER',"G1")
        
        a,b = split_map[bayer_pattern == "G"][1]
        G2_data = raw_data[a::2, b::2]
        G2_hdu = pf.ImageHDU(G2_data)
        _update_header(G2_hdu)
        G2_hdu.header.update('FILTER',"G2")
        
        a,b = split_map[bayer_pattern == "B"][0]
        B_data = raw_data[a::2, b::2]
        B_hdu = pf.ImageHDU(B_data)
        _update_header(B_hdu)
        B_hdu.header.update('FILTER',"B")
        
        hdulist = pf.HDUList(hdus=[R_hdu, G1_hdu, G2_hdu, B_hdu])
    
    # Otherwise, save the whole raw image as the primary HDU of the FITS file
    else:
        hdu = pf.PrimaryHDU(raw_data)
        _update_header(hdu)
        hdu.header.add_comment('BAYERPA is the Bayer filter pattern')
        
        hdulist = pf.HDUList(hdus=[hdu])
    
    if fits_filename != None:
        hdulist.writeto(fits_filename)
    else:
        return hdulist

if __name__ == '__main__':
    parser = ArgumentParser(description="")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False,
                    help="Be chatty (default = False)")
    parser.add_argument("--test", action="store_true", dest="test", default=False,
                    help="Run tests")

    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    if args.test:
        # Run some tests
        test_file1 = "IMG_1204.CR2"
        raw_to_fits(test_file1)
        raw_to_fits(test_file1, split_channels=True)
        raw_to_fits(test_file1, fits_filename=test_file1+".fits")
        raw_to_fits(test_file1, split_channels=True, fits_filename=test_file1+".fits")
