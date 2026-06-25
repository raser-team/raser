#!/usr/bin/env bash        
# Install raser and setup environment     
# Author SHI Xin <shixin@ihep.ac.cn>  
# Created [2023-04-09 Sun 16:13] 


tmpdir=/scratchfs/atlas/$USER 
cd $tmpdir 

echo "clone raser ..."
git clone git@code.ihep.ac.cn:$USER/raser.git 
cd raser
git remote add upstream git@code.ihep.ac.cn:raser/raser.git 
cd 
ln -s $tmpdir/raser . 

echo "link vscode-server"
mv .vscode-server $tmpdir 
ln -s $tmpdir/.vscode-server  .  


