import os
from Formats.MSG import do_decode_block
from Formats.codes import commands

def do_extract_msg_1(file_path, msg_file_offset, msg_file_size, ptr_tbl_size):
    print(f"\nExtracting {file_path}")

    with open(file_path, "rb") as f:
        data_file = f.read()

    # 대사 영역
    data_file_area = data_file[msg_file_offset:msg_file_offset + msg_file_size]

    # 포인터 테이블은 data_file_area의 마지막 ptr_tbl_size 크기만큼의 데이터
    ptr_tbl_data = data_file_area[-ptr_tbl_size:]

    base_offset = msg_file_offset
    num_offsets = ptr_tbl_size // 4

    # 모든 오프셋을 리스트에 수집하고 첫 번째 오프셋 0을 수동으로 추가
    offset_list = [(0, 0)]  # 첫 번째 오프셋 수동 추가
    for i in range(num_offsets):
        offset = int.from_bytes(ptr_tbl_data[i * 4:(i * 4) + 4], byteorder='little') - base_offset
        offset_list.append((i + 1, offset))

    # 마지막 블록의 끝까지 포함하도록 추가
    offset_list.append((num_offsets + 1, msg_file_size - ptr_tbl_size))

    # 오프셋 리스트를 정렬
    sorted_offsets = sorted(offset_list, key=lambda x: x[1])

    # 정렬된 오프셋 리스트로 블록 크기 계산
    offset_dict = {}
    for i in range(len(sorted_offsets) - 1):
        index, offset = sorted_offsets[i]
        next_offset = sorted_offsets[i + 1][1]
        offset_dict[index] = (offset, next_offset - offset)

    print(f"Pointer table contains {num_offsets} blocks")

    # 대사 블록 데이터 영역 가져오기
    blocks_data = data_file_area[:-ptr_tbl_size]  # 포인터 테이블을 제외한 대사 데이터

    # offset_dict를 block_start 순으로 정렬하여 파일에 기록
    output_buffer = []
    for block_number, (block_start, block_size) in sorted(offset_dict.items(), key=lambda x: x[1][0]):
        block_end = block_start + block_size
        block_data = blocks_data[block_start:block_end]

        output_buffer.append(f"[Block {block_number:02X}, String: {block_start:04X}-{block_end:04X}]\n")
        output_buffer.append(do_decode_block(block_data, commands) + "\n\n")

    # data 폴더에 파일 저장
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    output_file_name = os.path.join(output_dir, f"{data_filename}_type1_1_{hex(msg_file_offset)}.txt")
    with open(output_file_name, "w", encoding="utf-8") as output_file:
        output_file.writelines(output_buffer)

    print(f"Extraction completed. Output written to {output_file_name}")

def do_extract_msg_2(file_path, msg_file_offset, msg_file_size, numI):
    print(f"\nExtracting {file_path}")

    with open(file_path, "rb") as f:
        data_file = f.read()
        
    # 대사 영역
    data_file_area = data_file[msg_file_offset:msg_file_offset + msg_file_size]
    
    base_offset = msg_file_offset
    ptrs_dict = {}

    # 버퍼에서 4바이트씩 읽기 (0xffffffff를 찾기)
    idx = 0
    while idx + 4 <= len(data_file_area):
        # 4바이트씩 읽어서 0xffffffff를 찾음
        word = int.from_bytes(data_file_area[idx:idx + 4], byteorder='little')
        
        if word == 0xffffffff:
            # 0xffffffff 뒤로 이동
            idx += 4
            ptr_tbl_start = idx + base_offset

            # 0x00000000을 찾기 위해 계속 읽기
            while idx + 4 <= len(data_file_area):
                word = int.from_bytes(data_file_area[idx:idx + 4], byteorder='little')
                
                if word == 0x00000000:
                    ptr_tbl_end = idx + base_offset

                    # 포인터 테이블의 크기 계산
                    ptr_tbl_size_calculated = ptr_tbl_end - ptr_tbl_start

                    # 포인터 테이블의 시작 위치와 count를 딕셔너리에 저장
                    ptrs_dict[ptr_tbl_start] = ptr_tbl_size_calculated // 4
                    
                    # 포인터 테이블을 발견했으면 루프 종료
                    break
                else:
                    idx += 4
        else:
            idx += 4
            
    print(f"Found {len(ptrs_dict)} pointer tables.")

    # 로그 파일에 포인터 테이블 정보를 기록
    log_file_path = "log.txt"
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"Pointer Tables in {file_path}:\n")
        for ptr_tbl_start, num_offsets in ptrs_dict.items():
            log_file.write(f"  Start: {hex(ptr_tbl_start)}, Size: {num_offsets * 4} bytes ({num_offsets} offsets)\n")
        log_file.write("\n")
    
    print(f"Pointer table details written to {log_file_path}.")

    # 각 포인터 테이블을 개별 파일로 출력
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    
    for ptr_tbl_start, num_offsets in ptrs_dict.items():
        print(f"Processing pointer table starting at {hex(ptr_tbl_start)} with {num_offsets} offsets.")

        offset_dict = {}
        idx = ptr_tbl_start
        for i in range(num_offsets):
            ptr_value = int.from_bytes(data_file[idx:idx + 4], byteorder='little')
            idx += 4

            if i < num_offsets - 1:  # 마지막 포인터가 아니면 다음 포인터와의 차이로 블록 크기를 계산
                next_ptr_value = int.from_bytes(data_file[idx:idx + 4], byteorder='little')
                block_size = next_ptr_value - ptr_value
            else:  # 마지막 포인터인 경우
                block_size = (ptr_tbl_start - 4) - ptr_value - (num_offsets * 4)  # ptr_tbl_start이 데이터의 끝. 그러나 대사 개수만큼 4바이트가 있으므로 그만큼 뺀다

            offset_dict[ptr_value] = block_size

        output_buffer = []
        for block_number, (block_start, block_size) in enumerate(offset_dict.items()):
            block_end = block_start + block_size
            block_data = data_file[block_start:block_end]

            decoded_block = do_decode_block(block_data, commands)

            output_buffer.append(f"[Block {block_number:02X}, String: {block_start:04X}-{block_end:04X}]\n")
            output_buffer.append(decoded_block + "\n\n")

        # 포인터 테이블 시작 위치를 기준으로 파일 이름 생성
        output_file_name = os.path.join(output_dir, f"{data_filename}_type2_{numI}_{hex(ptr_tbl_start)}.txt")
        with open(output_file_name, "w", encoding="utf-8") as output_file:
            output_file.writelines(output_buffer)
        numI += 1

        print(f"Extraction completed. Output written to {output_file_name}")
    return numI
    
def do_extract_msg_3(file_path, msg_file_offset, msg_file_size, ptr_tbl_size, numI=0xff):
    print(f"\nExtracting {file_path}")

    with open(file_path, "rb") as f:
        data_file = f.read()

    # 대사 영역
    data_file_area = data_file[msg_file_offset:msg_file_offset + msg_file_size]
    #print(data_file_area)

    # 포인터 테이블은 data_file_area의 마지막 ptr_tbl_size 크기만큼의 데이터
    ptr_tbl_data = data_file_area[-ptr_tbl_size:]

    base_offset = msg_file_offset
    num_offsets = ptr_tbl_size // 4

    # 모든 오프셋을 리스트에 수집
    offset_list = []
    invalid = 0
    for i in range(num_offsets):
        offset = int.from_bytes(ptr_tbl_data[i * 4:(i * 4) + 4], byteorder='little')
        if offset == 0xffffffff or offset == 0x00000000:
            invalid += 1
            continue
        else:
            offset -= base_offset
            offset_list.append((i, offset))

    # 마지막 블록의 끝까지 포함하도록 추가
    offset_list.append((num_offsets, msg_file_size - ptr_tbl_size - ((num_offsets-2) * 4)))
    
    #print(offset_list, msg_file_offset, num_offsets)

    # 오프셋 리스트를 정렬
    sorted_offsets = sorted(offset_list, key=lambda x: x[1])

    # 정렬된 오프셋 리스트로 블록 크기 계산
    offset_dict = {}
    for i in range(len(sorted_offsets) - 1):
        index, offset = sorted_offsets[i]
        next_offset = sorted_offsets[i + 1][1]
        offset_dict[index] = (offset, next_offset - offset)

    print(f"Pointer table contains {num_offsets} blocks")

    # 대사 블록 데이터 영역 가져오기
    blocks_data = data_file_area[:-ptr_tbl_size]  # 포인터 테이블을 제외한 대사 데이터

    # 결과를 파일로 출력할 버퍼
    output_buffer = []
    for block_number, (block_start, block_size) in sorted(offset_dict.items(), key=lambda x: x[1][0]):
        block_end = block_start + block_size
        block_data = blocks_data[block_start:block_end]

        output_buffer.append(f"[Block {block_number:02X}, String: {block_start:04X}-{block_end:04X}]\n")
        output_buffer.append(do_decode_block(block_data, commands) + "\n\n")

    # data 폴더에 파일 저장
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    output_file_name = os.path.join(output_dir, f"{data_filename}_type3_{numI}_{hex(msg_file_offset)}.txt")
    with open(output_file_name, "w", encoding="utf-8") as output_file:
        output_file.writelines(output_buffer)
    numI += 1

    print(f"Extraction completed. Output written to {output_file_name}")
    return numI


numI = 1
data_file_path = 'data_translated/elf/.data'
data_filename = data_file_path.split('/')[-1]

# 시스템
do_extract_msg_1(data_file_path, msg_file_offset=0xCE38, msg_file_size=0x28C4, ptr_tbl_size=0x3E0)

# 컷신. 총크기: 0xb990
numI = do_extract_msg_2(data_file_path, 0xFC58, 0x58C4, numI)

# 에외
_ = do_extract_msg_1(data_file_path, msg_file_offset=0x12184, msg_file_size=0xfc, ptr_tbl_size=0x10)

# 0x1551C, 0xBC: 0x1C
numI = do_extract_msg_3(data_file_path, msg_file_offset=0x1551C, msg_file_size=0xBC, ptr_tbl_size=0x1C, numI=numI)
# 0x155D8, 0x110: 0x20
numI = do_extract_msg_3(data_file_path, msg_file_offset=0x155D8, msg_file_size=0x110, ptr_tbl_size=0x20, numI=numI)
numI = do_extract_msg_2(data_file_path, 0x156e8, 0x610, numI)
# 0x15Cf8, 0x398: 0x44
numI = do_extract_msg_3(data_file_path, msg_file_offset=0x15Cf8, msg_file_size=0x398, ptr_tbl_size=0x44, numI=numI)
# 0x16090, 0x2C4: 0x38
numI = do_extract_msg_3(data_file_path, msg_file_offset=0x16090, msg_file_size=0x2C4, ptr_tbl_size=0x38, numI=numI)
numI = do_extract_msg_2(data_file_path, 0x16354, 0x29B4, numI)
# 0x18D08, 0x129C: 0x130
numI = do_extract_msg_3(data_file_path, msg_file_offset=0x18D08, msg_file_size=0x129C, ptr_tbl_size=0x130, numI=numI)
numI = do_extract_msg_2(data_file_path, 0x19FA4, 0x1644, numI)