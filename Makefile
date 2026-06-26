.PHONY: check upload merge clean format lint lint-all typecheck typecheck-all tests tests-all build-raser-sandbox shell-raser-sandbox test-raser-sandbox build-raser-sif shell-raser-sif run-raser-sif-macos shell-raser-sif-macos

CHECK_PATHS ?= tests
ALL_CHECK_PATHS ?= src/raser tests

# Publish on pypi.org 
check: 
	python setup.py sdist
	twine check dist/* 
	
upload: 
	twine upload dist/* 
merge: 
	git remote update 
	git merge origin/main
	git merge upstream/main 

clean: 
	rm -rf dist raser.egg-info  

format:
	python -m ruff format $(CHECK_PATHS)

lint:
	python -m ruff check $(CHECK_PATHS)

lint-all:
	python -m ruff check $(ALL_CHECK_PATHS)

typecheck:
	python -m mypy $(CHECK_PATHS)

typecheck-all:
	python -m mypy $(ALL_CHECK_PATHS)

tests:
	python -m pytest -m "not root and not devsim and not geant4 and not ngspice and not hardware and not slow"

tests-all:
	python -m pytest

RASER_LIMA_INSTANCE ?= apptainer
RASER_SIF_COMMAND ?= /opt/raser/bin/raser signal HPK-Si-PiN
RASER_BOOTSTRAP_DEF ?= bootstrap/ubuntu/raser-ubuntu-sif.def
RASER_MKSQUASHFS_ARGS ?= -processors 1

build-raser-sandbox: 
	apptainer build --force --fakeroot --sandbox /tmp/raser-sandbox/ $(RASER_BOOTSTRAP_DEF)

shell-raser-sandbox:
	apptainer shell --env-file .raser/env --fakeroot -w /tmp/raser-sandbox 

test-raser-sandbox:
	apptainer shell --env-file .raser/env -B "$${BINDPATH:?source env/setup.sh first}" /tmp/raser-sandbox 

build-raser-sif:
	apptainer build --force --fakeroot --mksquashfs-args '$(RASER_MKSQUASHFS_ARGS)' raser.sif /tmp/raser-sandbox

shell-raser-sif:
	apptainer shell --env-file .raser/env -B "$${BINDPATH:?source env/setup.sh first}" raser.sif 

run-raser-sif-macos:
	limactl shell --workdir "$$(pwd)" $(RASER_LIMA_INSTANCE) sh -lc 'source env/setup.sh && apptainer exec --bind "$$BINDPATH" --env-file .raser/env "$$IMGFILE" $(RASER_SIF_COMMAND)'

shell-raser-sif-macos:
	limactl shell --workdir "$$(pwd)" $(RASER_LIMA_INSTANCE) sh -lc 'source env/setup.sh && apptainer shell --env-file .raser/env -B "$$BINDPATH" "$$IMGFILE"'
