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

RASER_LIMA_INSTANCE ?= apptainer
RASER_SIF_COMMAND ?= python -m src.raser signal HPK-Si-PiN
RASER_BOOTSTRAP_DEF ?= bootstrap/linux_x86/raser-linux-reference.def

build-login:
	ssh -Y [user]@lxlogin@ihep.ac.cn

build-raser-sandbox: 
	apptainer build --force --fakeroot --sandbox /tmp/raser-sandbox/ $(RASER_BOOTSTRAP_DEF)

build-raser-sandbox-arm64:
	$(MAKE) build-raser-sandbox RASER_BOOTSTRAP_DEF=bootstrap/linux_arm64/raser-linux-arm64-reference.def

shell-raser-sandbox:
	apptainer shell --env-file .raser/env --fakeroot -w /tmp/raser-sandbox 

test-raser-sandbox:
	apptainer shell --env-file .raser/env -B "$${BINDPATH:?source env/setup.sh first}" /tmp/raser-sandbox 

build-raser-sif:
	apptainer build --force --fakeroot raser.sif /tmp/raser-sandbox  

shell-raser-sif:
	apptainer shell --env-file .raser/env -B "$${BINDPATH:?source env/setup.sh first}" raser.sif 

run-raser-sif-macos:
	limactl shell --workdir "$$(pwd)" $(RASER_LIMA_INSTANCE) sh -lc 'source env/setup.sh && apptainer exec --bind "$$BINDPATH" --env-file .raser/env "$$IMGFILE" $(RASER_SIF_COMMAND)'

shell-raser-sif-macos:
	limactl shell --workdir "$$(pwd)" $(RASER_LIMA_INSTANCE) sh -lc 'source env/setup.sh && apptainer shell --env-file .raser/env -B "$$BINDPATH" "$$IMGFILE"'
