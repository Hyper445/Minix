from stat import *
import sys
import struct

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
    for i in range (8):
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

        for i in range(loopamount):

            #Go to the data zone
            datazone = diskimg.read(entrysize)

            if (S_ISDIR(inodeinfo['mode'])):
                idx = 0
                (inode,) = struct.unpack("<H", datazone[idx : idx + 2])
                idx += 2
                (filename,) = struct.unpack(f"<{entrysize - 2}s", datazone[idx : idx + entrysize - 2])

                printname = filename.rstrip(b'\0')
                if (printname == b''): continue
                data[printname] = inode

            if (S_ISREG(inodeinfo['mode'])):
                idx = 0
                (filetext,) = struct.unpack(f"<{entrysize}s", datazone[idx : idx + entrysize])

                printtext = filetext.rstrip(b'\0')
                if (printtext == b''): continue
                data[printtext] = i


        zoneindex += 1
        zone = inodeinfo['zone'][zoneindex]

    return data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mfstool.py image command params")
        sys.exit(0)

    diskimg = sys.argv[1]
    cmd = sys.argv[2]
    if (len(sys.argv) > 3): file = sys.argv[3]

    with open(diskimg, "rb") as f:

        # Skip boot block
        f.seek(BLOCK_SIZE)
        # Read super block
        sbdata = f.read(BLOCK_SIZE)

        # Save data from superblock in sbdict
        sbdict = parse_superblock(sbdata)

        if (sbdict['magic'] == 4991): entrysize = 16
        else: entrysize = 32

        # Calculate the amount of blocks needed for all the inodes
        # INODETABLE_BLOCKS = math.ceil(sbdict['ninodes'] * 32 / BLOCK_SIZE)

        inodedata = get_inode_data(sbdata, f, 0)
        rootdata = get_zone_data(f, inodedata, entrysize)

        # Get the files in the root data
        if (cmd == 'ls'): 
            print("\n\n")
            for i in rootdata:
                sys.stdout.buffer.write(i)
                sys.stdout.buffer.write(b'\n')       

        if (cmd == 'cat'):
            inodenr = rootdata[file.encode("utf-8")]
            inodedata = get_inode_data(sbdata, f, inodenr)
            inodezonedata = get_zone_data(f, inodedata, BLOCK_SIZE)
            for i in inodezonedata:
                print(i)
                # sys.stdout.buffer.write(i)
                # sys.stdout.buffer.write(b'\n')      
        
        
        
        
        
        
        
        
        
        
        # #### LOOKING FOR DATAZONE FOR INODE ####
        # f.seek(BLOCK_SIZE * 2, 0)

        # sbdata = f.read(INODEMAP_BLOCK_SIZE)

        # inodemapdict = {}
        # idx = 0
        # while (idx != INODEMAP_BLOCK_SIZE):

        #     (inode,) = struct.unpack("<b", sbdata[idx : idx + 1])
        #     idx += 1
        #     (available,) = struct.unpack("<b", sbdata[idx : idx + 1])
        #     inodemapdict[inode] = available
        #     idx += 1