; 록맨 DASH 한글 글꼴 확장
;
; 원본 글꼴은 VRAM 의 4bpp 페이지 하나(256x256)에 12x12 글자를 21x21 로 두 장 겹쳐 넣고
; CLUT 로 어느 쪽을 보일지 고른다. 문자 코드는 0x000~0x371, 제어 코드는 0x372~0x3FF.
;
; 한글 글꼴은 실행파일 확장 영역의 RAM 텍스처(KOR_FONT_TEX)에 따로 둔다.
;   - 문자 코드 0x400 이상도 글자로 취급한다. 글자 번호 = 코드 (0x400 이상은 코드 - 0x8E)
;   - 대사 출력 함수가 SPRT(0x64) 대신 한글 글자 프리미티브(PRIM_KGLYPH)를 만든다.
;     u,v 자리(+0x0C)에는 16비트 글자 번호를 넣는다.
;   - PS1 GPU 에뮬레이션은 0x00~0x1F 코드를 아무것도 안 하는 함수로 보내는데,
;     그 함수를 고쳐 PRIM_KGLYPH 이면 한글 텍스처로 글자를 그린다.
;   그래서 원본 글꼴 페이지를 쓰는 다른 그래픽(작은 글꼴, 아이콘 등)은 원본 그대로 나온다.
;
; 주소와 글꼴 배치 상수는 build_eboot.py 가 만드는 layout.asm 에 있다.

.psp
.include "layout.asm"
.open "EBOOT.BIN", TEXT_HEADERSIZE

CTRL_FIRST      equ 0x372       ; 제어 코드 시작
CTRL_COUNT      equ 0x400 - CTRL_FIRST
EXT_FIRST       equ 0x400       ; 확장 문자 코드 시작 (글자 번호 0x372 부터)
HALF_SPACE_W    equ 6           ; 반각 공백 폭 (일반 글자는 12)
PRIM_KGLYPH     equ 0x1C        ; 한글 글자 프리미티브 코드 (PS1 에서는 NOP)

; ---- 원본 함수/변수 ----
.definelabel FixPrimColor,  0x08A1B1EC  ; (r*, g*, b*) 색 하위 비트 보정
.definelabel ScaleX,        0x08A1B214  ; PS1 x → 화면 x
.definelabel ScaleY,        0x08A1B220  ; PS1 y → 화면 y
.definelabel SetTpage,      0x08A1BA50  ; (DR_MODE 프리미티브*) 텍스처 페이지 적용
.definelabel ClutIdToAddr,  0x08A1CDA4  ; (CLUT ID) → CLUT 주소
.definelabel GuEnable,      0x08A253E8
.definelabel DrawSprite,    0x08A263D4  ; (x, y, 0, u, v, 0, 0)
.definelabel SetSpriteSize, 0x08A267E0  ; (텍스처 w, h, 화면 w, h)
.definelabel GuColor,       0x08A272B4
.definelabel GuShadeModel,  0x08A274F8
.definelabel GuTexMode,     0x08A278A8  ; (psm, 0, 0, 0)
.definelabel GuTexImage,    0x08A27BA0  ; (0, w, h, tbw, 주소)
.definelabel GuClutLoad,    0x08A27DBC  ; (블록 수, 주소)
.definelabel DrawOffsetX,   0x08BA3F58  ; u16
.definelabel DrawOffsetY,   0x08BA3F5A  ; u16
.definelabel TpageCache,    0x08B2801C  ; u16, 마지막으로 적용한 tpage (0xFFFF = 없음)


; ================================================================
;  대사 출력 함수 (0x08840xxx) 고치기
; ================================================================

; 타자 진행: 다음 글자가 제어 코드인지 판정
.org 0x088406E4
    j       TypeCheckCode
    move    a0, a2

; 그리기: 다음 글자가 제어 코드인지 판정
.org 0x08840814
    j       DrawCheckCode
    nop

; 글자 프리미티브 코드
.org 0x08840838
    li      v1, PRIM_KGLYPH

; 두 번째 글꼴 페이지로 가는 분기 없애기 (항상 첫 페이지 CLUT)
.org 0x0884088C
    nop
    nop

; u,v 계산 대신 글자 번호 저장
.org 0x088408B0
.area 0x0884092C - 0x088408B0, 0
    lw      v0, 0x14(s0)
    lhu     v0, 0x0(v0)             ; 문자 코드
    sltiu   v1, v0, EXT_FIRST
    bnez    v1, @@store
    nop
    addiu   v0, v0, CTRL_FIRST - EXT_FIRST
@@store:
    b       0x0884092C
    sh      v0, 0xC(a2)             ; 글자 번호
.endarea

; PS1 GPU 0x00~0x1F 코드 처리 함수 (원래 jr ra / nop)
.org 0x08A1CD3C
    j       KorGlyphPrim
    nop


; ================================================================
;  확장 영역 코드
; ================================================================
.headersize EXT_HEADERSIZE
.org EXT_CODE
.area EXT_CODE_END - EXT_CODE

; v1 = 문자 코드. 0x372~0x3FF 만 제어 코드
TypeCheckCode:
    addiu   v0, v1, -CTRL_FIRST
    sltiu   v0, v0, CTRL_COUNT
    beqz    v0, @@char
    nop
    j       0x08840BEC              ; 제어 코드 처리
    nop
@@char:
    j       0x088406F0
    nop

; v1 = 문자 코드, a1 = 문자 위치
DrawCheckCode:
    addiu   v0, v1, -CTRL_FIRST
    sltiu   v0, v0, CTRL_COUNT
    beqz    v0, @@char
    nop
    j       0x08840B3C              ; 제어 코드 처리
    sll     v0, v1, 2               ; (제어 코드 처리에서 v0 = 코드*4 를 씀)
@@char:
    li      v0, CHAR_HALF_SPACE
    beq     v1, v0, @@halfSpace
    nop
    j       0x08840820              ; 글자 그리기
    nop
@@halfSpace:                        ; 그리지 않고 6 만큼만 이동
    lhu     v0, 0x10(s0)
    addiu   v0, v0, HALF_SPACE_W
    sh      v0, 0x10(s0)
    addiu   v0, a1, 2
    sw      v0, 0x14(s0)
    j       0x0884099C              ; 다음 글자
    lw      a2, 0x6C(s0)

; a0 = 프리미티브. PRIM_KGLYPH 가 아니면 원래처럼 아무것도 안 한다.
; 원본 SPRT 처리(0x08A1C83C, 크기 지정형)와 같은 순서로 그리되
; 텍스처를 한글 글꼴로 바꾸고 u,v 를 글자 번호로 계산한다.
KorGlyphPrim:
    lbu     v0, 0x7(a0)
    andi    v0, v0, 0xFC            ; 반투명/텍스처 직접 비트 무시
    xori    v0, v0, PRIM_KGLYPH
    beqz    v0, @@glyph
    nop
    jr      ra
    nop
@@glyph:
    addiu   sp, sp, -0x20
    sw      s0, 0x08(sp)
    sw      s1, 0x0C(sp)
    sw      s2, 0x10(sp)
    sw      s3, 0x14(sp)
    sw      ra, 0x18(sp)
    move    s0, a0

    ; 그리기 상태 (원본 SPRT 와 같음)
    jal     GuEnable
    li      a0, 9
    jal     GuEnable
    li      a0, 0x15
    jal     GuShadeModel
    move    a0, zero
    addiu   a0, s0, 4
    addiu   a1, s0, 5
    jal     FixPrimColor
    addiu   a2, s0, 6
    lbu     a0, 4(s0)
    lbu     v0, 5(s0)
    lbu     v1, 6(s0)
    sll     v0, v0, 8
    or      a0, a0, v0
    sll     v1, v1, 16
    or      a0, a0, v1
    lui     v0, 0x8000
    jal     GuColor
    or      a0, a0, v0
    jal     ClutIdToAddr
    lhu     a0, 0xE(s0)
    li      a0, 0x10
    jal     GuClutLoad
    move    a1, v0

    ; 한글 글꼴 텍스처 (4bpp)
    li      a0, 4
    li      a1, 0
    li      a2, 0
    jal     GuTexMode
    li      a3, 0
    li      a0, 0
    li      a1, KOR_FONT_TEX_SIZE
    li      a2, KOR_FONT_TEX_SIZE
    li      a3, KOR_FONT_TEX_SIZE
    li      t0, KOR_FONT_TEX
    jal     GuTexImage
    nop

    ; 크기
    lh      s1, 0x10(s0)            ; w
    jal     ScaleX
    move    a0, s1
    move    s3, v0
    lh      s2, 0x12(s0)            ; h
    jal     ScaleY
    move    a0, s2
    move    a0, s1
    move    a1, s2
    move    a2, s3
    jal     SetSpriteSize
    move    a3, v0

    ; 화면 위치
    li      v1, DrawOffsetX
    lhu     v0, 0(v1)
    lhu     a0, 0x8(s0)
    addu    a0, a0, v0
    jal     ScaleX
    seh     a0, a0
    move    s1, v0
    li      v1, DrawOffsetY
    lhu     v0, 0(v1)
    lhu     a0, 0xA(s0)
    addu    a0, a0, v0
    jal     ScaleY
    seh     a0, a0
    move    a1, v0

    ; 글자 번호 → 텍스처 좌표
    lhu     v0, 0xC(s0)
    li      v1, KOR_FONT_COLUMNS
    divu    v0, v1
    mfhi    a3                      ; 열
    mflo    t0                      ; 행
    li      v1, KOR_FONT_CELL
    multu   a3, v1
    mflo    a3                      ; u
    multu   t0, v1
    mflo    t0                      ; v
    move    a0, s1
    move    a2, zero
    move    t1, zero
    jal     DrawSprite
    move    t2, zero

    ; 원래 텍스처 페이지 다시 적용 (다음 프리미티브가 그대로 쓸 수 있게)
    li      v1, TpageCache
    lhu     v0, 0(v1)
    li      a0, 0xFFFF
    beq     v0, a0, @@done
    sh      a0, 0(v1)               ; 캐시를 비워야 SetTpage 가 다시 적용한다
    sw      v0, 4(sp)               ; sp+0 = 임시 DR_MODE 프리미티브
    jal     SetTpage
    move    a0, sp
@@done:
    lw      s0, 0x08(sp)
    lw      s1, 0x0C(sp)
    lw      s2, 0x10(sp)
    lw      s3, 0x14(sp)
    lw      ra, 0x18(sp)
    jr      ra
    addiu   sp, sp, 0x20

.endarea

.close
