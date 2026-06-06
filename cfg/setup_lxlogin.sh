# Setup raser environment     
# Author SHI Xin <shixin@ihep.ac.cn>  
# Created [2023-08-31 Thu 08:36] 

if [ -z "$PS1" ]; then
    echo "Setting up raser ..."
fi

dir_raser=$(cd $(dirname $(dirname $BASH_SOURCE[0])) && pwd)
dir_geant4_data=/cvmfs/common.ihep.ac.cn/software/geant4/10.7.p02/data
GEANT4_INSTALL=/cvmfs/common.ihep.ac.cn/software/geant4/10.7.p02

cfg_env=$dir_raser/cfg/env
rm -f $cfg_env
cat << EOF >> $cfg_env
# PATH 
PATH=/cvmfs/common.ihep.ac.cn/software/hepjob/bin:/bin:\$PATH

# ROOT 
ROOTSYS=/usr/local/share/root_install

# Geant4 
GEANT4_INSTALL=$GEANT4_INSTALL/x86_64-centos7-gcc9-optdeb
G4ENSDFSTATEDATA=$dir_geant4_data/G4ENSDFSTATE2.3
G4PIIDATA=$dir_geant4_data/G4PII1.3
G4INCLDATA=$dir_geant4_data/G4INCL1.0
G4LEDATA=$dir_geant4_data/G4EMLOW7.13
G4PARTICLEXSDATA=$dir_geant4_data/G4PARTICLEXS3.1.1
G4NEUTRONHPDATA=$dir_geant4_data/G4NDL4.6
G4SAIDXSDATA=$dir_geant4_data/G4SAIDDATA2.0
G4REALSURFACEDATA=$dir_geant4_data/RealSurface2.2
G4ABLADATA=$dir_geant4_data/G4ABLA3.1
G4LEVELGAMMADATA=$dir_geant4_data/PhotonEvaporation5.7
G4RADIOACTIVEDATA=$dir_geant4_data/RadioactiveDecay5.6

# Python 
PYTHONPATH=/usr/local/share/root_install/lib:$GEANT4_INSTALL/install/lib64/python3.6/site-packages:/usr/local/share/acts_build/python
LD_LIBRARY_PATH=$GEANT4_INSTALL/x86_64-centos7-gcc9-optdeb/lib64:/usr/local/share/root_install/lib:/.singularity.d/libs

#pyMTL3 Verilator
PYMTL_VERILATOR_INCLUDE_DIR="/usr/local/share/verilator/include"
EOF

export PATH=/cvmfs/common.ihep.ac.cn/software/hepjob/bin:$PATH
export IMGFILE=/afs/ihep.ac.cn/users/c/chenguanxing/img/raser_latest.sif
export BINDPATH=/cvmfs,/etc/condor/condor_config,/etc/condor/config.d,/etc/redhat-release,/run/user,$HOME/.Xauthority,$HOME/.vscode-server,$HOME/vscode-container,$dir_raser
# notice: if home is binded, then the default path in the apptainer will change from current path to the home path
# $HOME/.Xauthority for G4 visualization, $HOME/.vscode-server and $HOME/.vscode-container for vscode remote development
# /run/user for vscode gui
# condor_config and redhat-release for hep_job
# For vscode users entering .sif, the symbol links should be converted into real paths

# 定义函数：将输入路径字符串中的软链接转换为真实路径，并按原顺序返回新字符串
resolve_and_reorder() {
    local input_str="$1"
    IFS=',' read -ra paths <<< "$input_str"  # 分割输入字符串为数组

    local resolved_paths=()
    for path in "${paths[@]}"; do
        # 检查路径是否为软链接，如果是则解析真实路径并添加，否则只添加原路径
        if [ -L "$path" ]; then
            resolved=$(readlink -f "$path")
            resolved_paths+=("$resolved")
        else 
            # 跳过不存在的路径
            if [ ! -e "$path" ]; then
                if [ -z "$PS1" ]; then
                    echo "Warning from raser setup: $path do not exist"
                fi
                continue
            fi
        fi
        resolved_paths+=("$path")
    done

    # 按原顺序重新拼接为逗号分隔的字符串
    IFS=','; echo "${resolved_paths[*]}"
}

export BINDPATH=$(resolve_and_reorder "$BINDPATH")

export RASER_SETTING_PATH=$dir_raser/setting

# temporary solution for scipy import error
export OPENBLAS_NUM_THREADS=1

alias raser-shell="apptainer shell --env-file $cfg_env -B $BINDPATH $IMGFILE"

raser_exec="apptainer exec --env-file $cfg_env -B $BINDPATH $IMGFILE"
raser_python="$raser_exec python3"

alias raser="$raser_python -m src.raser"
alias raser-test="$raser_python -m unittest discover -v -s src/raser/tests"
alias pytest="$raser_exec pytest"
alias raser-install="$raser_exec pip install -e ."  

alias drawfig="$raser_python misc/drawfig"
alias control="$raser_python misc/control"
alias mesh="$raser_python setting/detector"