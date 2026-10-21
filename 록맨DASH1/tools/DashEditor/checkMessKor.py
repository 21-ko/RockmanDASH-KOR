import os
import re
from Formats.codes import command_mapping, char_table, commands

def load_text_table(filename):
    text_table = {}
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            hex_val, char = line.strip('\t\n').split('=', 1)
            text_table[char] = bytes.fromhex(hex_val)
    return text_table

def convert_script_to_binary(script, text_table, filename):
    binary_data = []
    block_positions = {}
    offset = 0

    # 블록별로 나누기
    blocks = re.split(r'\[Block', script)
    
    for idx, block in enumerate(blocks[1:], start=1):
        lines = block.strip().splitlines()
        
        try:
            header_match = re.match(r'(\w+), String: ([0-9A-Fa-f]+)-([0-9A-Fa-f]+)', lines[0])
            if not header_match:
                raise ValueError(f"Invalid block header format in file '{filename}', block {hex(idx)}")
            
            block_id = int(header_match.group(1), 16)
            start_pos = int(header_match.group(2), 16)
            end_pos = int(header_match.group(3), 16)
        except IndexError:
            raise ValueError(f"Missing block header in file '{filename}', block {hex(idx)}")
        
        binary_block = b''
        
        for line in lines[1:]:
            components = re.split(r'(<[^>]+>)', line)
            for component in components:
                if component.startswith('<') and component.endswith('>'):
                    command = component[1:-1]
                    cmd_parts = command.split()
                    
                    try:
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
                    except ValueError as e:
                        raise ValueError(f"Error in file '{filename}', block {idx}, command '{command}': {e}")
                else:
                    try:
                        for char in component:
                            if char in text_table:
                                binary_block += text_table[char]
                            else:
                                raise ValueError(f"Character '{char}' not found in text table")
                    except ValueError as e:
                        raise ValueError(f"Error in file '{filename}', block {idx}, line '{line}': {e}")
                            
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
    
# MessKor 폴더 내의 모든 .msg 파일을 처리하는 main 함수
def main():
    # 텍스트 테이블 파일과 MessKor 폴더 경로
    text_table_filename = 'table.tbl'
    folder_path = 'MessKor'

    # 텍스트 테이블 로드
    text_table = load_text_table(text_table_filename)
    
    # MessKor 폴더 내의 모든 .txt 파일 처리
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            msg_file_path = os.path.join(folder_path, filename)
            
            # .txt 파일 열기
            with open(msg_file_path, 'r', encoding='utf-8') as f:
                script = f.read()
            
            # 스크립트를 바이너리로 변환
            try:
                binary_data = convert_script_to_binary(script, text_table, filename)
                #if len(binary_data) > 0x4c00:
                #    print(f"FUCK! {filename} {hex(len(binary_data))}")
                print(f"Processed {filename}: Binary data generated.")
            except ValueError as e:
                print(f"Error processing {filename}: {e}")

# 프로그램 시작
if __name__ == "__main__":
    main()