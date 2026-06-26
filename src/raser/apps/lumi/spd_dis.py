import ROOT
import json
import multiprocessing
import os
from . import cflm_spd

def main():

    root_path = 'src/raser/apps/lumi/input/datafile_p1.root'
    g4_json_path = os.getenv("RASER_SETTING_PATH")+"/g4experiment/cflm_spd.json"
    
    root_file = ROOT.TFile(root_path, "READ")
    tree = root_file.Get("electrons")
    
    def worker_function(queue, lock, j):
        try:
            print(f"运行 loop_solver:{j}")
            result_message = "Execution completed successfully"
            cflm_spd.main()   # cflm_spd.json 'vis' item must be 0, please check it !!!
        except Exception as e:
            result_message = f"Error: {e}"
        with lock:
            queue.put(result_message)
    lock = multiprocessing.Lock()
    queue = multiprocessing.Queue()
    
    for i in range(tree.GetEntries()):
        
        pos, mom, energy = [], [], []
        tree.GetEntry(i)
        
        pos.append([tree.pos_x, tree.pos_y, tree.pos_z])
        mom.append([tree.px, tree.py, tree.pz])
        energy.append(tree.s_energy) 

        with open(g4_json_path, 'r') as file:
            g4_dic = json.load(file)    
            g4_dic['par_in']      = pos
            g4_dic['par_direct']  = mom
            g4_dic['par_energy']  = energy
            g4_dic['PosBaseName'] = f"SecondaryParticle_{i}"   
            updated_g4_dic = json.dumps(g4_dic, indent=4)

        with open(g4_json_path, 'w') as file:
             file.write(updated_g4_dic)

        p = multiprocessing.Process(target=worker_function, args=(queue, lock, i))
        p.start()
        p.join()
        
        while not queue.empty():
            output_info = queue.get() 
            print("队列输出:", output_info)  # 确认输出内容
            if output_info is None:
                print("警告: worker_function 返回了 None,可能发生了错误!")

if __name__ == '__main__':
    main()  