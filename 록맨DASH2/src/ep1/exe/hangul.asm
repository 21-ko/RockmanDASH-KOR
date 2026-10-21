; 록맨 DASH2 EP1 (dash2e1.prx) 대사 테이블 4바이트 모드
;
; 번역이 원래 자리에 안 들어간 대사 테이블은 4바이트 모드로 바뀌고 데이터는 확장 영역에 들어간다
; (tools/exe/msgtext.py, msgtable.asm). 테이블 항목을 읽는 곳 네 군데를 고친다.
;
; dash2e1.prx 는 EP2 EBOOT 바로 뒤 EP1_LOAD_ADDR(0x091B2000)에 올라간다고 보고 주소를 쓴다.
; (EBOOT 의 끝 주소를 고정해 두는 이유. build_exe.py 참고)

.psp
.include "layout.asm"
.include "msgtable.asm"
.open "dash2e1.prx", TEXT_HEADERSIZE

.org 0x091DB0C4
    j       MsgHook1                ; 지연 슬롯은 원래 명령 (sw v1,4(sp))
.org 0x091DD984
    j       MsgHook2
    nop
.org 0x091DEB3C
    j       MsgHook3
    nop
.org 0x091DEBB8
    j       MsgHook4
    nop


.headersize DATA_HEADERSIZE
.org EXT_CODE
.area EXT_CODE_END - EXT_CODE

MsgHook1:                           ; a1 = 테이블, a2 = 테이블 + 번호*2
    subu    a2, a2, a1
    sra     a2, a2, 1
    MsgEntry v0, a2, a1, a2
    j       0x091DB0CC
    nop
MsgHook2:                           ; v1 = 테이블, a1 = 번호
    MsgEntry v0, a1, v1, a1
    j       0x091DD994
    addu    v1, v1, v0              ; 덮어쓴 원래 명령
MsgHook3:                           ; t0 = 테이블, a1 = 번호
    MsgEntry a0, v1, t0, a1
    j       0x091DEB4C
    addu    a0, a0, t0              ; 덮어쓴 원래 명령
MsgHook4:                           ; a3 = 테이블, a0 = 번호
    MsgEntry v1, v0, a3, a0
    addu    v1, v1, a3
    addiu   v1, v1, 2
    jr      ra
    sw      v1, 0x34(a2)

.endarea

.close
