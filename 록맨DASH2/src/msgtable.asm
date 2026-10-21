; 대사 테이블 항목 읽기 (EP1, EP2 공용)
;
; 테이블 형식 (tools/exe/msgtext.py)
;   2바이트 모드: [오프셋 u16 x (블록 수 + 1)]...
;   4바이트 모드: [FF FF 00 00][오프셋 u32 x (블록 수 + 1)]   (번역이 원래 자리에 안 들어간 테이블)
; 2바이트 모드의 첫 오프셋은 테이블 머리 크기라서 0xFFFF 가 될 수 없다.
;
; entry = index 번째 항목 주소, out = 그 오프셋 (테이블 시작 기준)
; entry 와 index 는 같은 레지스터여도 된다. out 은 다른 셋과 달라야 한다.

.macro MsgEntry, out, entry, table, index
    lhu     out, 0(table)
    xori    out, out, 0xFFFF
    bnez    out, @@short
    nop
    sll     entry, index, 2
    addu    entry, entry, table
    addiu   entry, entry, 4
    b       @@done
    lw      out, 0(entry)
@@short:
    sll     entry, index, 1
    addu    entry, entry, table
    lhu     out, 0(entry)
@@done:
.endmacro
