#!/bin/bash

p1_current(){

  source env/setup.sh
  repo_root=$(git rev-parse --show-toplevel)
  lumi_output="$repo_root/work/lumi/N0_3_4"
  mkdir -p "$lumi_output"
  cd src/raser/apps/lumi
  mkdir tmp_event_folder
  
  filename="$lumi_output/PossionHit.txt"
  
  count=0
  while IFS= read -r line
  do
      hE=$(echo "$line" | awk '{print $1}')
      hT=$(echo "$line" | awk '{print $NF}')
      hInfo=$(echo "$line" | awk '{$1=""; $NF=""; print $0}' | sed 's/^ //;s/ $//')
      
      mkdir -p "$lumi_output/event_$count"
  
      cp components/g4experiment/cflm_p1.json ./tmp_event_folder
      mv ./tmp_event_folder/cflm_p1.json ./tmp_event_folder/event_$count.json
      mv ./tmp_event_folder/event_$count.json "$lumi_output/event_$count"
  
      cp ./cflm_p1.py ./tmp_event_folder
      sed -i "s|output(__file__, \"N0_3_4\")|'$lumi_output/event_$count'|g" "./tmp_event_folder/cflm_p1.py"
      sed -i "s|component_path('g4experiment', 'cflm_p1.json')|'$lumi_output/event_$count/event_$count.json'|g" "./tmp_event_folder/cflm_p1.py"
      mv ./tmp_event_folder/cflm_p1.py ./tmp_event_folder/cflm_event_$count.py
      mv ./tmp_event_folder/cflm_event_$count.py .
  
      cp ./get_current_p1.py ./tmp_event_folder
      sed -i "s|component_path('g4experiment', 'cflm_p1.json')|'$lumi_output/event_$count/event_$count.json'|g" "./tmp_event_folder/get_current_p1.py"
      sed -i "s|cflm_p1|cflm_event_$count|g" "./tmp_event_folder/get_current_p1.py"
      mv ./tmp_event_folder/get_current_p1.py ./tmp_event_folder/get_current_event_$count.py
      mv ./tmp_event_folder/get_current_event_$count.py .
  
      cp ./poisson_generator_p1.py ./tmp_event_folder
      sed -i "s|output(__file__, \"N0_3_4\")|'$lumi_output/event_$count'|g" "./tmp_event_folder/poisson_generator_p1.py"
      sed -i "s|component_path('g4experiment', 'cflm_p1.json')|'$lumi_output/event_$count/event_$count.json'|g" "./tmp_event_folder/poisson_generator_p1.py"
      sed -i "s|cflm_p1|cflm_event_$count|g" "./tmp_event_folder/poisson_generator_p1.py"
      sed -i "s|get_current_p1|get_current_event_$count|g" "./tmp_event_folder/poisson_generator_p1.py"
      mv ./tmp_event_folder/poisson_generator_p1.py ./tmp_event_folder/poisson_event_$count.py
      mv ./tmp_event_folder/poisson_event_$count.py .
      
      echo "    if label == 'Event_p1_$count':" >> __init__.py
      echo "       from . import poisson_event_$count" >> __init__.py
      echo "       poisson_event_$count.main($hE, $hInfo, $hT)" >> __init__.py
  
      ((count++))    
  
  done < "$filename"
  
  cd -
  
  for ((i=0; i<count; i++)); do
      python src/raser -b lumi Event_p1_$i
  done
  
  rm -rf src/raser/apps/lumi/tmp_event_folder

}

p1_current
