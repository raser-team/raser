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

build-login:
	ssh -Y [user]@lxlogin@ihep.ac.cn

build-raser-sandbox: 
	apptainer build --force --fakeroot --sandbox /tmp/raser-sandbox/ bootstrap/linux_x86/raser-linux-reference.def

shell-raser-sandbox:
	apptainer shell --env-file .raser/env --fakeroot -w /tmp/raser-sandbox 

test-raser-sandbox:
	apptainer shell --env-file .raser/env -B /afs,/besfs5,/cefs,/cvmfs,/etc/condor/,/etc/redhat-release,/publicfs,/scratchfs,/workfs2 /tmp/raser-sandbox 

build-raser-sif:
	apptainer build --force --fakeroot raser.sif /tmp/raser-sandbox  

shell-raser-sif:
	apptainer shell --env-file .raser/env -B /afs,/besfs5,/cefs,/cvmfs,/etc/condor/,/etc/redhat-release,/publicfs,/scratchfs,/workfs2 raser.sif 
