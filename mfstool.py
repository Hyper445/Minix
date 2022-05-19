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
    (sbdict["firstdatazones"],) = struct.unpack("<H", sbdata[idx : idx + 2])
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

    return sbinodeentry


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mfstool.py image command params")
        sys.exit(0)

    diskimg = sys.argv[1]
    cmd = sys.argv[2]

    with open(diskimg, "rb") as f:

        # Skip boot block
        f.seek(BLOCK_SIZE, 0)
        # Read super block
        sbdata = f.read(BLOCK_SIZE)

        # Save data from superblock in sbdict
        sbdict = parse_superblock(sbdata)

        # Move past superblock
        f.seek(BLOCK_SIZE, 1)

        # Get sizes of inodemap and zonemap
        INODEMAP_BLOCK_SIZE = sbdict['imap_blocks'] * BLOCK_SIZE
        ZONEMAP_BLOCK_SIZE = sbdict['zmap_blocks'] * BLOCK_SIZE

        # Skip inodemap block and zonemap block
        f.seek(INODEMAP_BLOCK_SIZE + ZONEMAP_BLOCK_SIZE, 1)

        # Calculate the amount of blocks needed for all the inodes
        INODETABLE_BLOCKS = math.ceil(sbdict['ninodes'] * 32 / BLOCK_SIZE)

        sbdata = f.read(32)

        sbinodetable = {}

        for i in range(sbdict['ninodes']):
            sbinodetable[i] = parse_inodetable(sbdata)
            f.seek(32, 1)
            sbdata = f.read(32)

        for i in range(len(sbinodetable)):
            print(sbinodetable[i])
        #print(sbinodetable)
        print(sbdict)
