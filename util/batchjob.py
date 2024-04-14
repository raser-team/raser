#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
Description:  Run batch model     
@Date       : 2023/09/16 23:43:07
@Author     : tanyuhang, Tao Yang, Chenxi Fu
@version    : 3.0
'''

import os
import sys
import subprocess
import grp
import pwd

def main(destination_subfolder, command, args):
    test = vars(args)['test'] 
    stat_info = os.stat("./")
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    user = pwd.getpwuid(uid)[0]
    group = grp.getgrgid(gid)[0]
 
    create_path("./output/{}/jobs".format(destination_subfolder))
    command_name = command.replace(" ","_").replace("/","_")
    jobfile_name = "./output/{}/jobs/".format(destination_subfolder)+command_name+".job"
    gen_job(jobfile_name,run_code='python3 raser'+' '+command)
    submit_job(jobfile_name,destination_subfolder,group,test=test)

def gen_job(jobfile_name,run_code):
    jobfile = open(jobfile_name,"w")
    jobfile.write(run_code)
    jobfile.close()
    print("Generate job file: ", jobfile_name)

def submit_job(jobfile_name,destination_subfolder,group, test=False):
    print("Submit job file: ", jobfile_name)
    os.chmod(jobfile_name, 0o755)
    command = "hep_sub -o ./output/{}/jobs -e ./output/{}/jobs {} -g {}".format(
        destination_subfolder,destination_subfolder,jobfile_name,group)
    run_cmd(command, test)

def create_path(path):
    """ If the path does not exit, create the path"""
    if not os.access(path, os.F_OK):
        os.makedirs(path, exist_ok=True) 

def run_cmd(command, test=False):
    if test:
        sys.stdout.write(command+'\n')
        return 
    subprocess.run([command],shell=True)
    

if __name__ == "__main__":
    main(sys.argv[1],sys.argv[2])