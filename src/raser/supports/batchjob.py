#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Description:  Run batch model
@Date       : 2023/09/16 23:43:07
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu
@version    : 3.0
"""

import os
import sys
import subprocess
import grp

from raser.supports.output import create_path
from raser.supports.paths import project_path

def main(destination_subfolder, command, batch_level, is_test):
    stat_info = os.stat("./")
    gid = stat_info.st_gid
    group = grp.getgrgid(gid)[0]

    mem = 8000 * batch_level

    job_dir = project_path(destination_subfolder, "jobs")
 
    create_path(job_dir)
    command_name = command.replace(" ","_").replace("/","_")
    jobfile_name = str(job_dir / (command_name+".job"))
    IMGFILE = os.environ.get('IMGFILE')
    raser_shell = ( "/usr/bin/apptainer exec --env-file .raser/env" + " " \
                + IMGFILE + " " \
                + "raser"
    )
    gen_job(jobfile_name, run_code=raser_shell+' '+command)
    submit_job(jobfile_name, destination_subfolder, group, mem, is_test=is_test)

def gen_job(jobfile_name, run_code):
    jobfile = open(jobfile_name, "w")
    jobfile.write(run_code)
    jobfile.close()
    print("Generate job file: ", jobfile_name)

def submit_job(jobfile_name, destination_subfolder, group, mem, is_test=False):
    print("Submit job file: ", jobfile_name)
    os.chmod(jobfile_name, 0o755)
    job_dir = project_path(destination_subfolder, "jobs")
    command = "hep_sub -o {} -e {} {} -mem {} -g {}".format(
        job_dir, job_dir, jobfile_name, mem, group)
    run_cmd(command, is_test)

def run_cmd(command, is_test=False):
    if is_test:
        sys.stdout.write(command+'\n')
        return 
    subprocess.run([command],shell=True)
    

if __name__ == "__main__":
    main(sys.argv[1],sys.argv[2])
