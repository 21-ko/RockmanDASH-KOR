; 록맨 DASH2 EP2 (EBOOT.BIN) 한글 출력
;
; 원본 대사 바이트: 0x00~0xE9 = 1바이트 글자, 0xEA~0xF7 = 2바이트 한자 첫 바이트, 0xF8 = 버튼, 0xFB~ = 제어.
; 원본 글꼴은 VRAM 4bpp 페이지에 12x12 글자 20열을 2비트 평면 두 개로 넣고 CLUT 로 평면을 고른다.
;
; 한글판 (tools/exe/charset.py 참고)
;   - 2바이트 글자는 첫 바이트 0xF1~: 평면 1 = 0xF100~, 평면 2 = 0xF700~ (첫 바이트 0xF7~ 이면 평면 2 CLUT)
;   - 글꼴 텍스처: 원본 글꼴 페이지 대신 확장 영역의 RAM 텍스처 (1024x512, 41열)
;   - 글자를 그릴 때 u,v 에 열·행 번호를 넣고, 정점을 만들 때 지금 텍스처가 한글 글꼴이면 12배 한다
;     (u,v 가 1바이트라 512 크기 텍스처 좌표를 직접 못 넣음)
;   - 1바이트 글자는 폭 표(DATA/widths.txt)로 가변폭
;   - 대사 테이블 4바이트 모드 (msgtable.asm)
;
; 주소와 글자 코드 상수는 build_exe.py 가 만드는 layout.asm 에 있다.

.psp
.include "layout.asm"
.include "msgtable.asm"
.open "EBOOT.BIN", TEXT_HEADERSIZE

ORIG_FONT_TEX   equ 0x04128180      ; VRAM 의 원본 글꼴 페이지
GLYPH_SIZE      equ 12
BUTTON_COUNT    equ 4               ; ○△▽□

.definelabel ClutTable,     0x08AEA2A4  ; 글자 CLUT ID 표 (u16, [스타일 + 평면*8]), [0] = 버튼 색


; ================================================================
;  대사 글자
; ================================================================

; 타자 진행: 0xEA~0xF7 에 붙이던 2바이트 한자 표시(0x400000)를 0xEA~0xF0 에만
.org 0x08838468
    sltiu   v0, v1, KOR_LEAD_FIRST

; 그리기: 한자(0xEA~0xF7) 처리로 가던 분기를 없애고 모두 아래 글자 처리로
.org 0x08838E38
    b       0x08838F24

; 평면 2 CLUT 를 쓰는 첫 바이트 (원래 0xF9)
.org 0x08838F28
    sltiu   v1, a0, KOR_PLANE2_LEAD

; 글자 → 텍스처 칸, 폭 (원래 0x08838F48~0x0883905C 는 이제 안 씀)
.org 0x08838F48
    j       GlyphCell
    lh      fp, 0(v0)               ; CLUT ID (원래 명령)

; 커서 ▷ ▶ 의 텍스처 위치를 열·행으로 (정점에서 12배 되므로)
.org 0x0883AB8C
    li      t7, CURSOR_OPEN_COL     ; ▷ u
.org 0x0883AC44
    li      t7, CURSOR_FILL_COL     ; ▶ u
.org 0x0883ABE8
    ori     v1, v1, CURSOR_ROW << 8 ; ▷▶ v
.org 0x0888E670                     ; 롤의 일기장
    ori     a2, a2, (CURSOR_ROW << 8) | CURSOR_FILL_COL
.org 0x08A3EEB4                     ; 특수 무기 장착, 개발
    ori     a2, a2, (CURSOR_ROW << 8) | CURSOR_FILL_COL
.org 0x08A426E0
    ori     a2, a2, (CURSOR_ROW << 8) | CURSOR_FILL_COL
.org 0x08A9A0E4
    ori     a2, a2, (CURSOR_ROW << 8) | CURSOR_FILL_COL

; 줄바꿈(0xFC) 처리에서 0x17 칸을 한 번 더 늘리던 것 없앰 (원래 sb a1,0x17(a0))
.org 0x0883AF28
    nop

; 실행파일이 직접 찍는 ” (원래 2바이트 0xF8 0x1E)
.org 0x0883CACC
    li      v0, CLOSE_QUOTE >> 8
.org 0x0883CAE4
    li      v0, CLOSE_QUOTE & 0xFF

; 롤러보드 경주 기록의 이름 칸
.org 0x08844E88
    lui     t1, CODE_SA             ; 사
.org 0x08844EDC
    ori     t1, t1, CODE_MOT        ; 못
.org 0x08844EE8
    li      t2, CODE_FULL_SPACE     ; 전각 공백


; ================================================================
;  글꼴 텍스처
; ================================================================

; sceGuTexImage: 원본 글꼴 페이지면 한글 글꼴로 바꾸고 크기를 512 로
.org 0x08AAAAB4
    j       TexImageHook            ; 지연 슬롯은 원래 명령 (sw s4,0x10(sp))

; 스프라이트 정점: 한글 글꼴이면 u,v 를 12배
.org 0x08AA939C
    j       SpriteUV
    nop


; ================================================================
;  대사 테이블 4바이트 모드
; ================================================================

.org 0x08837D04
    j       MsgHook1
    nop
.org 0x0883ADAC
    j       MsgHook2
    nop
.org 0x0883C5FC
    j       MsgHook3
    nop
.org 0x0883C650
    j       MsgHook4
    nop
.org 0x0883C810
    j       MsgHook5
    nop
.org 0x0883C894
    j       MsgHook6
    nop
.org 0x0883D8F8
    j       MsgHook7
    nop
.org 0x0883D948
    j       MsgHook8
    nop


; ================================================================
;  .data
; ================================================================
.headersize DATA_HEADERSIZE

; 미션 / 스타트 / 컴플리트 글자 그림 좌표 (12바이트씩)
.org 0x08AE927C
    .byte 0xE8, 0x00, 0x80, 0x0A, 0x00, 0xFD, 0x98, 0x01, 0x00, 0x00, 0x16, 0x00
    .byte 0xF0, 0x00, 0x00, 0x0B, 0x00, 0xFE, 0x98, 0x01, 0x00, 0x00, 0x17, 0x00
    .byte 0xF8, 0x00, 0x80, 0x0B, 0x00, 0xFF, 0x98, 0x01, 0x00, 0x00, 0x00, 0x00
    .byte 0x80, 0x00, 0x00, 0x08, 0x00, 0xE8, 0x13, 0x18, 0x13, 0x00, 0x00, 0x00
    .byte 0xA0, 0x00, 0x00, 0x0A, 0x13, 0xE8, 0x06, 0x18, 0x19, 0x00, 0x00, 0x00
    .byte 0xC0, 0x00, 0x00, 0x0C, 0x19, 0xE8, 0x16, 0x18, 0x2F, 0x00, 0x00, 0x00
    .byte 0xE0, 0x00, 0x00, 0x0E, 0x2F, 0xE8, 0x06, 0x18, 0x35, 0x00, 0x00, 0x00
    .byte 0x00, 0x01, 0x00, 0x00, 0x35, 0xE8, 0x1E, 0x18, 0x58, 0x00, 0x00, 0x00
    .byte 0x20, 0x01, 0x00, 0x02, 0x58, 0xE8, 0x0D, 0x18, 0x65, 0x00, 0x00, 0x00
    .byte 0x40, 0x01, 0x00, 0x04, 0x65, 0xE8, 0x19, 0x18, 0x7E, 0x00, 0x00, 0x00
    .byte 0x60, 0x01, 0x00, 0x06, 0x7E, 0xE8, 0x0C, 0x18, 0x8A, 0x00, 0x00, 0x00
    .byte 0x80, 0x01, 0x00, 0x08, 0x8A, 0xE8, 0x0C, 0x18, 0x00, 0x00, 0x00, 0x00
    .byte 0x80, 0x00, 0x00, 0x08, 0x00, 0xE8, 0x13, 0x18, 0x13, 0x00, 0x00, 0x00
    .byte 0xA0, 0x00, 0x00, 0x0A, 0x13, 0xE8, 0x06, 0x18, 0x19, 0x00, 0x00, 0x00
    .byte 0xC0, 0x00, 0x00, 0x0C, 0x19, 0xE8, 0x16, 0x18, 0x2F, 0x00, 0x00, 0x00
    .byte 0xE0, 0x00, 0x00, 0x0E, 0x2F, 0xE8, 0x06, 0x18, 0x35, 0x00, 0x00, 0x00
    .byte 0x00, 0x01, 0x00, 0x00, 0x35, 0xE8, 0x1E, 0x18, 0x58, 0x00, 0x00, 0x00
    .byte 0x20, 0x01, 0x00, 0x02, 0x98, 0xE8, 0x0D, 0x18, 0x65, 0x00, 0x00, 0x00
    .byte 0x40, 0x01, 0x00, 0x04, 0xA5, 0xE8, 0x10, 0x18, 0x75, 0x00, 0x00, 0x00
    .byte 0x60, 0x01, 0x00, 0x06, 0xB5, 0xE8, 0x13, 0x18, 0x88, 0x00, 0x00, 0x00
    .byte 0x80, 0x01, 0x00, 0x08, 0xC8, 0xE8, 0x15, 0x18, 0x9D, 0x00, 0x00, 0x00
    .byte 0xA0, 0x01, 0x00, 0x0A, 0xDD, 0xE8, 0x0A, 0x18, 0xA7, 0x00, 0x00, 0x00
    .byte 0xC0, 0x01, 0x00, 0x0C, 0xE7, 0xE8, 0x16, 0x18


; ================================================================
;  확장 영역 코드
; ================================================================
.org EXT_CODE
.area EXT_CODE_END - EXT_CODE

; 0x08838F48 에서 옴. t0 = a0 = 첫 바이트, t1 = 글자 위치, fp = 스타일 CLUT ID
; 나가는 값 (0x08838B18): s5 = 열, s2 = 행, s6 = 폭, s7 = 높이, fp = CLUT ID
;                         2바이트 글자면 t1 은 둘째 바이트, a1 = 둘째 바이트
GlyphCell:
    addiu   v1, a0, -BUTTON_FIRST
    sltiu   v1, v1, BUTTON_COUNT
    beqz    v1, @@code
    andi    v1, t0, 0xFF
    addiu   t2, v1, -BUTTON_FIRST   ; 원본 버튼 처리처럼 t2 = 버튼 번호
    lui     v0, hi(ClutTable)
    lh      fp, lo(ClutTable)(v0)   ; 버튼 글자는 버튼 색 CLUT
@@code:
    sltiu   v0, v1, KOR_LEAD_FIRST
    bnez    v0, @@cell              ; 1바이트: 글자 번호 = 바이트
    move    a0, v1
    addiu   t1, t1, 1               ; 2바이트
    lbu     a1, 0(t1)
    sll     a0, v1, 8
    or      a0, a0, a1
    li      v0, KOR_CODE_BASE
    subu    a0, a0, v0              ; 글자 번호
    sltiu   v0, a0, KOR_PLANE2_INDEX
    bnez    v0, @@cell
    nop
    addiu   a0, a0, -KOR_PLANE2_INDEX   ; 평면 2 안의 번호
@@cell:
    li      v0, KOR_FONT_COLUMNS
    divu    a0, v0
    mflo    v0
    andi    s2, v0, 0xFF            ; v = 행
    mfhi    v0
    andi    s5, v0, 0xFF            ; u = 열
    li      s6, GLYPH_SIZE
    sltiu   v0, t0, ONE_BYTE_COUNT
    beqz    v0, @@done
    li      s7, GLYPH_SIZE
    lui     v0, hi(WidthTable)
    addu    v0, v0, t0
    lbu     s6, lo(WidthTable)(v0)  ; 1바이트 글자는 폭 표
@@done:
    j       0x08838B18
    nop

; 0x08AAAAB4 에서 옴. a0 = 너비, s1 = 높이, t0 = 텍스처 주소 (sceGuTexImage 인자를 옮겨 둔 상태)
TexImageHook:
    sll     s0, s0, 2               ; 덮어쓴 원래 명령
    li      at, ORIG_FONT_TEX
    bne     t0, at, @@save
    nop
    li      t0, KOR_FONT_TEX
    li      a0, KOR_FONT_TEX_SIZE
    li      s1, KOR_FONT_TEX_SIZE
@@save:
    lui     at, hi(CurTex)
    j       0x08AAAABC
    sw      t0, lo(CurTex)(at)

; 0x08AA939C 에서 옴. v0 = 크기 표 항목, t6 = 정점, t7/t8 = u/v 시작의 하위 바이트
SpriteUV:
    lui     at, hi(CurTex)
    lw      at, lo(CurTex)(at)
    li      v1, KOR_FONT_TEX
    beq     at, v1, @@font
    lhu     v1, 0x3C(v0)            ; 텍스처 너비 (원래 명령)
    j       0x08AA93A4              ; 한글 글꼴이 아니면 원래대로
    addu    v1, v1, s1              ; 덮어쓴 원래 명령 (u 끝)
@@font:
    sll     at, t7, 1
    addu    at, at, t7
    sll     t7, at, 2               ; u = 열 x 12
    sh      t7, 0x0(t6)
    addu    v1, v1, t7
    sh      v1, 0xA(t6)             ; u 끝
    sll     at, t8, 1
    addu    at, at, t8
    sll     t8, at, 2               ; v = 행 x 12
    sh      t8, 0x2(t6)
    lhu     at, 0x40(v0)            ; 텍스처 높이
    addu    at, at, t8
    j       0x08AA93DC
    sh      at, 0xC(t6)             ; v 끝

; 대사 테이블 항목 (원래 lhu 로 읽던 곳)
MsgHook1:                           ; a1 = 테이블, a2 = 테이블 + 번호*2
    subu    a2, a2, a1
    sra     a2, a2, 1
    MsgEntry v0, a2, a1, a2
    j       0x08837D0C
    srl     a2, a0, 0x13            ; 덮어쓴 원래 명령
MsgHook2:                           ; a2 = 테이블, a1 = 번호
    MsgEntry t0, a1, a2, a1
    j       0x0883ADB8
    nop
MsgHook3:                           ; t1 = 테이블, v1 = 번호
    MsgEntry a0, v1, t1, v1
    addu    a0, a0, t1
    sw      a0, 0x30(t0)
    jr      ra
    nop
MsgHook4:                           ; a3 = 테이블, v0 = 번호
    MsgEntry v1, v0, a3, v0
    addu    v1, v1, a3
    jr      ra
    sw      v1, 0x34(a0)
MsgHook5:                           ; t1 = 테이블, v1 = 번호
    MsgEntry a0, v1, t1, v1
    addu    a0, a0, t1
    addiu   a0, a0, 2
    sw      a0, 0x30(t0)
    jr      ra
    nop
MsgHook6:                           ; t0 = 테이블, a0 = 번호
    MsgEntry v1, v0, t0, a0
    addu    v1, v1, t0
    addiu   v1, v1, 2
    jr      ra
    sw      v1, 0x34(a3)
MsgHook7:                           ; a2 = 테이블, v1 = 번호
    MsgEntry v0, v1, a2, v1
    j       0x0883D908
    sw      a0, 0x30(a1)            ; 덮어쓴 원래 명령
MsgHook8:                           ; a1 = 테이블, v1 = 번호
    MsgEntry v0, v1, a1, v1
    addu    v0, v0, a1
    jr      ra
    sw      v0, 0x34(a0)

.align 4
CurTex:                             ; 마지막으로 sceGuTexImage 에 넘어간 텍스처 주소
    .word 0
WidthTable:                         ; 1바이트 글자 폭 (DATA/widths.txt)
    .incbin "widths.bin"

.endarea

.close
