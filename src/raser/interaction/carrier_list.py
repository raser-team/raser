'''
Description:  carrier_list.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''

import ROOT
ROOT.gROOT.SetBatch(True)
class CarrierListFromG4P:
    def __init__(self, material, my_g4, batch):
        """
        Description:
            Events position and energy depositon
        Parameters:
            material : string
                deciding the energy loss of MIP
            my_g4 : G4Interaction
            batch : int
                batch = -1: Single event, select particle with long enough track
                batch != -1: Multi event, assign particle with batch number
        Modify:
            2022/10/25
        """
        if (material == "SiC"):
            self.energy_loss = 8.4 #ev
        elif (material == "Si"):
            self.energy_loss = 3.6 #ev
        elif(material == "Diamond"):
            self.energy_loss =13.1 #eV

        if batch == -1 and (my_g4.geant4_model == "time_resolution" or my_g4.geant4_model == "charge_collection" or my_g4.geant4_model == "bmos"  or my_g4.geant4_model == "beta_source"):
            total_step=0
            particle_number=0
            for p_step in my_g4.p_steps_current:   # selecting particle with long enough track
                if len(p_step)>1:
                    particle_number=1+particle_number
                    total_step=len(p_step)+total_step
            for j in range(len(my_g4.p_steps_current)):
                if(len(my_g4.p_steps_current[j])>((total_step/particle_number)*0.5)):
                    self.batch_def(my_g4,j)
                    my_g4.selected_batch_number=j
                    break
            if particle_number > 0:
                batch = 1

            if batch == -1:
                print("=========RASER info ===========\nGeant4:the sensor didn't have particles hitted\n==========================")
                raise ValueError
            
        elif batch == -1 and my_g4.geant4_model == "Si_strip":
            # P13 cut condition
            # TODO: specify device name
            h1 = ROOT.TH1F("Edep_device", "Energy deposition in Detector", 100, 0, max(my_g4.edep_devices)*1.1)
            for i in range (len(my_g4.edep_devices)):
                h1.Fill(my_g4.edep_devices[i])
            max_event_bin=h1.GetMaximumBin()
            bin_wide=max(my_g4.edep_devices)*1.1/100
            c=ROOT.TCanvas("c","c",700,500)
            h1.Draw()
            # c.SaveAs("./output/particle/edeptest.pdf")

            for j in range (len(my_g4.edep_devices)):
                #compare to experimental data
                if (my_g4.edep_devices[j]<0.084 and my_g4.edep_devices[j]>0.083):
                    try_p=1
                    for single_step in my_g4.p_steps_current[j]:
                        if abs(single_step[0]-my_g4.p_steps_current[j][0][0])>5:
                            try_p=0
                    if try_p==1:
                        self.batch_def(my_g4,j)
                        my_g4.selected_batch_number=j
                        batch = 1
                        break
                    
            if batch == -1:
                print("=========RASER info ===========\nGeant4:the sensor didn't have particles hitted\n==========================")
                raise ValueError
        else:
            my_g4.selected_batch_number=batch
            self.batch_def(my_g4,batch)

    def batch_def(self,my_g4,j):
        self.beam_number = j
        self.track_position = [[single_step[0],single_step[1],single_step[2],1e-9] for single_step in my_g4.p_steps_current[j]]
        self.tracks_step = my_g4.energy_steps[j]
        self.tracks_t_energy_deposition = my_g4.edep_devices[j] #为什么不使用？
        self.ionized_pairs = [step*1e6/self.energy_loss for step in self.tracks_step]

class PixelCarrierListFromG4P:
    def __init__(self, my_d,my_g4):
        """
        Description:
            Events position and energy depositon
        Parameters:
            material : string
                deciding the energy loss of MIP
            my_g4 : G4Interaction
            batch : int
                batch = 0: Single event, select particle with long enough track
                batch != 0: Multi event, assign particle with batch number
        Modify:
            2022/10/25
        """
        batch = len(my_g4.localpositions)
        layer = len(my_g4.ltz)
        material = my_d.material
        self.pixelsize_x = my_d.p_x
        self.pixelsize_y = my_d.p_y
        self.pixelsize_z = my_d.l_z
        
        if (material == "SiC"):
            self.energy_loss = 8.4 #ev
        elif (material == "Si"):
            self.energy_loss = 3.6 #ev
        elif (material == "C"):
            self.energy_loss = 13.1 #ev
        
        self.track_position, self.ionized_pairs= [],[]
        self.layer= layer
        for j in range(batch):
            self.single_event(my_g4,j)

    def single_event(self,my_g4,j):
        s_track_position,s_energy= [],[]
        for i in range(self.layer):
            position = []
            energy = []
            name = "Layer_"+str(i)
            #print(name)
            for k in range(len(my_g4.devicenames[j])):
                px,py,pz = self.split_name(my_g4.devicenames[j][k])
                if name in my_g4.devicenames[j][k]:
                    tp = [0 for i in range(3)]
                    tp[0] = my_g4.localpositions[j][k][0]+(px-0.5)*self.pixelsize_x
                    tp[1] = my_g4.localpositions[j][k][1]+(py-0.5)*self.pixelsize_y
                    tp[2] = my_g4.localpositions[j][k][2]+self.pixelsize_z/2
                    position.append(tp) 
                    energy.append(my_g4.energy_steps[j][k])
            s_track_position.append(position)
            pairs = [step*1e6/self.energy_loss for step in energy]
            s_energy.append(pairs)
            del position,energy
        self.track_position.append(s_track_position)
        self.ionized_pairs.append(s_energy)
        
    def split_name(self,volume_name):
        parts = volume_name.split('_')
        return int(parts[1]),int(parts[2]),int(parts[4])
