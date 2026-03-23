PROD = 1
OPT = $(if $(PROD:0=),0:1)
ONLY =
SRC_DIR = work:Documents/snake
TERMINAL_PORT = /dev/ttyUSB0
TERMINAL_BAUD = 9600

.PHONY: play
play: $(if $(ONLY:0=),,transfer)
	picocom $(TERMINAL_PORT) -b $(TERMINAL_BAUD)

.PHONY: transfer
transfer: OPT_ESC = $(if $(PROD:0=),--optimize-esc,)
transfer: Snake.atom remote-atom_transfer.py
	python3 atom_transfer.py --port $(TERMINAL_PORT) --baud $(TERMINAL_BAUD) $(OPT_ESC) --upload Snake.atom

Snake.atom: VARIANT = $(if $(PROD:0=),-DPROD,)
Snake.atom: OPTIMIZE = $(if $(OPT:0=),python3 optimize.py,tee)
Snake.atom: remote-Snake.abp remote-AcornAtom.abp remote-optimize.py
	cpp -P $(VARIANT) Snake.abp | $(OPTIMIZE) > Snake.atom

.PHONY: remote-%
remote-%:
	scp $(SRC_DIR)/$* .

.PHONY: mf
mf: remote-Makefile

.PHONY: print-%
print-%:
	@echo "$*=$($*)"

# scp work:Documents/snake/{optimize.py,atom_transfer.py,Snake.abp,AcornAtom.abp} . \
  && (cpp -P Snake.abp | python3 optimize.py > Snake.atom) \
  && python3 atom_transfer.py --port /dev/ttyUSB0 --upload Snake.atom \
  && picocom /dev/ttyUSB0 -b 9600

# scp work:Documents/snake/{optimize.py,atom_transfer.py,Snake.abp,AcornAtom.abp} .\
  && (cpp -DPROD -P Snake.abp | python3 optimize.py > Snake.atom) \
  && python3 atom_transfer.py --optimize-esc --port /dev/ttyUSB0 --upload Snake.atom \
  && picocom /dev/ttyUSB0 -b 9600
