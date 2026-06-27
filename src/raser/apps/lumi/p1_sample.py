import os
import random
import ROOT
from raser.supports.output import output

def main():
    
    output_path = output(__file__, "N0_3_4")
    
    random.seed(3020122)                # process list using python random  
    rand = ROOT.TRandom3(3020122)       # generate Poisson distribution using ROOT random
    average_hit = 3.06
    total_samples = 100000
    hitnumber = []


    for i in range(total_samples):
        hitnumber.append(rand.Poisson(average_hit))
    
    hist = ROOT.TH1F("hist", "One-Dimensional Histogram", 10000, -5, 15)

    for num in hitnumber:
        hist.Fill(num)

    cp = ROOT.TCanvas("cp", "cp", 800, 600)
    hist.Draw()

    cp.SaveAs(os.path.join(output_path, 'poisson_dis.pdf'))

    file = ROOT.TFile("src/raser/apps/lumi/input/datafile_p1.root", "READ")
    tree = file.Get("electrons")

    pos, mom, energy = [], [], []
    TotalHitInfo = [] 
    
    for i in range(tree.GetEntries()):

        tree.GetEntry(i)
        pos.append([tree.pos_x, tree.pos_y, tree.pos_z])
        mom.append([tree.px, tree.py, tree.pz])
        energy.append(tree.s_energy) 

    for k in range(len(pos)):
        TotalHitInfo.append([pos[k], mom[k], energy[k]])
    
    random.shuffle(TotalHitInfo)

    sampleNumber = 804
    randomhit = random.sample(hitnumber, sampleNumber)

    time_table = []
    
    for l in range(0, 268):
        time_table.append(l*600)
    for y in range(0, 268):
        time_table.append(y*600+333373)
    for p in range(0, 268):
        time_table.append(p*600+666746)

    with open(os.path.join(output_path, 'PossionHit.txt'), 'w') as PossionHitFile:      
         for i in range(len(randomhit)):
             if randomhit[i] == 0:
                  PossionHitFile.write(f'{randomhit[i]} {999} {time_table[i]}\n')
             else:
                  randomHitInfo = random.sample(TotalHitInfo, randomhit[i])
                  PossionHitFile.write(f'{randomhit[i]} {randomHitInfo} {time_table[i]}\n')

if __name__ == '__main__':
    main()    
