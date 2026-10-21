import re
from Formats.BIN import bytes_to_uint
from Formats.codes import command_mapping, char_table, commands

HEADER_LEN = 2048

def load_text_table(filename):
    text_table = {}
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            hex_val, char = line.strip('\t\n').split('=', 1)
            text_table[char] = bytes.fromhex(hex_val)
    return text_table

def convert_script_to_binary(script, text_table):
    binary_data = []
    block_positions = {}
    offset = 0

    # 블록별로 나누기
    blocks = re.split(r'\[Block', script)
    
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        
        header_match = re.match(r'(\w+), String: ([0-9A-Fa-f]+)-([0-9A-Fa-f]+)', lines[0])
        if not header_match:
            raise ValueError("Invalid block header format")
        
        block_id = int(header_match.group(1), 16)
        start_pos = int(header_match.group(2), 16)
        end_pos = int(header_match.group(3), 16)
        
        binary_block = b''
        
        for line in lines[1:]:
            components = re.split(r'(<[^>]+>)', line)
            for component in components:
                if component.startswith('<') and component.endswith('>'):
                    # 명령어 처리
                    command = component[1:-1]
                    cmd_parts = command.split()
                    
                    if len(cmd_parts) == 1 and re.fullmatch(r'[0-9A-Fa-f]{4}', cmd_parts[0]):
                        binary_block += bytes.fromhex(cmd_parts[0])[::-1]
                    
                    elif len(cmd_parts) > 1 and re.fullmatch(r'[0-9A-Fa-f]{4}', cmd_parts[0]):
                        binary_block += bytes.fromhex(cmd_parts[0])[::-1]
                        cmd_data = ''.join(cmd_parts[1:])
                        binary_block += bytes.fromhex(cmd_data)
                    
                    else:
                        cmd_name = cmd_parts[0]
                        cmd_data = ''.join(cmd_parts[1:]) if len(cmd_parts) > 1 else ''
                        
                        if cmd_name in command_mapping:
                            binary_block += command_mapping[cmd_name].to_bytes(2, 'little')
                            if cmd_data:
                                binary_block += bytes.fromhex(cmd_data)
                        else:
                            raise ValueError(f"Unknown command format: {command}")
                else:
                    # 일반 문자 처리
                    for char in component:
                        if char in text_table:
                            binary_block += text_table[char]
                        else:
                            raise ValueError(f"Character '{char}' not found in text table.")
                            
        binary_block += b'\x00\x00'
        
        # 블록 시작 위치 기록
        block_positions[block_id] = offset
        offset += len(binary_block)  # 현재 오프셋 업데이트
        
        # 블록 데이터를 리스트에 추가
        binary_data.append(binary_block)

    # 포인터 테이블 block_id순으로 생성
    position_data = b''.join((block_positions[block_id] + len(block_positions) * 2).to_bytes(2, 'little') for block_id in sorted(block_positions))
    
    # 포인터 테이블 붙이기
    binary_data.insert(0, position_data)
    
    return b''.join(binary_data)
    
def do_insert_msg(original_msg, text_file):
    print("\nInserting {}".format(original_msg))
    
    # 테이블 파일 불러오기
    text_table = load_text_table('table.tbl')
    
    # 텍스트 파일 읽기
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()

    # 텍스트를 msg 데이터로 변환
    binary_data = convert_script_to_binary(text, text_table)
    new_size = len(binary_data)
    if new_size % 2048 != 0:
        padding_size = 2048 - (new_size % 2048)
        binary_data += b'\x00' * padding_size
    
    # msg 파일 열기 
    with open(original_msg, "r+b") as msg_file:
        msg_file.seek(4)
        msg_file.write(new_size.to_bytes(4, 'little'))  # 새로운 크기로 기록
        msg_file.write(((len(binary_data) // 2048) + 1).to_bytes(4, 'little'))  # 새로운 크기로 기록
        msg_file.seek(0)
        header_data = msg_file.read(HEADER_LEN)
        
    # msg 파일 새로 쓰기
    with open(original_msg, "wb") as msg_file:
        msg_file.write(header_data)  # 수정된 헤더
        msg_file.write(binary_data)  # 새로운 msg
        
        print("Successfully inserted new msg data into msg file.")

def do_decode_block(block_data, commands):
    decoded_block = ''
    i = 0
    multi_args = 0

    while i < len(block_data):
        b1_0 = block_data[i]
        b1_1 = block_data[i + 1] if i + 1 < len(block_data) else 0
        b1 = (b1_1 << 8) + b1_0

        extra_bytes = [block_data[i + j] if i + j < len(block_data) else None for j in range(2, 18)]
        i += 1

        # 문자 디코딩 시도
        if b1 < 0x0372:
            try:
                decoded_block += char_table[b1]
            except KeyError:
                pass
            i += 1
            continue
            
        def handle_default():
            nonlocal decoded_block, i, multi_args
            decoded_block += '<{:04X}>'.format(b1)

        def handle_simple_command(fmt, extra_byte_count):
            nonlocal decoded_block, i, multi_args
            decoded_block += fmt.format(*extra_bytes[:extra_byte_count])
            i += extra_byte_count

        # 제어 코드 처리
        command_info = commands.get(b1, ('', None))
        if callable(command_info[0]):
            if b1 == 0x0383:
                decoded_block, i, multi_args, should_continue = command_info[0](decoded_block, extra_bytes, b1, i, multi_args)
                if not should_continue:
                    break
            else:
                decoded_block, i, multi_args = command_info[0](decoded_block, extra_bytes, b1, i, multi_args)
        elif command_info[1] is not None:
            handle_simple_command(*command_info)  # 포맷 문자열 처리
        else:
            handle_default()

        i += 1

    return decoded_block


def do_extract_msg(file_path):
    print("\nExtracting {}".format(file_path))
    # msg 파일 열기
    msg_file = open(file_path, "rb").read()
    # 크기 읽기
    file_size = bytes_to_uint(msg_file[4:8])
    # 포인터 테이블 크기 읽기 (첫번째 포인터)
    ptr_tbl_size = bytes_to_uint(msg_file[HEADER_LEN:HEADER_LEN + 2])
    # 포인터 테이블 읽기
    ptr_tbl_data = msg_file[HEADER_LEN:HEADER_LEN + ptr_tbl_size]
    
    num_offsets = ptr_tbl_size // 2
    offset_dict = {}
    
    # 블록 오프셋과 크기 계산
    for i in range(num_offsets):
        offset = int.from_bytes(ptr_tbl_data[i*2:(i*2)+2], byteorder='little') - ptr_tbl_size
        if i < num_offsets - 1:
            next_offset = int.from_bytes(ptr_tbl_data[(i+1)*2:(i+1)*2+2], byteorder='little') - ptr_tbl_size
        else:
            next_offset = (file_size - ptr_tbl_size)  # 파일 끝
            
        size = next_offset - offset
        offset_dict[offset] = size
        #print(hex(offset), hex(size))

    print("Pointer table contains {} blocks".format(int(num_offsets)))
    
    # 블록들 데이터
    blocks_data = msg_file[HEADER_LEN+ptr_tbl_size:HEADER_LEN+file_size]

    output_file = open(file_path + ".txt", "w", encoding="utf-8")

    block_number = 0
    for block_start, block_size in offset_dict.items():
        block_end = block_start + block_size - 2  # 마지막 2바이트는 그냥 \x00\x00
        block_data = blocks_data[block_start:block_end]
        
        output_file.write(
            "[Block {:02X}, String: {:04X}-{:04X}]\n".format(block_number, block_start, block_end + 2)
        )

        output_file.write(do_decode_block(block_data, commands) + "\n\n")
        
        block_number += 1

    output_file.close()
