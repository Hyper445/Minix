from stat import *
import sys
import struct
import binascii

import math

BLOCK_SIZE = 1024


def parse_superblock(sbdata):
    sbdict = {}

    idx = 0
    (sbdict["ninodes"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["nzones"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["imap_blocks"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["zmap_blocks"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["firstdatazone"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["log_zone_size"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["maxfilesize"],) = struct.unpack("<L", sbdata[idx : idx + 4])
    idx += 4
    (sbdict["magic"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbdict["state"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2


    return sbdict


def parse_inodetable(sbdata):

    sbinodeentry = {}
    zonelist = []

    idx = 0
    (sbinodeentry["mode"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbinodeentry["uid"],) = struct.unpack("<H", sbdata[idx : idx + 2])
    idx += 2
    (sbinodeentry["size"],) = struct.unpack("<L", sbdata[idx : idx + 4])
    idx += 4
    (sbinodeentry["time"],) = struct.unpack("<L", sbdata[idx : idx + 4])
    idx += 4
    (sbinodeentry["gid"],) = struct.unpack("<B", sbdata[idx : idx + 1])
    idx += 1
    (sbinodeentry["links"],) = struct.unpack("<B", sbdata[idx : idx + 1])
    idx += 1
    for i in range (9):
        (zone,) = struct.unpack("<H", sbdata[idx : idx + 2])
        zonelist.append(zone)
        sbinodeentry["zone"] = zonelist
        idx += 2

    return sbinodeentry

def get_inode_data(sbdata, f, inodenr):

    # Get sizes of inodemap and zonemap
    INODEMAP_BLOCK_SIZE = sbdict['imap_blocks'] * BLOCK_SIZE
    ZONEMAP_BLOCK_SIZE = sbdict['zmap_blocks'] * BLOCK_SIZE

    # Skip inodemap block and zonemap block
    f.seek(BLOCK_SIZE * 2 + INODEMAP_BLOCK_SIZE + ZONEMAP_BLOCK_SIZE, 0)

    # Store all the inode information in the sbinodetable dictionary
    f.seek(32 * inodenr, 1)
    inodedatafile = f.read(32)
    if (parse_inodetable(sbdata) != None):
        inodedata = parse_inodetable(inodedatafile)

    return inodedata


def get_zone_data(diskimg, inodeinfo, entrysize):

    data = {}

    zoneindex = 0
    zone = inodeinfo['zone'][zoneindex]

    while (zone > 0):

        diskimg.seek(BLOCK_SIZE * zone, 0)

        loopamount = int(inodeinfo['size'] / entrysize)
        if (loopamount > (BLOCK_SIZE / entrysize)): loopamount = int(BLOCK_SIZE / entrysize)

        if (S_ISDIR(inodeinfo['mode'])):
            for i in range(loopamount):

                #Go to the data zone
                datazone = diskimg.read(entrysize)

                idx = 0
                (inode,) = struct.unpack("<H", datazone[idx : idx + 2])
                idx += 2
                (filename,) = struct.unpack(f"<{entrysize - 2}s", datazone[idx : idx + entrysize - 2])

                printname = filename.rstrip(b'\0')
                if (printname == b''): continue
                data[printname] = inode


        if (S_ISREG(inodeinfo['mode'])):
            #Go to the data zone

            size = inodeinfo['size']
            if (inodeinfo['size'] > BLOCK_SIZE): size = BLOCK_SIZE

            datazone = diskimg.read(inodeinfo['size'])

            idx = 0
            (filetext,) = struct.unpack(f"<{size}s", datazone[idx : idx + size])

            printtext = filetext.rstrip(b'\0')
            if (printtext == b''): continue
            data[zone] = printtext


        zoneindex += 1
        zone = inodeinfo['zone'][zoneindex]

    return data


def is_set(x, n):
    return x & 2 ** n != 0 

    # a more bitwise- and performance-friendly version:
    return x & 1 << n != 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mfstool.py image command params")
        sys.exit(0)

    diskimg = sys.argv[1]
    cmd = sys.argv[2]
    if (len(sys.argv) > 3): 
        file = sys.argv[3]
        file_split = file.split("/")    

    with open(diskimg, "rb") as f:

        # Skip boot block
        f.seek(BLOCK_SIZE)
        # Read super block
        sbdata = f.read(BLOCK_SIZE)

        # Save data from superblock in sbdict
        sbdict = parse_superblock(sbdata)

        if (sbdict['magic'] == 4991): entrysize = 16
        else: entrysize = 32

        inodedata = get_inode_data(sbdata, f, 0)
        rootdata = get_zone_data(f, inodedata, entrysize)
        
        # Get the files in the root data
        if (cmd == 'ls'): 
            for i in rootdata:
                sys.stdout.buffer.write(i)
                sys.stdout.buffer.write(b'\n')

        if (cmd == 'cat'):
            directory_data = rootdata
            j = 0

            # Go through the directories to find the file
            for i in range (len(file_split) - 1):

                try:
                    inodenr = directory_data[file_split[i].encode("utf-8")]
                    directory_inode_data = get_inode_data(sbdata, f, inodenr - 1)
                    directory_data = get_zone_data(f, directory_inode_data, 1)
                    j += 1
                except:
                    print("Couldn't find file!")

            # Read the text from the file
            try:
                inodenr = directory_data[file_split[j].encode("utf-8")]
                inode_data = get_inode_data(sbdata, f, inodenr - 1)
                inodezonedata = get_zone_data(f, inode_data, 1)

                for item in inodezonedata:
                    sys.stdout.buffer.write(inodezonedata[item])

            except:
                print("Couldn't find file!")
        
        if (cmd == 'touch'):

            f.seek(BLOCK_SIZE * 2, 0)

            #inode_map_data = f.read(BLOCK_SIZE * sbdict['imap_blocks'])

            free_inode_nr = idx = 0

            #Get the first available inode slot                
            for i in range(sbdict['ninodes']):
                data = f.read(1)
                intdata = int.from_bytes(data, byteorder ='big')

                if (free_inode_nr > 0): break

                for j in range(8):
                    if ((intdata >> j) & 1):
                        idx += 1
                    else:
                        free_inode_nr = idx

            f.seek(BLOCK_SIZE * (2 + sbdict['zmap_blocks']))

            zonenr = 0
            idx = 0
            # Get the first available zone slot
            while(zonenr == 0):
                data = f.read(1)
                intdata = int.from_bytes(data, byteorder ='big')

                for j in range(8):
                    if ((intdata >> j) & 1):
                        idx += 1
                    else:
                        zonenr = idx - 1 + sbdict['firstdatazone']



                print(free_inode_nr)
                print(zonenr)




            for i in range(10):
                data = get_inode_data(sbdata, f, i)
                print(data)



            

