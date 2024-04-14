# -*- encoding: utf-8 -*-
'''
Description: 
    PixelDetector Telescope's analysis  
@Date       : 2023/08/22
@Author     : yiminghu
@version    : 1.0
'''
import ROOT
import time
import os
import acts
import numpy as np

class telescope:
    def __init__(self,my_d,my_c):
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
        self.pixelsize_z = my_d.p_z
        self.layer_z = my_d.lt_z
        self.seedcharge = my_d.seedcharge
        
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
        path = os.path.join("fig", str(now),'' )
        #print(path)
        
        """ If the path does not exit, create the path"""
        if not os.access(path, os.F_OK):
            os.makedirs(path) 
        
        canvas.SaveAs(path+Name+".png")
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
            Resolution_DUT[i] = [Resolution_Tol[i][0]/(kt+1),Resolution_Tol[i][1]/(kt+1)]
        
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
        
        now = time.strftime("%Y_%m%d_%H%M")
        path = os.path.join("fig", str(now),'' )
        #print(path)
        
        """ If the path does not exit, create the path"""
        if not os.access(path, os.F_OK):
            os.makedirs(path) 
        
        canvas.SaveAs(path+Name+".png")
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
            if(len(evt)!=len(self.layer_z)):
                self.multi_cluster+=1
                continue
            else:
                flag = 0
                for layer in evt:
                    if(len(evt[layer])!=1):
                        flag = 1
                        break
                if(flag == 1):
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
                
                residualx = kx*(self.layer_z[DUT]+self.pixelsize_z/2)+bx-cluster_dict[DUT][0][0]
                residualy = ky*(self.layer_z[DUT]+self.pixelsize_z/2)+by-cluster_dict[DUT][0][1]
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
class Test:
    def __init__(self,my_d):
        self.event = []
        
        if my_d == 0:
            raise TypeError(my_d)
            
        self.layer_z = my_d.lt_z
        self.pixelsizex = my_d.p_x
        self.pixelsizey = my_d.p_y
        self.thickness = my_d.p_z
        
        self.laserz = 0
        self.laserx = self.pixelsizex/2
        self.lasery = self.pixelsizey/2
        self.generate(1000)
        
    def generate(self,Num):
        #dont let bx,by change by pixelsize
        bx,by = 512*25.,512*25.
        random_generator = ROOT.TRandom()
        min_value = -256.*25./(self.layer_z[5]-self.laserz)
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
    
def main(my_d):
    my_c = Test(my_d)
    tel = telescope(my_d,my_c)
    return tel.Resolution_Tol[2][0]
    
if __name__ == '__main__':
    start = time.time()
    main()
    print("drift_total1:%s"%(time.time()-start))
    print("RUN END")
    os._exit(0) 