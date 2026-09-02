# make            -> code.mif
# make MODEL=x.obj -> code.mif + model.mif
MODEL ?= house.obj
all: code.mif model.mif
code.mif: render.c hw.h crt0.S link.ld
	./build.sh
	python3 mkcode.py render.bin code.mif
model.mif: $(MODEL) conv.py mkmodel.py memmap.py
	python3 mkmodel.py $(MODEL) model.mif
clean:
	rm -f render.elf render.bin code.mif model.mif
