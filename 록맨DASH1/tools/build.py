"""록맨 DASH 한글패치 전체 빌드.

  1. EBOOT.BIN  : src/eboot/BOOT.BIN(원본) 확장 → 한글 글꼴/실행파일 대사 삽입 → asm 패치
  2. DAT/*.BIN  : 원본 ISO 의 DAT 를 풀고 → 번역 대사(src/text), 한글 그래픽(src/tim)을 넣고 재패킹
  3. ISO        : 원본 ISO에 파일 교체
  4. 패치 파일   : BPTC 패치 생성 + 검증
  5. 인스톨러    : DashKor.exe (PyInstaller 가 있을 때만)

src/ 의 파일은 건드리지 않고 build/ 에 복사해서 작업한다.
"""
import contextlib
import csv
import os
import runpy
import shutil
import subprocess
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
SRC = os.path.join(ROOT, 'src')
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, '결과물')
ORIGINAL_ISO = os.path.join(ROOT, '원본', 'UMD9660.ISO')
ORIGINAL_CRC = 0x78DFD145
ORIGINAL_SIZE = 0x12E10000
ORIGINAL_BOOT = os.path.join(SRC, 'eboot', 'BOOT.BIN')
ORIGINAL_BOOT_CRC = 0xDC6A3D43

ISO_NAME = '록맨DASH_한글.iso'
PATCH_NAME = 'rockman.patch'

sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, 'eboot'))
from isotool import IsoImage  # noqa: E402
from bptc_make import make_patch  # noqa: E402
from build_eboot import EbootError, build as build_eboot_bin  # noqa: E402
import exetext  # noqa: E402


class BuildError(Exception):
    pass


def step(msg):
    print('\n==== ' + msg)


def crc32_file(path):
    crc = 0
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 20):
            crc = zlib.crc32(chunk, crc)
    return crc


def check_prerequisites():
    step('준비물 확인')
    if not os.path.isfile(ORIGINAL_ISO):
        raise BuildError('원본 ISO가 없습니다: ' + ORIGINAL_ISO)
    if os.path.getsize(ORIGINAL_ISO) != ORIGINAL_SIZE or crc32_file(ORIGINAL_ISO) != ORIGINAL_CRC:
        raise BuildError('원본 ISO의 CRC가 다릅니다 (ULJM05030 원본이 필요합니다)')
    if shutil.which('armips') is None:
        raise BuildError('armips 를 찾을 수 없습니다 (PATH 확인)')
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise BuildError('Pillow 가 필요합니다: pip install pillow')
    print('OK')


def build_eboot():
    """src/eboot/BOOT.BIN(원본 ISO 의 복호화된 실행파일)으로 한글 EBOOT.BIN 을 만든다."""
    step('EBOOT.BIN 빌드')
    with open(ORIGINAL_BOOT, 'rb') as f:
        boot = f.read()
    if zlib.crc32(boot) != ORIGINAL_BOOT_CRC:
        raise BuildError('src/eboot/BOOT.BIN 이 원본과 다릅니다 (원본 ISO 의 PSP_GAME/SYSDIR/BOOT.BIN 이어야 합니다)')
    try:
        return build_eboot_bin(boot, os.path.join(SRC, 'eboot'), os.path.join(BUILD, 'eboot'))
    except (EbootError, exetext.ScriptError, ValueError) as e:
        raise BuildError(str(e))


def run_dash_editor(args_list, cwd, log_path):
    """DashEditor.py 를 한 프로세스 안에서 여러 번 실행한다 (폴더마다 프로세스를 띄우면 느림)."""
    editor = os.path.join(TOOLS, 'DashEditor', 'DashEditor.py')
    if os.path.dirname(editor) not in sys.path:
        sys.path.insert(0, os.path.dirname(editor))
    old_cwd = os.getcwd()
    os.chdir(cwd)
    try:
        with open(log_path, 'a', encoding='utf-8') as log, contextlib.redirect_stdout(log):
            for args in args_list:
                sys.argv = [editor] + args
                runpy.run_path(editor, run_name='__main__')
    except Exception as e:
        raise BuildError('DashEditor 오류: {} (자세한 내용: {})'.format(e, os.path.relpath(log_path, ROOT)))
    finally:
        os.chdir(old_cwd)


def build_dat(table_tbl):
    step('DAT 빌드')
    work = os.path.join(BUILD, 'dat')
    dat = os.path.join(work, 'DAT')
    os.makedirs(dat)
    shutil.copy(table_tbl, os.path.join(work, 'table.tbl'))
    log_path = os.path.join(BUILD, 'dat.log')

    # 바꿀 DAT = 대사가 들어가는 것(msg_map.csv) + 한글 그래픽이 있는 것(src/tim/<DAT 이름>/)
    with open(os.path.join(SRC, 'msg_map.csv'), encoding='utf-8') as f:
        msg_map = [(row['Destination Path'], row['Source Path']) for row in csv.DictReader(f)]
    names = sorted({src.replace('\\', '/').split('/')[1] for _, src in msg_map}
                   | set(os.listdir(os.path.join(SRC, 'tim'))))

    # 원본 ISO 에서 꺼내 DashEditor -e 로 푼다 (DAT/<이름>/ 폴더가 생김)
    iso = IsoImage(ORIGINAL_ISO, writable=False)
    try:
        for name in names:
            with open(os.path.join(dat, name + '.BIN'), 'wb') as f:
                f.write(iso.read('PSP_GAME/USRDIR/DAT/' + name + '.BIN'))
    finally:
        iso.close()
    run_dash_editor([['-e', 'DAT/' + name + '.BIN'] for name in names], work, log_path)
    for name in names:
        os.remove(os.path.join(dat, name + '.BIN'))  # -i 는 BIN 이 이미 있으면 거부한다

    # 한글 그래픽과 번역 대사를 덮어쓴다 (같은 대사를 여러 DAT 에 쓰는 것은 msg_map.csv 대로)
    shutil.copytree(os.path.join(SRC, 'tim'), dat, dirs_exist_ok=True)
    for text, target in msg_map:
        shutil.copy(os.path.join(SRC, 'text', os.path.basename(text.replace('\\', '/'))),
                    os.path.join(work, target.replace('\\', '/')))

    run_dash_editor([['-i', 'DAT/' + name] for name in names], work, log_path)
    missing = [n for n in names if not os.path.isfile(os.path.join(dat, n + '.BIN'))]
    if missing:
        raise BuildError('BIN 생성 실패: {} (build/dat.log 확인)'.format(', '.join(missing)))
    print('{}개 BIN 생성'.format(len(names)))
    return {n + '.BIN': os.path.join(dat, n + '.BIN') for n in names}


def build_iso(eboot, dat_bins):
    step('ISO 빌드')
    iso_path = os.path.join(OUT, ISO_NAME)
    shutil.copyfile(ORIGINAL_ISO, iso_path)  # 원본의 읽기 전용 속성은 복사하지 않음

    def read(path):
        with open(path, 'rb') as f:
            return f.read()

    iso = IsoImage(iso_path)
    try:
        iso.replace('PSP_GAME/PARAM.SFO', read(os.path.join(SRC, 'iso', 'PARAM.SFO')))
        iso.replace('PSP_GAME/PIC0.PNG', read(os.path.join(SRC, 'iso', 'PIC0.PNG')))
        # 복호화된 EBOOT.BIN 이 실행되도록 BOOT.BIN 은 0으로 채운다
        iso.replace('PSP_GAME/SYSDIR/BOOT.BIN', bytes(len(iso.read('PSP_GAME/SYSDIR/BOOT.BIN'))))
        for name, path in dat_bins.items():
            iso.replace('PSP_GAME/USRDIR/DAT/' + name, read(path))
        iso.replace('PSP_GAME/SYSDIR/EBOOT.BIN', read(eboot))
    finally:
        iso.close()
    print(ISO_NAME)

    return iso_path


def build_patch(iso_path):
    step('패치 파일 생성')
    sys.path.insert(0, os.path.join(ROOT, 'installer'))
    from bptc import apply_patch

    patch = os.path.join(OUT, PATCH_NAME)
    make_patch(ORIGINAL_ISO, iso_path, patch)
    # 인스톨러와 같은 코드로 적용해서 결과가 같은지 확인
    check = os.path.join(BUILD, 'patch_check.iso')
    apply_patch(ORIGINAL_ISO, patch, check)
    if crc32_file(check) != crc32_file(iso_path):
        raise BuildError(PATCH_NAME + ' 검증 실패')
    os.remove(check)
    print('{} ({:,} bytes, 검증 OK)'.format(PATCH_NAME, os.path.getsize(patch)))
    return patch


def build_installer(patch):
    step('인스톨러 빌드')
    if subprocess.run([sys.executable, '-m', 'PyInstaller', '--version'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print('PyInstaller 가 없어서 건너뜁니다. (설치: pip install pyinstaller pyqt5)')
        return

    work = os.path.join(BUILD, 'installer')
    shutil.copytree(os.path.join(ROOT, 'installer'), work,
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(patch, os.path.join(work, 'assets'))

    # PyArmor 가 있으면 구 Xx.bat 처럼 난독화한 코드로 빌드한다
    entry = 'DashKor.py'
    if shutil.which('pyarmor'):
        res = subprocess.run(['pyarmor', 'gen', '-O', 'obf', 'DashKor.py', 'bptc.py'], cwd=work)
        if res.returncode != 0:
            raise BuildError('PyArmor 난독화 실패')
        entry = os.path.join('obf', 'DashKor.py')
    else:
        print('PyArmor 가 없어서 난독화 없이 빌드합니다.')

    cmd = [sys.executable, '-m', 'PyInstaller', '--onefile', '--noconfirm', '--noconsole',
           '--hidden-import=bptc',
           '--hidden-import=PyQt5.QtWidgets',
           '--hidden-import=PyQt5.QtGui',
           '--hidden-import=PyQt5.QtCore',
           '--add-data', os.path.join(work, 'assets') + os.pathsep + 'assets',
           '--icon', os.path.join(work, 'assets', 'Dash.ico'),
           '--distpath', OUT,
           '--workpath', os.path.join(work, 'pyi'),
           '--specpath', work]
    if os.path.isdir(r'C:\user_prog\bin'):
        cmd.append(r'--upx-dir=C:\user_prog\bin')
    cmd.append(entry)
    if subprocess.run(cmd, cwd=work).returncode != 0:
        raise BuildError('PyInstaller 실패')
    print('DashKor.exe')


def main():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD)
    os.makedirs(OUT, exist_ok=True)

    check_prerequisites()
    eboot, table_tbl = build_eboot()
    dat_bins = build_dat(table_tbl)
    iso_path = build_iso(eboot, dat_bins)
    patch = build_patch(iso_path)
    build_installer(patch)

    step('완료 → ' + OUT)


if __name__ == '__main__':
    try:
        main()
    except BuildError as e:
        print('\n[실패] ' + str(e))
        sys.exit(1)
