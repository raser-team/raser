#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
Description:  Run batch model     
@Date       : 2023/09/16 23:43:07
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu
@version    : 3.0
'''

import os
import sys
import subprocess
import grp
import pwd

from ..util.output import create_path

def main(destination_subfolder, command, batch_level, is_test):
    stat_info = os.stat("./")
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    user = pwd.getpwuid(uid)[0]
    group = grp.getgrgid(gid)[0]

    mem = 8000 * batch_level
 
    create_path("./output/{}/jobs".format(destination_subfolder))
    command_name = command.replace(" ","_").replace("/","_")
    jobfile_name = "./output/{}/jobs/".format(destination_subfolder)+command_name+".job"
    IMGFILE = os.environ.get('IMGFILE')
    raser_shell = "/usr/bin/apptainer exec --env-file .raser/env" + " " \
                + IMGFILE + " " \
                + "python3 -m src.raser"
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
    command = "hep_sub -o ./output/{}/jobs -e ./output/{}/jobs {} -mem {} -g {}".format(
        destination_subfolder, destination_subfolder, jobfile_name, mem, group)
    run_cmd(command, is_test)

def run_cmd(command, is_test=False):
    if is_test:
        sys.stdout.write(command+'\n')
        return 
    subprocess.run([command],shell=True)
    

if __name__ == "__main__":
    main(sys.argv[1],sys.argv[2])
