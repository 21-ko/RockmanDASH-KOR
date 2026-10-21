def handle_sel_command(decoded_block, extra_bytes, b1, i, multi_args):
    multi_args += 1
    command = 'SEL' if b1 == 0x0384 else f'{b1:04X}'
    decoded_block += '<{:s} {:02X}{:02X}{:02X}{:02X}>'.format(command, *extra_bytes[:4])
    i += 4
    return decoded_block, i, multi_args

def handle_multi_command(decoded_block, extra_bytes, b1, i, multi_args):
    multi_args += 1 if multi_args % 2 == 0 else 0
    byte_count = 1 + multi_args
    formatted_bytes = ''.join('{:02X}'.format(b) for b in extra_bytes[:byte_count] if b is not None)
    decoded_block += f'<{b1:04X} {formatted_bytes}>\n'
    i += byte_count
    return decoded_block, i, multi_args
    
def handle_0383(decoded_block, extra_bytes, b1, i, multi_args):
    decoded_block += '<0383>'
    if extra_bytes[0] == 0 and extra_bytes[1] == 0 and extra_bytes[2] is None:
        return decoded_block, i, multi_args, False  # 디코딩을 멈추기
    return decoded_block, i, multi_args, True  # 계속 진행