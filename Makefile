SRC_DIR = work:Documents/snake
CPP_DEFS = -DPROD
TERMINAL_PORT = /dev/ttyUSB0
TERMINAL_BAUD = 9600
OPT_ESC = $(if $(CPP_DEFS:-DPROD=),,--optimize-esc)

.PHONY: play
play: transfer
	picocom $(TERMINAL_PORT) -b $(TERMINAL_BAUD)

.PHONY: transfer
transfer: Snake.atom remote-atom_transfer.py
	python3 atom_transfer.py --port $(TERMINAL_PORT) --baud $(TERMINAL_BAUD) $(OPT_ESC) --upload Snake.atom

Snake.atom: remote-Snake.abp remote-AcornAtom.abp remote-optimize.py
	cpp -P $(CPP_DEFS) Snake.abp | python3 optimize.py > Snake.atom

.PHONY: remote-%
remote-%:
	scp $(SRC_DIR)/$* .

.PHONY: mf
mf: remote-Makefile

# scp work:Documents/snake/{optimize.py,atom_transfer.py,Snake.abp,AcornAtom.abp} . \
  && (cpp -P Snake.abp | python3 optimize.py > Snake.atom) \
  && python3 atom_transfer.py --port /dev/ttyUSB0 --upload Snake.atom \
  && picocom /dev/ttyUSB0 -b 9600

# scp work:Documents/snake/{optimize.py,atom_transfer.py,Snake.abp,AcornAtom.abp} .\
  && (cpp -DPROD -P Snake.abp | python3 optimize.py > Snake.atom) \
  && python3 atom_transfer.py --optimize-esc --port /dev/ttyUSB0 --upload Snake.atom \
  && picocom /dev/ttyUSB0 -b 9600
