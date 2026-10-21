import struct
import zlib

def apply_patch(original_file: str, patch_file: str, output_file: str):
    try:
        with open(original_file, 'rb') as f:
            original_data = f.read()

        with open(patch_file, 'rb') as f:
            if f.read(4) != b'BPTC':
                raise ValueError("패치 파일의 형식이 올바르지 않습니다.")

            version = struct.unpack('>B', f.read(1))[0]
            if version != 1:
                raise ValueError(f"지원하지 않는 패치 파일 버전입니다: {version}")

            original_size = struct.unpack('>Q', f.read(8))[0]
            new_size = struct.unpack('>Q', f.read(8))[0]

            original_crc = struct.unpack('>I', f.read(4))[0]
            new_crc = struct.unpack('>I', f.read(4))[0]

            if zlib.crc32(original_data) != original_crc:
                raise ValueError("원본 파일의 체크섬이 일치하지 않습니다.")

            delta_size = struct.unpack('>Q', f.read(8))[0]
            compressed_delta = f.read(delta_size)

            delta = zlib.decompress(compressed_delta)
            result = bytearray()
            pos = 0

            while pos < len(delta):
                cmd = delta[pos]
                pos += 1

                if cmd == 0x01:  # COPY
                    offset = struct.unpack('>I', delta[pos:pos + 4])[0]
                    length = struct.unpack('>I', delta[pos + 4:pos + 8])[0]
                    pos += 8
                    result.extend(original_data[offset:offset + length])
                elif cmd == 0x02:  # ADD
                    length = struct.unpack('>I', delta[pos:pos + 4])[0]
                    pos += 4
                    result.extend(delta[pos:pos + length])
                    pos += length
                else:
                    raise ValueError(f"알 수 없는 명령어입니다: {cmd}")

            if zlib.crc32(result) != new_crc:
                raise ValueError("결과 파일의 체크섬이 일치하지 않습니다.")

            with open(output_file, 'wb') as out_f:
                out_f.write(result)

    except ValueError as e:
        raise ValueError(f"패치 적용 중 오류 발생: {str(e)}")
    except Exception as e:
        raise ValueError(f"예상치 못한 오류가 발생했습니다: {str(e)}")