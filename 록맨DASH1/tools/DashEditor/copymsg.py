import os
import shutil
import csv
import zlib
import argparse

# 설정
source_folder = 'DAT'  # 원본 폴더 경로
destination_folder = 'Mess'  # 목적지 폴더 경로
log_file = 'copy_log.csv'  # 로그 파일 경로
file_extension = '.msg.txt'  # 확장자


def calculate_crc(file_path):
    """파일의 CRC32 해시를 계산"""
    buffer_size = 65536  # 64KB
    crc = 0
    try:
        with open(file_path, 'rb') as file:
            while chunk := file.read(buffer_size):
                crc = zlib.crc32(chunk, crc)
    except FileNotFoundError:
        return None
    return crc & 0xFFFFFFFF


def load_existing_crcs(log_file):
    """기존 로그에서 Destination Path 파일들의 CRC를 읽어오기"""
    crc_map = {}
    if os.path.exists(log_file):
        with open(log_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                dest_path = row['Destination Path']
                if os.path.exists(dest_path):
                    crc_map[dest_path] = calculate_crc(dest_path)
    return crc_map


def copy_files_with_extension(src_folder, dest_folder, extension, log_file):
    """DAT에서 Mess로 파일 복사 및 중복 방지"""
    # 기존 파일의 CRC 로드
    existing_crcs = load_existing_crcs(log_file)

    # 목적지 폴더가 없으면 생성
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    # CSV 로그 파일 초기화
    if not os.path.exists(log_file):
        with open(log_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Source Path', 'Destination Path', 'Action'])  # 헤더 작성

    # 파일 복사
    with open(log_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.lower().endswith(extension):
                    src_file_path = os.path.join(root, file)
                    dest_file_path = os.path.join(dest_folder, file)

                    # 파일명이 중복되면 숫자 추가
                    base_name, ext = os.path.splitext(file)
                    counter = 1
                    while os.path.exists(dest_file_path):
                        dest_file_path = os.path.join(dest_folder, f"{base_name}_{counter}{ext}")
                        counter += 1

                    # CRC 비교
                    src_crc = calculate_crc(src_file_path)

                    # 기존 Destination Path 파일들 중 동일한 CRC가 있는지 확인
                    duplicate = False
                    for existing_path, existing_crc in existing_crcs.items():
                        if existing_crc == src_crc:
                            duplicate = True
                            writer.writerow([src_file_path, existing_path, 'Skipped (Duplicate Content)'])
                            print(f"중복된 파일 무시: {src_file_path} -> {existing_path}")
                            break

                    if not duplicate:
                        try:
                            shutil.copy(src_file_path, dest_file_path)  # 파일 복사
                            existing_crcs[dest_file_path] = src_crc  # CRC 기록
                            writer.writerow([src_file_path, dest_file_path, 'Copied'])
                            print(f"복사 완료: {src_file_path} -> {dest_file_path}")
                        except Exception as e:
                            print(f"파일 복사 실패: {src_file_path} -> {dest_file_path}, 에러: {e}")


def restore_files_from_csv(input_csv, output_folder):
    """CSV에서 Destination Path 파일을 읽어 Source Path 구조로 복원"""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_csv, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            source_path = row['Source Path']
            destination_path = row['Destination Path']

            # Source Path를 기준으로 out 폴더에 디렉토리 구조 재현
            relative_path = os.path.relpath(source_path, start=os.path.dirname(source_folder))
            out_file_path = os.path.join(output_folder, relative_path)

            # 대상 디렉토리 생성
            os.makedirs(os.path.dirname(out_file_path), exist_ok=True)

            try:
                shutil.copy(destination_path, out_file_path)  # 파일 복사
                print(f"복사 완료: {destination_path} -> {out_file_path}")
            except Exception as e:
                print(f"파일 복사 실패: {destination_path} -> {out_file_path}, 에러: {e}")


def main():
    parser = argparse.ArgumentParser(description="파일 복사 프로그램")
    parser.add_argument('-i', '--input', help="CSV 파일 경로 (복원 모드)")
    args = parser.parse_args()

    if args.input:
        # 복원 모드 실행
        input_csv = args.input
        output_folder = 'out'
        restore_files_from_csv(input_csv, output_folder)
    else:
        # 기본 파일 복사 모드 실행
        copy_files_with_extension(source_folder, destination_folder, file_extension, log_file)


if __name__ == '__main__':
    main()
