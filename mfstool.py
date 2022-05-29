from stat import *
import sys
import struct
from datetime import datetime
import math

BLOCK_SIZE = 1024


# Returns a dictionary with information about the the superblock
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


# Returns a dictionary with information about the the inodetable
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
    for i in range(9):
        (zone,) = struct.unpack("<H", sbdata[idx : idx + 2])
        zonelist.append(zone)
        sbinodeentry["zone"] = zonelist
        idx += 2

    return sbinodeentry


# Get the data of the specified inode
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


# Extract the data from a specified zone
def get_one_zone_data(diskimg, size):

    # Read the zone data
    datazone = diskimg.read(size)

    idx = 0
    # Determine which part of the zone is important
    if (size == 16 or size == 32):

        idx = 0
        (inode,) = struct.unpack("<H", datazone[idx : idx + 2])
        idx += 2
        (filename,) = struct.unpack(f"<{size - 2}s", datazone[idx : idx + size - 2])

        printname = filename.rstrip(b'\0')
        return printname, inode

    elif (size <= BLOCK_SIZE):
        (filetext,) = struct.unpack(f"<{size}s", datazone[idx : idx + size])

        printtext = filetext.rstrip(b'\0')
        return printtext


# Get the data from multiple zones
def get_zone_data(diskimg, inodeinfo, entrysize):

    data = {}
    zoneindex = 0
    zone = inodeinfo['zone'][zoneindex]

    # If data has been stored in a zone
    while (zone > 0):

        # Move to that zone
        diskimg.seek(BLOCK_SIZE * zone, 0)

        loopamount = int(inodeinfo['size'] / entrysize)
        if (loopamount > (BLOCK_SIZE / entrysize)):
            loopamount = int(BLOCK_SIZE / entrysize)

        # Get the data
        if (S_ISDIR(inodeinfo['mode'])):
            for i in range(loopamount):
                name, inodenr = get_one_zone_data(diskimg, entrysize)
                if (name != b''):
                    data[name] = inodenr

        if (S_ISREG(inodeinfo['mode'])):

            size = inodeinfo['size']
            if (inodeinfo['size'] > BLOCK_SIZE):
                size = BLOCK_SIZE

            text = get_one_zone_data(diskimg, size)
            if (text != b''):
                data[zone] = text

        zoneindex += 1
        zone = inodeinfo['zone'][zoneindex]

    return data


# If a file is in a directory, loop through the directories to
# find the file
def go_to_dir(f, file_split, directory_data, entrysize):

    j = 0
    # Go through the directories to find the file
    for i in range(len(file_split) - 1):
        try:
            # Go to every directory node and parse through their zones with
            # blocks of 'entrysize'
            inodenr = directory_data[file_split[i].encode("utf-8")]
            directory_inode_data = get_inode_data(sbdata, f, inodenr - 1)
            directory_data = get_zone_data(f, directory_inode_data, entrysize)
            j += 1

        except KeyError:
            print("Couldn't find directory!")

    return directory_data


# Find which inode is available
def get_inode_spot(file, skip_size):

    # Move to the inode map
    file.seek(skip_size, 0)
    idx = 0

    # Read (ninodes /  8) bytes untill a bit is found
    # that is set to 0
    for i in range(math.ceil((sbdict['ninodes'] / 8))):
        data = f.read(1)
        intdata = int.from_bytes(data, byteorder='big')

        for j in range(8):
            if ((intdata >> j) & 1):
                idx += 1
            else:
                return idx

    return 0


# Find which zone is available
def get_zone_spot(file, skip_size):

    # Move to the zone map
    file.seek(skip_size, 0)
    zonenr = idx = 0

    # Loop through the bytes untill a 0 bit is found
    while(zonenr == 0):
        data = f.read(1)
        intdata = int.from_bytes(data, byteorder='big')

        for j in range(8):
            if ((intdata >> j) & 1):
                idx += 1
            else:
                return idx - 1

    return 0


# Find where you can put a dictionary entry
def get_free_root_entry(sbdata, file, entrysize):

    inodenr = entry_nr = 0
    file.seek(BLOCK_SIZE * sbdata['firstdatazone'], 0)
    entrydata = file.read(entrysize)
    inodenr = struct.unpack("<H", entrydata[0 : 2])

    while (inodenr != 0):
        entrydata = f.read(entrysize)
        (inodenr,) = struct.unpack("<H", entrydata[0 : 2])
        entry_nr += 1

    return entry_nr


# Make an inode
def make_inode(mode, zonenr, size):

    new_inode = {}
    new_inode['mode'] = mode
    new_inode['uid'] = 0
    new_inode['size'] = size
    new_inode['time'] = int(datetime.now().timestamp())
    new_inode['gid'] = 0
    new_inode['links'] = 1
    new_inode['zone'] = [zonenr, 0, 0, 0, 0, 0, 0, 0, 0]

    return new_inode


# Insert an inode in the inode table
def insert_in_table(file, inode, spot_nr):

    file.seek(BLOCK_SIZE * 4, 0)
    file.seek((spot_nr - 1) * 32, 1)
    for key in inode:
        if (key == "mode" or key == "uid"):
            entry = struct.pack("<H", inode[key])
            file.write(entry)
        if (key == "size" or key == "time"):
            entry = struct.pack("<L", inode[key])
            file.write(entry)
        if (key == "gid" or key == "links"):
            entry = struct.pack("<B", inode[key])
            file.write(entry)

        if (key == "zone"):
            for i in range(len(inode[key])):
                entry = struct.pack("<H", inode[key][i])
                file.write(entry)


# Insert directory entry in the root datazone
def insert_in_zone_directory(file, filename, entrysize, spot_nr, inodenr, zonenr):

    file.seek(BLOCK_SIZE * zonenr, 0)
    file.seek(entrysize * spot_nr, 1)

    print(f"going to zone: {zonenr}")
    print(f"Inserting: {filename} at: {spot_nr}")

    file.write(struct.pack("<H", inodenr))
    file.write(struct.pack(f"<{entrysize - 2}s", filename.encode("utf-8")))


# Update the file of the root inode
def update_root_data(file, sbdict, entrysize):

    file.seek(4 * BLOCK_SIZE, 0)
    file.seek(4, 1)

    size = file.read(4)
    (size,) = struct.unpack("<L", size[0 : 4])
    size += entrysize
    f.seek(-4, 1)
    f.write(struct.pack("<L", size))


# Function that updates which nodes/zones are taken
def update_map(file, skip_size, spotnr):

    spotnr = int(spotnr / 7)

    file.seek(skip_size, 0)

    file.seek(spotnr, 1)
    data = file.read(1)

    intdata = int.from_bytes(data, byteorder='big')
    intdata = intdata * 2 + 1

    file.seek(-1, 1)
    intdata = intdata.to_bytes(1, "big")
    file.write(intdata)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mfstool.py image command params")
        sys.exit(0)

    diskimg = sys.argv[1]
    cmd = sys.argv[2]
    if (len(sys.argv) > 3):
        file = sys.argv[3]
        file_split = file.split("/")

    with open(diskimg, "rb+") as f:

        # Skip boot block
        f.seek(BLOCK_SIZE, 0)
        # Read super block
        sbdata = f.read(BLOCK_SIZE)
        # Save data from superblock in sbdict
        sbdict = parse_superblock(sbdata)

        INODE_MAP = BLOCK_SIZE * 2
        ZONE_MAP = BLOCK_SIZE * (2 + sbdict['imap_blocks'])

        if (sbdict['magic'] == 4991):
            entrysize = 16
        else:
            entrysize = 32

        inodedata = get_inode_data(sbdata, f, 0)
        rootdata = get_zone_data(f, inodedata, entrysize)

        # Get the files in the root data
        if (cmd == 'ls'):
            for i in rootdata:
                sys.stdout.buffer.write(i)
                sys.stdout.buffer.write(b'\n')

        # Print text from a specific file
        if (cmd == 'cat'):

            directory_data = go_to_dir(f, file_split, rootdata, entrysize)
            filename = file_split[len(file_split) - 1]

            # Read the text from the file
            try:
                inodenr = directory_data[filename.encode("utf-8")]
                inode_data = get_inode_data(sbdata, f, inodenr - 1)
                inodezonedata = get_zone_data(f, inode_data, BLOCK_SIZE)

                # Print text
                for item in inodezonedata:
                    sys.stdout.buffer.write(inodezonedata[item])

            except KeyError:
                print("Couldn't find file!")

        # Make a directory or touch
        if (cmd == 'touch' or cmd == 'mkdir' and len(sys.argv) > 3):

            free_inode_nr = get_inode_spot(f, INODE_MAP)
            free_zone_nr = get_zone_spot(f, ZONE_MAP) + sbdict['firstdatazone']

            # Make inode depending on type
            if cmd == 'touch':
                new_inode = make_inode(S_IFREG, 0, 0,)
            elif cmd == 'mkdir':
                new_inode = make_inode(S_IFDIR, free_zone_nr, entrysize * 2)

            root_entry_nr = get_free_root_entry(sbdict, f, entrysize)

            # Update data where needed
            insert_in_table(f, new_inode, free_inode_nr)
            insert_in_zone_directory(f, file_split[0], entrysize, root_entry_nr, free_inode_nr, sbdict['firstdatazone'])
            update_root_data(f, sbdict, entrysize)
            update_map(f, INODE_MAP, free_inode_nr)

            # Insert '.' and '..' in newly made directory
            if (cmd == "mkdir"):
                insert_in_zone_directory(f, ".", entrysize, 0, 1, free_zone_nr)
                insert_in_zone_directory(f, "..", entrysize, 1, free_inode_nr, free_zone_nr)
                update_map(f, ZONE_MAP, free_zone_nr - sbdict["firstdatazone"])

        # Add text to a file
        if (cmd == "append" and len(sys.argv) > 4):
            directory_data = go_to_dir(f, file_split, rootdata, entrysize)
            filename = file_split[len(file_split) - 1]
            appenddata = sys.argv[4]

            # Read the text from the file
            inodenr = directory_data[filename.encode("utf-8")]
            inode_data = get_inode_data(sbdata, f, inodenr - 1)
            inodezonedata = get_zone_data(f, inode_data, BLOCK_SIZE)

            # Go over every zone
            for i in range(7):

                if (inode_data['zone'][i] > 0):
                    f.seek(BLOCK_SIZE * inode_data['zone'][i], 0)

                    # Determine the amount of data can still be written
                    current_data = get_one_zone_data(f, BLOCK_SIZE)
                    free_zone_space = BLOCK_SIZE - len(current_data)
                    f.seek(BLOCK_SIZE * inode_data['zone'][i] + len(current_data), 0)

                elif (inode_data['zone'][i] == 0 and appenddata != ''):

                    free_zone_space = BLOCK_SIZE
                    free_zone_nr = get_zone_spot(f, ZONE_MAP) + sbdict['firstdatazone']
                    f.seek(BLOCK_SIZE * free_zone_nr, 0)

                # Updata the to be written data to fit in the block
                written_data = appenddata
                if not (free_zone_space > len(appenddata)):
                    written_data = appenddata[0 : free_zone_space]
                    appenddata = appenddata[free_zone_space:]
                else:
                    written_data = appenddata
                    appenddata = ''

                f.write(struct.pack(f"<{len(written_data)}s", written_data.encode("utf-8")))

                inode_data['size'] = inode_data['size'] + len(written_data)
                insert_in_table(f, inode_data, inodenr)

                # If the data zone was empty and data has been written to that zone
                if (inode_data['zone'][i] == 0 and len(written_data) > 0):
                    inode_data['zone'][i] = free_zone_nr
                    update_map(f, ZONE_MAP, free_zone_nr - sbdict["firstdatazone"])
