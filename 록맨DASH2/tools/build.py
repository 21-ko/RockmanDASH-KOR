"""록맨 DASH2 한글패치 전체 빌드.

  1. 실행파일   : 원본 EP2 BOOT.BIN, EP1 dash2e1.prx 확장 → 폰트, 실행파일 내 대사, asm 패치
  2. EP2 DAT    : 원본 BIN 분할 → 대사 삽입 → 텍스처 삽입 → 결합 (USRDIR/DAT, COMMON)
  3. EP1 DAT    : 대사 삽입, 텍스처 삽입, 폰트(INIT.BIN) (USRDIR/E1/DAT)
  4. ISO        : 원본 ISO 에 파일 교체, 옮겨진 파일은 EBOOT 의 LBA 테이블에 반영
  5. 패치 파일   : BPTC 패치 생성 + 검증
  6. 인스톨러    : Dash2Kor.exe (PyInstaller 가 있을 때만)

src/ 의 파일은 건드리지 않고 build/ 에 복사해서 작업한다.
"""
import os
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
SRC = os.path.join(ROOT, 'src')
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, '결과물')
ORIGINAL_ISO = os.path.join(ROOT, '원본', 'UMD9660.ISO')
ORIGINAL_CRC = 0x40F10DE6
ORIGINAL_SIZE = 0x14D50000
ISO_NAME = '록맨DASH2_한글.iso'

# 원본 실행파일 (복호화된 PRX, 수정하지 않음)
ORIGINAL_EBOOT = os.path.join(SRC, 'ep2', 'exe', 'BOOT.BIN')
ORIGINAL_EBOOT_CRC = 0xC9C679DE
ORIGINAL_PRX = os.path.join(SRC, 'ep1', 'exe', 'dash2e1.prx')
ORIGINAL_PRX_CRC = 0x8C006495

# 실행파일 안의 파일 LBA/크기 테이블 (0, LBA, 크기 12바이트씩) 의 .data 안 위치와 개수.
# 확장한 실행파일이라 원래 .data 자리에 옛 사본이 남아 있는데, 실행 시 매핑되는 쪽을 고친다.
EBOOT_TABLE = (0x590, 909)
PRX_TABLE = (0x85C, 854)

sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, 'exe'))
from isotool import IsoImage  # noqa: E402
from bptc_make import make_patch  # noqa: E402
import build_exe  # noqa: E402


class BuildError(Exception):
    pass


def step(msg):
    print('\n==== ' + msg)


def run(cmd, cwd, name=None):
    """명령 실행. 출력은 build/logs 에 남기고 실패하면 끝부분을 보여준다."""
    name = name or os.path.basename(cmd[1] if cmd[0] == sys.executable else cmd[0])
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    res = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = res.stdout.decode('utf-8', 'replace')
    os.makedirs(os.path.join(BUILD, 'logs'), exist_ok=True)
    with open(os.path.join(BUILD, 'logs', name + '.log'), 'a', encoding='utf-8') as f:
        f.write(out)
    if res.returncode != 0:
        print(out[-2000:])
        raise BuildError('{} 실패 (build/logs/{}.log)'.format(name, name))
    return out


def py(script, *args, cwd):
    return run([sys.executable, script] + list(args), cwd, os.path.basename(script))


def copy_files(src_dir, dst_dir, names):
    os.makedirs(dst_dir, exist_ok=True)
    for n in names:
        shutil.copy(os.path.join(src_dir, n), dst_dir)


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def crc32_file(path):
    crc = 0
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 20):
            crc = zlib.crc32(chunk, crc)
    return crc


def load_map(path):
    with open(path, encoding='utf-8') as f:
        return [l.rstrip('\n').split('\t') for l in f if l.strip() and not l.startswith('#')]


def check_prerequisites():
    step('준비물 확인')
    if not os.path.isfile(ORIGINAL_ISO):
        raise BuildError('원본 ISO가 없습니다: ' + ORIGINAL_ISO)
    if os.path.getsize(ORIGINAL_ISO) != ORIGINAL_SIZE or crc32_file(ORIGINAL_ISO) != ORIGINAL_CRC:
        raise BuildError('원본 ISO의 CRC가 다릅니다 (ULJM05037 원본이 필요합니다)')
    if shutil.which('armips') is None:
        raise BuildError('armips 를 찾을 수 없습니다 (PATH 확인)')
    try:
        import PIL  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        raise BuildError('Pillow, numpy 가 필요합니다: pip install pillow numpy')
    print('OK')


def build_exes():
    """원본 EBOOT/prx 로 한글 실행파일을 만든다. ((EBOOT, EBOOT 표 위치), (prx, prx 표 위치), EP2/EP1 Moji.tbl)"""
    errors = (build_exe.ExeError, build_exe.charset.CharsetError, build_exe.msgtext.MsgError, ValueError)
    step('EP2 실행파일 (EBOOT.BIN) 빌드')
    boot = read(ORIGINAL_EBOOT)
    if zlib.crc32(boot) != ORIGINAL_EBOOT_CRC:
        raise BuildError('src/ep2/exe/BOOT.BIN 이 원본과 다릅니다')
    try:
        eboot, ep2_tbl, data_off = build_exe.build_ep2(boot, os.path.join(SRC, 'ep2', 'exe'),
                                                       os.path.join(BUILD, 'ep2exe'))
    except errors as e:
        raise BuildError(str(e))
    eboot_table = (data_off + EBOOT_TABLE[0], EBOOT_TABLE[1])

    step('EP1 실행파일 (dash2e1.prx) 빌드')
    prx = read(ORIGINAL_PRX)
    if zlib.crc32(prx) != ORIGINAL_PRX_CRC:
        raise BuildError('src/ep1/exe/dash2e1.prx 가 원본과 다릅니다')
    try:
        prx, ep1_tbl, data_off = build_exe.build_ep1(prx, os.path.join(SRC, 'ep1', 'exe'),
                                                     os.path.join(BUILD, 'ep1exe'))
    except errors as e:
        raise BuildError(str(e))
    prx_table = (data_off + PRX_TABLE[0], PRX_TABLE[1])
    return (eboot, eboot_table), (prx, prx_table), ep2_tbl, ep1_tbl


def build_ep2_dat(iso, moji_tbl):
    step('EP2 DAT 빌드')
    work = os.path.join(BUILD, 'ep2')
    msg_map = load_map(os.path.join(SRC, 'ep2', 'msg_map.txt'))
    tex_map = load_map(os.path.join(SRC, 'ep2', 'tex_map.txt'))

    # 대사/텍스처가 들어가는 BIN 만 원본에서 꺼내서 분할 (구 splitBIN.bat)
    targets = sorted({tuple(dst.split('/')[:2]) for _, dst in msg_map}
                     | {tuple(dst.split('/')[:2]) for _, _, dst in tex_map})
    out_dirs = {'DAT': 'OUTDAT', 'COMMON': 'OUTCOMMON'}
    for kind, name in targets:
        orig = os.path.join(work, 'orig', kind, name + '.BIN')
        write(orig, iso.read('PSP_GAME/USRDIR/{}/{}.BIN'.format(kind, name)))
        py(os.path.join(TOOLS, 'combbin.py'), '-x', orig, out_dirs[kind], cwd=work)

    # 대사 삽입 (구 XxMess.bat). txt2msg.py 는 자기 폴더의 MojiKor.tbl 을 읽는다
    shutil.copy(os.path.join(TOOLS, 'txt2msg.py'), work)
    shutil.copy(moji_tbl, os.path.join(work, 'MojiKor.tbl'))
    for text, dst in msg_map:
        kind, rest = dst.split('/', 1)
        py(os.path.join(work, 'txt2msg.py'), os.path.join(SRC, 'ep2', 'text', text),
           os.path.join(out_dirs[kind], rest), cwd=work)
    print('대사 {}개'.format(len(msg_map)))

    # 텍스처: PNG → PIX (XxTex.py), PIX → MTIM 압축 (구 work_tex/XX.BAT, 압축.bat)
    tex = os.path.join(work, 'tex')
    shutil.copytree(os.path.join(SRC, 'ep2', 'tex'), tex)
    copy_files(os.path.join(TOOLS, 'ep2'), tex, ['XxTex.py', 'ImageHill.py', 'TIMresource.py'])
    py('XxTex.py', cwd=tex)
    for mode, pix, dst in tex_map:
        kind, rest = dst.split('/', 1)
        target = os.path.join(work, out_dirs[kind], rest)
        if mode == 'copy':
            shutil.copy(os.path.join(tex, 'ORG', pix), target)
        else:
            run([os.path.join(TOOLS, 'MELTTIMTool.exe'), 'c', os.path.join('ORG', pix), target], tex, 'MELTTIMTool')
    print('텍스처 {}개'.format(len(tex_map)))

    # 결합 (구 combBIN.bat)
    result = {}
    for kind, name in targets:
        out = os.path.join(work, kind)
        os.makedirs(out, exist_ok=True)
        py(os.path.join(TOOLS, 'combbin.py'), '-c', os.path.join(out_dirs[kind], name), kind, cwd=work)
        result['PSP_GAME/USRDIR/{}/{}.BIN'.format(kind, name)] = os.path.join(out, name + '.BIN')
    print('BIN {}개 생성'.format(len(result)))
    return result


def build_ep1_dat(iso, moji_tbl):
    step('EP1 DAT 빌드')
    work = os.path.join(BUILD, 'ep1')
    dat = os.path.join(work, 'DAT')
    texts = sorted(os.listdir(os.path.join(SRC, 'ep1', 'text')))

    # 대사 삽입 (구 메세지삽입.bat). 파일명 ST07-0x00012000.TXT → DAT/ST07.BIN 의 0x12000 위치
    msg_bins = sorted({t.split('-')[0] for t in texts})
    tex_bins = ['GAME', 'SELECT', 'ST23T', 'ST25T', 'SUBSCN03', 'SUBSCN04', 'SUBSCN06', 'TITLE']
    for name in msg_bins + tex_bins + ['INIT']:
        write(os.path.join(dat, name + '.BIN'), iso.read('PSP_GAME/USRDIR/E1/DAT/{}.BIN'.format(name)))
    shutil.copytree(os.path.join(SRC, 'ep1', 'text'), os.path.join(work, 'XMessKor'))
    shutil.copy(os.path.join(TOOLS, 'ep1', 'txt2msg.py'), work)
    shutil.copy(moji_tbl, os.path.join(work, 'MojiKor.tbl'))
    for t in texts:
        py('txt2msg.py', os.path.join('XMessKor', t), cwd=work)
    print('대사 {}개'.format(len(texts)))

    # 텍스처 (구 work_tex/XX.BAT). XxTex.py 가 ../DAT/*.BIN 에 직접 쓴다
    tex = os.path.join(work, 'work_tex')
    shutil.copytree(os.path.join(SRC, 'ep1', 'tex'), tex)
    copy_files(os.path.join(TOOLS, 'ep1'), tex, ['XxTex.py', 'ImageHill.py', 'TIMresource.py'])
    py('XxTex.py', cwd=tex)
    print('텍스처 BIN {}개'.format(len(tex_bins)))

    # 폰트 (구 Font/XxFont.bat): INIT.BIN 의 79920~114176 = CLUT(2000) + FONT.BIN
    font = os.path.join(work, 'font')
    shutil.copytree(os.path.join(SRC, 'ep1', 'font'), font)
    shutil.copy(os.path.join(TOOLS, 'ep1', 'FontTool.py'), font)
    py('FontTool.py', 'combine', cwd=font)
    init = read(os.path.join(dat, 'INIT.BIN'))
    clut = init[79920:79920 + 2000]
    font_bin = read(os.path.join(font, 'FONT.BIN'))
    if len(clut) + len(font_bin) != 114176 - 79920:
        raise BuildError('FONT.BIN 크기가 다릅니다: {}'.format(len(font_bin)))
    write(os.path.join(dat, 'INIT.BIN'), init[:79920] + clut + font_bin + init[114176:])
    print('폰트 INIT.BIN')

    return {'PSP_GAME/USRDIR/E1/DAT/{}.BIN'.format(n): os.path.join(dat, n + '.BIN')
            for n in msg_bins + tex_bins + ['INIT']}


def update_file_table(path, table, orig_iso, iso):
    """실행파일의 파일 테이블 갱신 (구 DATA/lba.txt 수작업).
    원본 ISO 의 USRDIR 파일과 LBA/크기가 같은 항목 중, 위치가 바뀐 파일만 새 LBA/크기로 바꾼다."""
    offset, count = table
    by_pos = {(lba, size): key for key, (_, lba, size) in orig_iso.entries.items()
              if key.startswith('PSP_GAME/USRDIR/')}
    data = bytearray(read(path))
    moved = []
    for i in range(count):
        pos = offset + i * 12
        _, lba, size = struct.unpack_from('<III', data, pos)
        key = by_pos.get((lba, size))
        if key and iso.entries[key][1] != lba:
            _, n_lba, n_size = iso.entries[key]
            struct.pack_into('<III', data, pos, 0, n_lba, n_size)
            moved.append(key.rsplit('/', 1)[1])
    return bytes(data), moved


def build_iso(eboot, eboot_table, prx, prx_table, ep1_bins, ep2_bins):
    step('ISO 빌드')
    iso_path = os.path.join(OUT, ISO_NAME)
    shutil.copyfile(ORIGINAL_ISO, iso_path)
    orig = IsoImage(ORIGINAL_ISO, writable=False)
    iso = IsoImage(iso_path)
    try:
        # 커진 파일은 이 순서대로 ISO 끝에 붙는다 (배포본과 같은 배치)
        iso.replace('PSP_GAME/SYSDIR/EBOOT.BIN', read(eboot))
        iso.replace('PSP_GAME/USRDIR/dash2e1.prx', read(prx))
        for path in sorted(ep1_bins):
            iso.replace(path, read(ep1_bins[path]))
        for path in sorted(ep2_bins):
            iso.replace(path, read(ep2_bins[path]))
        icon = read(os.path.join(SRC, 'iso', 'ICON0.PNG'))
        iso.replace('PSP_GAME/USRDIR/DAT/PICT/savepic.png', icon)
        iso.replace('PSP_GAME/PARAM.SFO', read(os.path.join(SRC, 'iso', 'PARAM.SFO')))
        iso.replace('PSP_GAME/ICON0.PNG', icon)
        iso.replace('PSP_GAME/PIC0.PNG', read(os.path.join(SRC, 'iso', 'PIC0.PNG')))
        iso.replace('PSP_GAME/PIC1.PNG', read(os.path.join(SRC, 'iso', 'PIC1.PNG')))
        # 복호화된 EBOOT.BIN 이 실행되도록 BOOT.BIN 은 0으로 채운다
        iso.replace('PSP_GAME/SYSDIR/BOOT.BIN', bytes(len(orig.read('PSP_GAME/SYSDIR/BOOT.BIN'))))

        # 배치가 끝난 뒤 EBOOT(EP2)와 dash2e1.prx(EP1)의 파일 테이블 갱신
        # (실행파일 크기는 그대로라 제자리에 다시 쓴다)
        data, moved = update_file_table(eboot, eboot_table, orig, iso)
        iso.replace('PSP_GAME/SYSDIR/EBOOT.BIN', data)
        data, moved_prx = update_file_table(prx, prx_table, orig, iso)
        iso.replace('PSP_GAME/USRDIR/dash2e1.prx', data)
    finally:
        iso.close()
        orig.close()
    print('ISO 끝으로 옮겨진 파일 → EBOOT 테이블: ' + ', '.join(moved))
    print('                       → prx 테이블: ' + ', '.join(moved_prx))
    print(ISO_NAME)
    return iso_path


def build_patch(iso_path):
    step('패치 파일 생성')
    sys.path.insert(0, os.path.join(ROOT, 'installer'))
    from bptc import apply_patch

    patch = os.path.join(OUT, 'rockman.patch')
    make_patch(ORIGINAL_ISO, iso_path, patch)
    # 인스톨러와 같은 코드로 적용해서 결과가 같은지 확인
    check = os.path.join(BUILD, 'patch_check.iso')
    apply_patch(ORIGINAL_ISO, patch, check)
    if crc32_file(check) != crc32_file(iso_path):
        raise BuildError('rockman.patch 검증 실패')
    os.remove(check)
    print('rockman.patch ({:,} bytes, 검증 OK)'.format(os.path.getsize(patch)))
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
        run(['pyarmor', 'gen', '-O', 'obf', 'DashKor.py', 'bptc.py'], work, 'pyarmor')
        entry = os.path.join('obf', 'DashKor.py')
    else:
        print('PyArmor 가 없어서 난독화 없이 빌드합니다.')

    cmd = [sys.executable, '-m', 'PyInstaller', '--onefile', '--noconfirm', '--noconsole',
           '--name', 'Dash2Kor',
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
    run(cmd, work, 'pyinstaller')
    print('Dash2Kor.exe')


def main():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD)
    os.makedirs(OUT, exist_ok=True)

    check_prerequisites()

    (eboot, eboot_table), (prx, prx_table), ep2_tbl, ep1_tbl = build_exes()

    orig = IsoImage(ORIGINAL_ISO, writable=False)
    try:
        ep2_bins = build_ep2_dat(orig, ep2_tbl)
        ep1_bins = build_ep1_dat(orig, ep1_tbl)
    finally:
        orig.close()

    iso_path = build_iso(eboot, eboot_table, prx, prx_table, ep1_bins, ep2_bins)
    patch = build_patch(iso_path)
    build_installer(patch)

    step('완료 → ' + OUT)


if __name__ == '__main__':
    try:
        main()
    except BuildError as e:
        print('\n[실패] ' + str(e))
        sys.exit(1)
