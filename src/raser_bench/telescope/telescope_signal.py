# -*- encoding: utf-8 -*-
"""
Description:
    PixelDetector Telescope's analysis
@Date       : 2023/08/22
@Author     : Yiming Hu
@version    : 1.0
"""

import json
import math
import time
import os
from types import SimpleNamespace

import ROOT
ROOT.gROOT.SetBatch(True)
import numpy as np

from raser_bench.telescope.g4_interaction import TelescopeG4Interaction
from raser.core.seeding import stream
from raser.core.device.build_device import Detector
from raser.core.current.cal_current import electrode_names
from raser.core.current.currents import EventCurrents, append_currents
from raser.core.current.diffusion import ELEMENTARY_CHARGE, collect_by_diffusion, time_bin
from raser.core.deposit.deposits import Deposits, EventDeposits
from raser.core.deposit.deposits import read_deposits, write_deposits
from raser.core.deposit.ionization import PAIR_ENERGY_EV, ionized_pairs
from raser.core.deposit.mip_track import PAIRS_PER_UM
from raser.supports.output import output
from raser.supports.paths import app_file_path

class Telescope:
    def __init__(self,my_d,my_g4,my_c,path):
        """
        Description:
            Telescope spatical resolution analysis, only consider vertical layer, ignore alignment
        Parameters:
        ---------
        Hits : list[dict]
            key_name: LayerID->int
            key_value:  hitpositions ->list
        Clusters : list[dict]
            key_name: LayerID->int
            key_value:  clusterpositions ->list
        Residual : dict
            key_name: LayerID->int
            key_value:  residual ->list
        Resolution : dict
            key_name: LayerID->int
            key_value:  resolution ->list
        path : str
            folder of the residual pictures
        @Modify:
        ---------
            2023/08/18
        """	
        #batch mode of root
        ROOT.gROOT.SetBatch(True)
        #gemotry information, default unit is um, better read from json file 
        #paras
        self.pixelsize_x = my_d.p_x
        self.pixelsize_y = my_d.p_y
        self.pixelsize_z = my_d.l_z
        self.layer_z = my_g4.ltz
        self.seedcharge = my_g4.seedcharge
        self.path = path
        
        #IO and mid paras
        self.Clusters = []
        self.Clustersize = []
        self.HitsID = []    # [ {0:[[i,j],[i2,j2]], ...}, ...]
        self.Hits = []      
        self.Chisquare = []
        self.Residual = {}
        #self.kvalue= {}
        self.AveClustersize = {}
        self.Resolution_Tol = {}
        self.Resolution_DUT = {}
        
        self.readdata(my_c)
        self.cluster(self.Hits,self.Clusters,self.Clustersize)
        #
        self._res_loop(self.Clusters,self.Residual,self.Chisquare)
        self._ave_cluster(self.Clustersize,self.AveClustersize)
        #
        self.resolution(self.Residual,self.Resolution_Tol)
        self.swap_res(self.Resolution_Tol,self.Resolution_DUT)
        
        #print("multi_clusters_evts",self.multi_cluster)
        print("Tol_evts:",len(self.Clusters))
        print("Tol_Resulution of each DUT",self.Resolution_Tol)
        print("DUT_Resulution of each DUT",self.Resolution_DUT)
        print("Average Clustersize:",self.AveClustersize)
        #self.save()
    
    #read data from calcurrent object,and turn the pixel coordinate to the new coordinate
    def readdata(self,my_c):
        for evt in my_c.event:
            hitID = {}
            for layer in evt:
                t_d = evt[layer]
                if layer not in hitID:
                    hitID[layer] = []
                for i in range(len(t_d['index'])):
                    if t_d['charge'][i] >= self.seedcharge:
                        hitID[layer].append(t_d['index'][i])
            self.HitsID.append(hitID)
        self._postransform(self.HitsID,self.Hits)
        #print(self.HitsID)
        #print(self.Hits)
        
    #find the cluster from planes hit
    def cluster(self,Hits,Clusters,Clustersize):
        for t_Hit in Hits:
            t_Clusters = {}
            t_Clustersize = {}
            for layer in  t_Hit:
                t_island = island(t_Hit[layer],self.pixelsize_x,self.pixelsize_y)
                t_Clusters[layer] = t_island.getcluster()
                t_Clustersize[layer] = t_island.getclustersize()
            Clusters.append(t_Clusters)
            Clustersize.append(t_Clustersize)        
    
    #fit the track , get the residual of DUTs
    def fit(self,pos_x,pos_y,pos_z):
        #fit with root
        graphx = ROOT.TGraph()
        graphy = ROOT.TGraph()
        for i in range(len(pos_z)):
            graphx.SetPoint(i,pos_z[i],pos_x[i])
            graphy.SetPoint(i,pos_z[i],pos_y[i])
        fitFunc = ROOT.TF1("fitFunc", "[0] + [1]*x", 0, 300000)  # y = a + bx
        fitFunc.SetParameters(400*25, 0)
        
        graphx.Fit(fitFunc,"Q")
        intercept_x = fitFunc.GetParameter(0)
        slope_x = fitFunc.GetParameter(1)
        
        graphy.Fit(fitFunc,"Q")
        intercept_y = fitFunc.GetParameter(0)
        slope_y = fitFunc.GetParameter(1)
        
        '''
        canvas = ROOT.TCanvas("canvas", "TGraph", 800, 600)
        graphx.SetMarkerStyle(ROOT.kFullCircle)
        graphx.Draw()
        
        
        Name = "fit"+str(DUT)
        now = time.strftime("%Y_%m%d_%H%M")
        path = output(__file__, "taichu_v1", str(now))
        #print(path)
        
        """ If the path does not exit, create the path"""
        if not os.access(path, os.F_OK):
            os.makedirs(path) 
        
        canvas.SaveAs(os.path.join(path, Name+".png"))
        '''
        return slope_x,intercept_x,slope_y,intercept_y
        
    #find the least square track
    def tracking(self):
        pass
    
    #calculate total resolution, total resolution of each DUT made up by Telescope res& DUT res
    def resolution(self,Residual,Resolution_Tol):
        for layer in Residual:
            residualx = [point[0] for point in self.Residual[layer]]
            residualy = [point[1] for point in self.Residual[layer]]
            #kx = [point[0] for point in self.kvalue[layer]]
            #ky = [point[1] for point in self.kvalue[layer]]
            
            Name = "Layer_"+str(layer)
            Namex = Name+"_x"
            Namey = Name+"_y"
            #Namekx = Name+"_kx"
            #Nameky = Name+"_ky"
            
            xmin = self.pixelsize_x*3
            meanx,sigmax = self._draw_res(residualx,Namex,-xmin,xmin)
            meany,sigmay = self._draw_res(residualy,Namey,-xmin,xmin)
            #meankx,sigmakx = self._draw_res(kx,Namekx,-0.002,0.002)
            #meanky,sigmaky = self._draw_res(ky,Nameky,-0.002,0.002)
            
            Resolution_Tol[layer]=[sigmax,sigmay]
    
    #swap total resolution to DUT's  res
    def swap_res(self,Resolution_Tol,Resolution_DUT):
        N = len(self.layer_z)
        for i in range(N):
            k1,k2,kt = 0.0,0.0,0
            for j in range(N):
                t1  = (self.layer_z[i]-self.layer_z[j])/10000
                k1 += t1
                k2 += t1**2
            k1 = k1**2
            kt = 1/(N-float(k1/k2))
            # kt is the leverage of layer i in a line through all N layers; the
            # residual to a line through the other layers has the variance
            # sigma^2/(1-kt) when every layer has the resolution sigma
            Resolution_DUT[i] = [Resolution_Tol[i][0]*(1-kt)**0.5,Resolution_Tol[i][1]*(1-kt)**0.5,]
        
    #final data to be saved
    def save(self):
        pass
    # protected fun
    #transform the ID to position
    def _postransform(self,HitsID,Hits):
        for t_HitsID in HitsID:
            t_Hits = {}
            for layer in t_HitsID:
                t_x,t_y = 0,0
                for x,y in t_HitsID[layer]:
                    t_x = float((x+0.5)*self.pixelsize_x)
                    t_y = float((y+0.5)*self.pixelsize_y)
                    if layer not in t_Hits:
                        t_Hits[layer] = []
                    t_Hits[layer].append([t_x,t_y])
            Hits.append(t_Hits)
    #draw gauss distribution of residual 
    def _draw_res(self,data,Name,xmin=-100,xmax = 100):
        hist = ROOT.TH1D(Name, Name, 50, xmin, xmax)  
        x = data  
        for value in x:
            hist.Fill(value)

        fitFunc = ROOT.TF1("fitFunc", "gaus", xmin, xmax)  
        hist.Fit(fitFunc, "Q")
        
        mean = fitFunc.GetParameter(1)
        sigma = fitFunc.GetParameter(2)
        entries = int(len(x))
        canvas = ROOT.TCanvas("canvas", "Histogram and Fit", 800, 600)
        hist.SetStats(False)
        hist.Draw()
        label = ROOT.TPaveText(0.6, 0.7, 0.9, 0.9, "NDC")
        label.AddText("Entries: {}".format(entries))
        label.AddText("Mean: {:.3f}".format(mean))
        label.AddText("Sigma: {:.3f}".format(sigma))
        label.SetFillStyle(0)
        label.SetTextAlign(12)
        label.Draw()
        
        os.makedirs(self.path, exist_ok=True)
        canvas.SaveAs(os.path.join(self.path, Name+".png"))
        return mean,sigma
    #get ave clustersize
    def _ave_cluster(self,Clustersize,AveClustersize):
        t_size = [[] for i in range(6)]
        for evt in Clustersize:
            for layer in evt:
                for n in evt[layer]:
                    t_size[layer].append(n)
        
        for layer in range(len(t_size)):
            AveClustersize[layer] = float(sum(t_size[layer]))/len(t_size[layer])
    #reconstruction loop over each event
    def _res_loop(self,Clusters,Residual,Chisquare):
        self.count = 0
        self.multi_cluster = 0
        for evt in Clusters:       
            if self.count % 1000 == 0:
                print("Excuate process:",self.count,"/",len(Clusters))
            self.count+=1
            #tracking
            #simple choose of track, only 1 cluster all layer evt considered
            if len(evt)!=len(self.layer_z):
                self.multi_cluster+=1
                continue
            else:
                flag = 0
                for layer in evt:
                    if len(evt[layer])!=1:
                        flag = 1
                        break
                if flag == 1:
                    continue
            #fill the cluster_dict,after tracking, cluster_dict[layer]'s len must == 1
            cluster_dict = evt
            for layer in cluster_dict:
                if len(cluster_dict[layer]) != 1 :
                    print("Erro:layer's len isn't 1 after tracking")
                    raise
            #fit the evt
            chisquare = 0 
            for DUT in cluster_dict:
                pos_x = []
                pos_y = []
                pos_z = []
                for layer in cluster_dict:
                    if layer == DUT:
                        continue
                    for point in cluster_dict[layer]:
                        pos_x.append(point[0])
                        pos_y.append(point[1])
                    pos_z.append(self.layer_z[layer])
                kx,bx,ky,by = self.fit(pos_x,pos_y,pos_z)
                
                residualx = ( kx*(self.layer_z[DUT]+self.pixelsize_z/2)+bx-cluster_dict[DUT][0][0]
                )
                residualy = ( ky*(self.layer_z[DUT]+self.pixelsize_z/2)+by-cluster_dict[DUT][0][1]
                )
                if DUT not in Residual:
                    Residual[DUT] = []
                    #self.kvalue[DUT] = []
                Residual[DUT].append([residualx,residualy])
                #self.kvalue[DUT].append([kx,ky])
                
                chisquare += (residualx**2/(self.pixelsize_x**2/12))+(residualy**2/(self.pixelsize_y**2/12))
                
            Chisquare.append(chisquare)

#find the clusters from hit list, named by the classic dfs sample
class island:
    def __init__(self,hitlist,pixelsize_x,pixelsize_y):
        self.EPSINON = 0.0000001
        self.pixelsize_x = pixelsize_x
        self.pixelsize_y = pixelsize_y
        self.clusterlist = []
        self.clustersize = []   
        self.numOfislands =0
           
        self.t_island = hitlist
        island_tag = set()
        t_island_id = []
        
        self.t_island.sort(key=lambda point: (point[0], point[1]))

        numid = 0
        if self.t_island:
            t_island_id.append([0])

        for i in range(1, len(self.t_island)):
            if self.t_island[i][0] != self.t_island[i - 1][0]:
                t_island_id.append([i])
                numid += 1
            else:
                t_island_id[numid].append(i)    

        for i in range(len(t_island_id)):
            for j in range(len(t_island_id[i])):
                if t_island_id[i][j] not in island_tag:
                    x, y, n = self.dfs(island_tag, t_island_id, i, j,0.0,0.0,0)
                    self.numOfislands += 1
                    self.clusterlist.append([x / n,y / n])
                    self.clustersize.append(n)
    
    def dfs(self,t_set,id,i,j,xi,yi,ni):
        x,y,n = xi,yi,ni
        if not self.inArea(id, i, j):
            return x,y,n
        if id[i][j] in t_set:
            return x,y,n
        
        t_set.add(id[i][j])
        x += self.t_island[id[i][j]][0]
        y += self.t_island[id[i][j]][1]
        n += 1
        
        if self.inLink(id, i, j, i, j + 1):
            x,y,n = self.dfs(t_set, id, i, j + 1, x, y, n)  # up
        if self.inLink(id, i, j, i, j - 1):
            x,y,n = self.dfs(t_set, id, i, j - 1, x, y, n)  # down
        
        if self.inArea(id, i - 1, 0):
            for k in range(len(id[i - 1])):
                if self.inLink(id, i, j, i - 1, k):
                    x,y,n = self.dfs(t_set, id, i - 1, k, x, y, n)  # l
        
        if self.inArea(id, i + 1, 0):
            for k in range(len(id[i + 1])):
                if self.inLink(id, i, j, i + 1, k):
                    x,y,n = self.dfs(t_set, id, i + 1, k, x, y, n)  # r

        return x,y,n
    
    def inArea(self,id,i,j):
        return 0 <= i < len(id) and 0 <= j < len(id[i])
    
    def inLink(self,id,i,j,ii,jj):
        if not self.inArea(id, i, j) or not self.inArea(id, ii, jj):
            return False
        x = self.t_island[id[i][j]][0] - self.t_island[id[ii][jj]][0]
        y = self.t_island[id[i][j]][1] - self.t_island[id[ii][jj]][1]
        # criterion
        return x ** 2 + y ** 2 <= self.pixelsize_x ** 2 + self.pixelsize_y ** 2 + self.EPSINON
    
    def getcluster(self):
        return self.clusterlist
    
    def getclustersize(self):
        return self.clustersize


#interface to generate simple examples for  debugging
class PixelHitTest:
    def __init__(self,my_d,my_g4):
        self.event = []
        
        if my_d == 0:
            raise TypeError(my_d)
            
        self.layer_z = my_g4.ltz
        self.pixelsizex = my_d.p_x
        self.pixelsizey = my_d.p_y
        self.thickness = my_d.l_z
        
        self.laserz = 0
        self.laserx = self.pixelsizex/2
        self.lasery = self.pixelsizey/2
        self.generate(1000)
        
    def generate(self,Num):
        #dont let bx,by change by pixelsize
        bx,by = 512* 25.0,512* 25.0
        random_generator = stream("pixel_hit_test")
        min_value = -256.0* 25.0/(self.layer_z[5]-self.laserz)
        max_value = -min_value
        for i in range(Num):
            evt = {}
            kx = random_generator.Uniform(min_value, max_value)
            ky = random_generator.Uniform(min_value, max_value)
            tx = random_generator.Uniform(-self.laserx,self.laserx) 
            ty = random_generator.Uniform(-self.lasery,self.lasery)
            for j in range(len(self.layer_z)):
                Hit = {'index':[],'charge':[]}  
                x1 = kx*(self.layer_z[j]-self.laserz)+bx/2+tx
                x2 = kx*(self.layer_z[j]+self.thickness-self.laserz)+bx/2+tx
                y1 = ky*(self.layer_z[j]-self.laserz)+by/2+ty
                y2 = ky*(self.layer_z[j]+self.thickness-self.laserz)+by/2+ty
                t_list = self.get_grid_cells_for_rectangle(x1,y1,x2,y2)
                for item in t_list:
                    Hit['index'].append(item)
                    Hit['charge'].append(int(random_generator.Uniform(200, 1000)))
                evt[j] = Hit
            self.event.append(evt)
        #print(self.event)
    
    def get_grid_cells_for_rectangle(self,x1, y1, x2, y2):
        grid_cells = set()
        #random_generator = ROOT.TRandom()

        N = 5
        for i in range(N+1):
            grid_x = int((x1+i*(x2-x1)/N) // self.pixelsizex)
            grid_y = int((y1+i*(y2-y1)/N) // self.pixelsizey)
            grid_cells.add((grid_x, grid_y))
            '''
            tx,ty =random_generator.Uniform(0,1),random_generator.Uniform(0,1)
            if tx>0.95:
                grid_x +=1
            if tx<0.05:
                grid_x -=1
            if ty>0.95:
                grid_y +=1
            if ty<0.05:
                grid_y +=1
            grid_cells.add((grid_x, grid_y))
            '''
        t_list = [list(item) for item in grid_cells]
        #print(t_list)
        return t_list
    
DIFFUSION_STEP = 50e-12  # s, one random step of the diffusion
HIT_ELECTRONS = 0.2  # a pixel that collected more is a hit


def _setup():
    with open(app_file_path("raser_bench/telescope", "telescope.json")) as file:
        return json.load(file)


def _file(kwargs, name):
    """The file `name` of this job, in the point that holds its slice."""
    batch = kwargs["_slice_batch_paths"][name.split(".")[0]]
    return os.path.join(batch, "%s_%s.h5" % (name, kwargs.get("job_index") or 0))


SPEED_OF_LIGHT = 2.99792458e14  # um/s


def straight_tracks(my_d, setup, events):
    """Deposits of `events` straight tracks of the beam of `setup` through its layers.

    A track starts at par_in and its slopes are drawn like the directions of
    the beam. In every layer it leaves the energy of a MIP, in pieces no
    longer than maxstep [um] along z: no scattering, no fluctuation of the
    energy, no secondaries. The layers must not be rotated.
    """
    start, end = setup["par_in"], setup["par_out"]
    energy = PAIRS_PER_UM[my_d.material] * PAIR_ENERGY_EV[my_d.material] * 1.0e-6  # MeV/um
    pieces = math.ceil(my_d.l_z / setup["maxstep"])
    piece = my_d.l_z / pieces
    layers = list(setup["object"]["layer"].values())
    for layer in layers:
        if any(layer["rotation_xyz"]):
            raise ValueError(
                f"{layer['name']} is rotated: the fast mode has straight tracks "
                "through layers that face the beam only"
            )
    generator = stream("telescope_straight_tracks")
    records = []
    for number in range(int(events)):
        slope_x = (end[0] - start[0] + generator.Uniform(-setup["par_randx"], setup["par_randx"])) / (end[2] - start[2])
        slope_y = (end[1] - start[1] + generator.Uniform(-setup["par_randy"], setup["par_randy"])) / (end[2] - start[2])
        record = EventDeposits(number, [], [], [], [], [], [])
        for layer in layers:
            for k in range(pieces):
                in_layer = (k + 0.5) * piece
                along = layer["position_z"] - my_d.l_z / 2 + in_layer - start[2]
                record.detector.append(layer["name"])
                record.x.append(start[0] + slope_x * along - layer["position_x"] + my_d.l_x / 2)
                record.y.append(start[1] + slope_y * along - layer["position_y"] + my_d.l_y / 2)
                record.z.append(in_layer)
                record.t.append(along / SPEED_OF_LIGHT)
                record.e.append(energy * piece)
        records.append(record)
    return records


def collect_under(my_d, pairs, positions, step):
    """The charge of one event when every deposit is collected at once by the
    pixel it lies in; a deposit outside the pixels is lost. Parameters and
    returns as collect_by_diffusion, without the window."""
    t0 = min((position[3] for position in positions), default=0.0)
    last = max((position[3] for position in positions), default=0.0)
    electrons = np.zeros((my_d.x_ele_num * my_d.y_ele_num, time_bin(last, t0, step) + 1))
    for n_pairs, (x, y, z, t) in zip(pairs, positions, strict=True):
        i, j = int(x // my_d.p_x), int(y // my_d.p_y)
        if 0 <= i < my_d.x_ele_num and 0 <= j < my_d.y_ele_num and 0 <= z <= my_d.l_z:
            electrons[i * my_d.y_ele_num + j, time_bin(t, t0, step)] += n_pairs
    charge = -ELEMENTARY_CHARGE * electrons.sum(axis=1)
    return t0, -ELEMENTARY_CHARGE * electrons / step, charge


def deposits(kwargs):
    """The beam through the layers of telescope.json: deposit_<job>.h5.

    The mode full is Geant4, fast is straight_tracks. Every generated
    event is recorded, also one that left nothing. The detector of a deposit
    is the name of its layer; x, y, z are in the coordinates of that layer,
    from its corner and its lower face.
    """
    my_d = Detector("TAICHU3")
    if kwargs["mode"] == "fast":
        events = straight_tracks(my_d, _setup(), kwargs["events_per_job"])
        for record in events:
            record.pairs, _ = ionized_pairs(record, my_d.material)
        write_deposits(
            _file(kwargs, "deposit"),
            Deposits(int(kwargs["events_per_job"]), {}, "any", None, events),
        )
        return
    my_g4 = TelescopeG4Interaction(
        my_d, "telescope", kwargs["seed"], int(kwargs["events_per_job"])
    )
    events = []
    for number, names, positions, energies, times in zip(
        my_g4.eventIDs,
        my_g4.devicenames,
        my_g4.localpositions,
        my_g4.energy_steps,
        my_g4.time_steps,
        strict=True,
    ):
        record = EventDeposits(int(number), [], [], [], [], [], [])
        for name, local, energy, time in zip(names, positions, energies, times, strict=True):
            # pixels are named <type>_<row>_<column>_<layer>
            _, row, column, layer = name.split("_", 3)
            record.detector.append(layer)
            record.x.append(local[0] + (int(column) + 0.5) * my_d.p_x)
            record.y.append(local[1] + (int(row) + 0.5) * my_d.p_y)
            record.z.append(local[2] + my_d.l_z / 2)
            record.t.append(time)
            record.e.append(energy)
        record.pairs, _ = ionized_pairs(record, my_d.material)
        events.append(record)
    write_deposits(
        _file(kwargs, "deposit"), Deposits(my_g4.generated_events, {}, "any", None, events)
    )


class DiffusedCharge:
    """The electrons every pixel of every layer collects, written layer by
    layer to `paths` as the currents of that layer. `collect` gives the
    charge of one layer and event: (pairs, positions) -> (t0, current, charge).

    An event without a deposit in a layer has no row in the file of that layer.

    event : one dict per event, layer number -> {'index': [[i, j], ...], 'charge': [...]},
        the pixels of the layer that collected electrons and how many
    last : (x_ele_num, y_ele_num) array, the electrons of the last layer of
        the last event
    """
    def __init__(self, my_d, events, paths, collect):
        names = electrode_names(my_d.read_out_contact, my_d.x_ele_num * my_d.y_ele_num)
        self.event = [{} for _ in events]
        for number, (layer, path) in enumerate(paths.items()):
            if os.path.exists(path):
                os.remove(path)
            for record, layers in zip(events, self.event, strict=True):
                mine = [k for k, name in enumerate(record.detector) if name == layer]
                pairs = [record.pairs[k] for k in mine]
                positions = [[record.x[k], record.y[k], record.z[k], record.t[k]] for k in mine]
                t0, current, charge = collect(pairs, positions)
                if mine:
                    append_currents(
                        path,
                        names,
                        DIFFUSION_STEP,
                        EventCurrents(record.event, t0, current, charge, sum(pairs)),
                    )
                electrons = (-charge / ELEMENTARY_CHARGE).reshape(my_d.x_ele_num, my_d.y_ele_num)
                fired = np.argwhere(electrons > HIT_ELECTRONS)
                layers[number] = {
                    "index": fired.tolist(),
                    "charge": [float(electrons[i, j]) for i, j in fired],
                }
                self.last = electrons


def currents(kwargs):
    """The deposits of every layer collected by its pixels: currents.<layer>_<job>.h5,
    one file per layer. The mode full is collect_by_diffusion, fast is
    collect_under. The charge of the last layer of the last event and the
    residuals of every layer are drawn in plots/job_<job>.

    The hits, clusters and residuals are still made here, from the charges
    just collected, until the analysis reads the files.
    """
    my_d = Detector("TAICHU3")
    setup = _setup()
    my_g4 = SimpleNamespace(ltz=setup["ltz"], seedcharge=setup["seedcharge"])
    paths = {
        layer: _file(kwargs, "current." + layer) for layer in setup["object"]["layer"]
    }
    if kwargs["mode"] == "fast":
        def collect(pairs, positions):
            return collect_under(my_d, pairs, positions, DIFFUSION_STEP)
    else:
        def collect(pairs, positions):
            return collect_by_diffusion(
                my_d, pairs, positions, setup["collection_window_s"], DIFFUSION_STEP
            )
    my_hit_charge = DiffusedCharge(
        my_d, read_deposits(_file(kwargs, "deposit")).events, paths, collect
    )
    plots = os.path.join(
        os.path.dirname(kwargs["_slice_batch_paths"]["current"]),
        "plots",
        "job_%s" % (kwargs.get("job_index") or 0),
    )
    draw_charge(my_hit_charge, plots)
    Telescope(my_d, my_g4, my_hit_charge, plots)


def draw_charge(my_charge, path):
    os.makedirs(path, exist_ok=True)
    c=ROOT.TCanvas("c","canvas1",1000,1000)
    c.cd()
    c.Update()
    c.SetLeftMargin(0.12)
    # c.SetTopMargin(0.12)
    c.SetRightMargin(0.12)
    c.SetBottomMargin(0.14)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptStat(0)

    n_x, n_y = my_charge.last.shape
    sum_charge = ROOT.TH2F("charge", "Pixel Detector charge", n_x, 0, n_x, n_y, 0, n_y)
    for i, j in np.argwhere(my_charge.last > 0):
        sum_charge.SetBinContent(int(i) + 1, int(j) + 1, float(my_charge.last[i, j]))
    sum_charge.GetXaxis().SetNdivisions(510)
    sum_charge.GetYaxis().SetNdivisions(505)
    sum_charge.GetXaxis().SetTitle("X")
    sum_charge.GetYaxis().SetTitle("Y")

    sum_charge.Draw("lego")
    c.Update()
    c.SaveAs(path+"/Pixel_charge.pdf")
    c.SaveAs(path+"/Pixel_charge.root")

def taichu_v2(label=""):
    #virtual object
    class MyObject:
        pass
    #output 
    res = []
    psize = []
    N = 25
    MaxSize = 25.0
    now = time.strftime("%Y_%m%d_%H%M")
    path = output(__file__, "taichu_v2", str(now))
    for i in range(N):
        t_my_d = MyObject()
        t_my_d.p_x = MaxSize*(i+1)/N
        t_my_d.p_y = MaxSize*(i+1)/N
        t_my_d.l_z = 200.0
        t_my_g = MyObject()
        t_my_g.seedcharge = 100
        t_my_g.ltz = [20000.0, 60000.0, 100000.0, 140000.0, 180000.0, 220000.0]
        psize.append(t_my_d.p_x)
        my_hit_test = PixelHitTest(t_my_d, t_my_g)
        my_telescope_test = Telescope(
            t_my_d, t_my_g, my_hit_test, os.path.join(path, "pixel_%g" % t_my_d.p_x)
        )
        res.append(my_telescope_test.Resolution_Tol[2][0])

    graph = ROOT.TGraph()
    for i in range(len(psize)):
        graph.SetPoint(i,psize[i],res[i])

    canvas = ROOT.TCanvas("canvas", "TGraph", 800, 600)
    graph.SetMarkerStyle(ROOT.kFullCircle)
    graph.GetYaxis().SetTitle("Resolution [um]")
    graph.GetYaxis().CenterTitle()  
    graph.GetXaxis().SetTitle("Pixel Size [um]")
    graph.GetXaxis().CenterTitle()  

    legend = ROOT.TLegend(0.27,0.67,0.62,0.80)
    legend.SetTextSize(0.04)
    legend.AddEntry(graph,label)

    canvas.SetGrid() 

    graph.Draw("APL")
    legend.Draw()

    canvas.Draw()
    Name = "Res vs size"
    canvas.SaveAs(os.path.join(path, Name+".png"))
