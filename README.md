# 록맨 DASH 1·2 PSP 한글패치

PSP 판 록맨 DASH 시리즈 두 편의 한글패치 빌드 프로젝트.
원본 ISO 를 넣고 `Build.bat` 을 실행하면 한글 ISO, BPTC 패치, 패치 인스톨러가 만들어진다.

| 폴더 | 게임 | 배포 |
|---|---|---|
| `록맨DASH1/` | 록맨 DASH 강철의 모험심 (ULJM05030) | 2025-04-26 |
| `록맨DASH2/` | 록맨 DASH2 에피소드2 위대한 유산 (ULJM05037) | 2025-05-28 |

### 레포에 없는 것

| 경로 | 내용 | 없을 때 |
|---|---|---|
| `*/원본/UMD9660.ISO` (모든 ISO) | 원본 게임 | 직접 넣어야 빌드 가능 |
| `*/자료/` | 작업 자료 (그래픽 원본 psd, 일본어 원문, 원본 DAT, 도구 등) | 빌드에는 영향 없음 |
| `*/build/`, `*/결과물/` | 빌드가 만듦 | — |

게임 파일은 빌드할 때 원본 ISO 에서 꺼내 쓰므로, 클론하고 원본 ISO 만 넣으면 두 프로젝트 모두 빌드된다.

## 준비물

- Windows (빌드 스크립트 일부가 `.exe` 도구를 쓴다)
- Python 3 (3.13 에서 확인) + `pip install pillow numpy`
- [armips](https://github.com/Kingcom/armips) (PATH 에 있어야 함, v0.11.0 에서 확인)
- 인스톨러까지 만들려면 `pip install pyinstaller pyqt5` (없으면 그 단계만 건너뜀). `upx.exe` 와 PyArmor 는 있으면 사용
- 원본 ISO (레포에 없음). 각 프로젝트의 `원본/UMD9660.ISO` 로 넣는다.

| 게임 | 크기 (바이트) | CRC32 |
|---|---|---|
| 록맨 DASH (ULJM05030) | 316,735,488 | `78DFD145` |
| 록맨 DASH2 (ULJM05037) | 349,503,488 | `40F10DE6` |

빌드는 시작할 때 크기와 CRC 를 확인하고, 다르면 멈춘다.

## 빌드

각 프로젝트 폴더의 `Build.bat` 을 실행한다 (`python tools\build.py`). 결과는 그 폴더의 `결과물/` 에 생긴다.

| 파일 | 내용 |
|---|---|
| `록맨DASH_한글.iso` / `록맨DASH2_한글.iso` | 한글 ISO |
| `rockman.patch` | 원본 ISO → 한글 ISO BPTC 패치 (빌드가 직접 적용해서 검증) |
| `DashKor.exe` / `Dash2Kor.exe` | 패치 인스톨러 (PyInstaller 가 있을 때) |

걸리는 시간은 DASH1 약 2분, DASH2 약 4분. `build/` 는 매번 지우고 새로 만든다.

## 구조

```
록맨DASH1/, 록맨DASH2/
  Build.bat      전체 빌드
  src/           빌드 입력. 번역은 여기만 고치면 된다
  tools/         빌드 스크립트 (tools/build.py 가 시작점)
  installer/     패치 인스톨러 소스
  자료/          빌드에 안 쓰는 작업 자료 (레포에 없음)
  원본/          원본 ISO 자리 (레포에 없음)
  build/, 결과물/  빌드가 만듦 (레포에 없음)
```

### DASH1 DAT
빌드가 원본 ISO 의 `USRDIR/DAT/*.BIN` 을 `tools/DashEditor` 로 풀고, 아래를 덮어쓴 뒤 다시 묶는다.
- `src/text/*.msg.txt` 번역 대사. `src/msg_map.csv` 대로 같은 대사를 여러 DAT 에 넣는다
- `src/tim/<DAT 이름>/...` 한글 그래픽 TIM (DAT 안 경로 그대로)

다시 묶는 DAT 는 이 둘이 들어가는 것 (지금 140개). 예전에 쓰던 추출 폴더(`src/dat`)로 만든 결과와 BIN 이 바이트 단위로 같다.

## 메모

- `.gitattributes` 로 모든 파일을 바이트 그대로 저장한다 (줄바꿈 변환 없음). 대사·테이블 파일의 CRLF/LF 가
  바뀌면 빌드 결과가 달라질 수 있다.
- 두 프로젝트의 `tools/isotool.py`, `tools/bptc_make.py` 는 각자 사본이다.
