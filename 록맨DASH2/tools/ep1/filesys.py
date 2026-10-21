import os
from pathlib import Path
import sys

def uncompress(file_path, start_offset):

    comp_file = open(file_path, "rb")
    comp_file.seek(start_offset)

    file_type = int.from_bytes(comp_file.read(4), "little") #0
    assert file_type == 3, "ERROR, " + file_path + " " + hex(start_offset) + " IS NOT A COMPRESSED FILE"
    
    uncompressed_size = int.from_bytes(comp_file.read(4), "little") #4
    sectors_to_next = int.from_bytes(comp_file.read(4), "little") #8
    
    clut_x = int.from_bytes(comp_file.read(2), "little") #A
    clut_y = int.from_bytes(comp_file.read(2), "little") #C
    clut_w = int.from_bytes(comp_file.read(2), "little") #E
    clut_h = int.from_bytes(comp_file.read(2), "little") #10
    
    pxl_x = int.from_bytes(comp_file.read(2), "little") #12
    pxl_y = int.from_bytes(comp_file.read(2), "little") #14
    pxl_w = int.from_bytes(comp_file.read(2), "little") #16
    pxl_h = int.from_bytes(comp_file.read(2), "little") #18
    
    comp_file.seek(start_offset + 0x24)
    
    comp_cursor = start_offset + int.from_bytes(comp_file.read(2), "little") + 0x30 #24
    control_cursor = start_offset + 0x30
    
    output_size = 0
    out_buffer = b""
    ref_window_cursor = 0
    end_reached = False
    FFFFs_left = uncompressed_size >> 0xD
    if uncompressed_size & 0x1FFF > 0:
        FFFFs_left += 1

    for n in range((comp_cursor - control_cursor) //4):
        if FFFFs_left == 0:
            break
        comp_file.seek(control_cursor)
        control_block = int.from_bytes(comp_file.read(4), "little")
        control_cursor += 4
        
        for bit_number in reversed(range(32)):
            if FFFFs_left == 0:
                break
            control_bit = control_block & (1 << bit_number)
            
            if control_bit == 0:
                #literal
                comp_file.seek(comp_cursor)
                out_buffer += comp_file.read(2)
                comp_cursor += 2
                output_size += 2
            else:
                #reference
                comp_file.seek(comp_cursor)
                ref_block = int.from_bytes(comp_file.read(2), "little")
                comp_cursor += 2
                if ref_block == 0xFFFF:
                    #Window push
                    ref_window_cursor += 0x2000
                    FFFFs_left -= 1
                    continue

                ref_size   = (ref_block & 0b111) + 2
                ref_offset = (ref_block & 0b1111111111111000) >> 3

                #print("Reference at offset %x, size %x" % (ref_offset, ref_size))

                if ref_offset + ref_size >= 0x2000:
                    #print("Reference overflow!!!")
                    pass

                for x in range(ref_size):
                    ref_start = ref_window_cursor + ref_offset + x*2
                    out_buffer += out_buffer[ref_start:ref_start + 2]
                
                output_size += ref_size*2

    print(hex(uncompressed_size), hex(output_size),  hex(ref_window_cursor), FFFFs_left)

    out_buffer = out_buffer[0:uncompressed_size]
    
    
    return out_buffer
    
def isFilesizeException(src_path, offset):
    src_file = open(src_path, "rb")
    src_file.seek(offset)

    file_type = int.from_bytes(src_file.read(4), "little")

    if file_type == 3:
        return False

    purported_size = int.from_bytes(src_file.read(4), "little")

    total_sectors = int.from_bytes(src_file.read(4), "little")

    min_size = total_sectors*0x800 - 0x7FF
    max_size = total_sectors*0x800
    if purported_size >= min_size and purported_size <= max_size:
        return False
    else:
        print(src_path, hex(offset), "is an exception. Type:", hex(file_type))
        return True
    
def unpack_file(src_path, out_dir):
    dat_file = open(src_path, "rb")
    
    cursor = 0
    
    os.makedirs(out_dir, exist_ok=True)
    
    while cursor < os.stat(src_path).st_size - 0x800:
        dat_file.seek(cursor)
        
        is_filesize_exception = isFilesizeException(src_path, cursor)

        file_type = int.from_bytes(dat_file.read(4), "little")
        file_size = int.from_bytes(dat_file.read(4), "little")
        sectors_to_next = int.from_bytes(dat_file.read(4), "little")
        
        out_stem = Path(src_path).stem + "-{0:#0{1}x}".format(cursor,10) + "-" + str(file_type)
        
        if file_type == 3:
            out_stem += ".uncomp"
        
        out_path = os.path.join(out_dir, out_stem + ".bin")
        out_file = open(out_path, 'wb')
        
        if file_type == 3:
            #print("Uncompressing", out_stem)
            out_file.write(uncompress(src_path, cursor))
        else:
            #print("Exporting", out_stem)
            dat_file.seek(cursor + 0x30)
            if is_filesize_exception:
                out_file.write(dat_file.read((sectors_to_next*0x800)-0x30))
            else:
                out_file.write(dat_file.read(file_size))
        
        out_file.close()
        
        cursor += sectors_to_next*0x800
    
    return

def unpack_all():
    os.makedirs("unpack\\DAT", exist_ok=True)
    
    files = Path("DAT").glob('*.bin')
    for file in files:
        out_folder =  "unpack\\DAT\\"
        unpack_file(file, os.path.join(out_folder, Path(file).stem))
    
    return

unpack_all()