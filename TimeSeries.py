#-*- coding: utf-8 -*-

import numpy as np
from scipy.stats import nanmedian
import tsinsar as ts
import shutil
import h5py



class TimeSeries:
    """
    Abstract class for all time series data objects.
    """

    def __init__(self, name="Time series", stnfile=None, dtype=None):

        self.name = name
        self.dtype = dtype

        # Read station/groundpoint locations from file       
        if stnfile is not None:
            ext = stnfile.split('.')[1]
            if ext == 'txt':
                name,lat,lon,elev = ts.tsio.textread(stnlist, 'S F F F')
            elif ext == 'h5':
                with h5py.File(stnfile, 'r') as ifid:
                    name = ifid['name'].value
                    lat = ifid['name'].value
                    lon = ifid['lon'].value
                    elev = ifid['elev'].value
            else:
                assert False, 'Input station file has an unsupported extension'

        # Determine the components depending on the datatype
        if self.dtype.lower() == 'gps':
            self.components = ['east', 'north', 'up']
        elif self.dtype.lower() in ['edm', 'insar']:
            self.components = ['los']
        else:
            assert False, 'Unsupported data type. Must be gps, edm, or insar'
        self.ncomp = len(self.components)

        self.h5file = self.output_h5file = None

        return


    def __del__(self):
        """
        Make sure to close any H5 file.
        """
        if type(self.h5file) is h5py.File:
            print('Finished processing. Closing H5 file')
            self.h5file.close()
        elif type(self.h5file) is dict and self.output_h5file is not None:
            print('Finished processing. Saving H5 file')
            self._saveh5(self.output_h5file, self.h5file)
        return


    def clear(self):
        """
        Clears entries for station locations and names.
        """
        for attr in ('name', 'lat', 'lon', 'elev'):
            setattr(self, attr, [])
        self.nstat = 0
        return


    def loadStationDict(self, inputDict):
        """
        Transfers data from a dictionary of station classes to self.
        """
        self.clear()
        for statname, stat in inputDict.items():
            self.name.append(statname)
            self.lat.append(stat.lat)
            self.lon.append(stat.lon)
            self.elev.append(stat.elev)
        self.name = np.array(self.name)
        self.lat,self.lon,self.elev = [np.array(lst) for lst in [self.lat,self.lon,self.elev]]
        self.nstat = self.lat.size
        self.statDict = inputDict
        self.statGen = ((statname, stat) for (statname, stat) in self.statDict.items()
                         if statname != 'tdec')

        return


    def loadStationH5(self, h5file, fileout=None, copydict=False):
        """
        Transfers data from an h5py data stack to self.
        """
        self.clear()

        # If user specifies an output file, we copy the input file and open
        # the output in read/write mode
        if fileout is None:
            if copydict:
                self.h5file = self._loadh5(h5file)
            else:
                self.h5file = h5py.File(h5file, 'r')
        else:
            shutil.copyfile(h5file, fileout)
            # Load all data into a python dictionary
            if copydict:
                self.h5file = self._loadh5(h5file)
                self.output_h5file = fileout
            else:
                self.h5file = h5py.File(fileout, 'r+')
        self.statDict = self.h5file

        # Make a generator to loop over station data
        self.statGen = list((statname, stat) for (statname, stat) in self.h5file.items()
                             if statname != 'tdec')


        # Get the data
        for statname, stat in self.statGen:
            self.name.append(statname.lower())
            if type(stat['lat']) in [h5py.Dataset, h5py.Group]:
                self.lat.append(stat['lat'].value)
                self.lon.append(stat['lon'].value)
                self.elev.append(stat['elev'].value)
            else:
                self.lat.append(stat['lat'])
                self.lon.append(stat['lon'])
                self.elev.append(stat['elev'])
        self.name = np.array(self.name)
        self.lat,self.lon,self.elev = [np.array(lst) for lst in [self.lat,self.lon,self.elev]]
        self.nstat = self.lat.size
        self.tdec = np.array(self.h5file['tdec'])
        
        return


    @staticmethod
    def _loadh5(h5file):
        """
        Load data from an H5 file into a dictionary.
        """
        data = {}
        with h5py.File(h5file, 'r') as h5file:
            for key, value in h5file.items():
                if type(value) == h5py.Group:
                    group = {}
                    for gkey, gvalue in value.items():
                        group[gkey] = gvalue.value
                    data[key] = group
                else:
                    data[key] = value.value
        return data
        

    @staticmethod
    def _saveh5(h5file, data):
        """
        Save a data stored in dictionary to H5 file.
        """
        with h5py.File(h5file, 'w') as hfid:
            for key, value in data.items():
                if type(value) is dict:
                    Group = hfid.create_group(key)
                    for gkey, gvalue in value.items():
                        Group[gkey] = gvalue
                else:
                    hfid[key] = value
        return


    def zeroMeanDisplacements(self):
        """
        Remove the mean of the finite values in each component of displacement.
        """
        from scipy.stats import nanmean
        for statname, stat in self.statGen:
            for component in self.components:
                dat = getattr(self, component)
                dat -= nanmean(dat)
        return
           

    def getDataArrays(self, order='columns'):
        """
        Traverses the station dictionary to construct regular sized arrays for the
        data and weights.
        """
        assert self.statDict is not None, 'must load station dictionary first'

        # Get first station to determine the number of data points
        for statname, stat in self.statGen:
            dat = getattr(stat, self.components[0])
            ndat = dat.size
            break 

        # Construct regular arrays and fill them
        data = np.empty((ndat, self.nstat*self.ncomp))
        weights = np.empty((ndat, self.nstat*self.ncomp))
        j = 0
        for component in self.components:
            for statname, cnt in zip(self.name, range(self.nstat)):
                stat = self.statDict[statname]
                compDat = getattr(stat, component)
                compWeight = getattr(stat, 'w_' + component)
                data[:,j] = compDat
                weights[:,j] = compWeight
                j += 1
        
        if order == 'rows':
            return data.T.copy(), weights.T.copy()
        else:
            return data, weights


    def computeNetworkWeighting(self, smooth=1.0, n_neighbor=3, L0=None):
        """
        Computes the network-dependent spatial weighting based on station/ground locations.
        """
        import topoutil as tu

        dist_weight = np.zeros((self.nstat, self.nstat))
        # Loop over stations
        rad = np.pi / 180.0
        for i in range(self.nstat):
            ref_X = tu.llh2xyz(self.lat[i]*rad, self.lon[i]*rad, self.elev[i])
            stat_dist = np.zeros((self.nstat,))
            # Loop over other stations
            for j in range(self.nstat):
                if j == i:
                    continue
                curr_X = tu.llh2xyz(self.lat[j]*rad, self.lon[j]*rad, self.elev[j])
                # Compute distance between stations
                stat_dist[j] = np.linalg.norm(ref_X - curr_X)
            if L0 is None:
                # Mean distance to 3 nearest neighbors multipled by a smoothing factor
                Lc = smooth * np.mean(np.sort(stat_dist)[1:1+n_neighbor])
                dist_weight[i,:] = np.exp(-stat_dist / Lc)
                print(' - scale length at', self.name[i], ':', 0.001 * Lc, 'km')
            else:
                dist_weight[i,:] = np.exp(-stat_dist / L0)

        return dist_weight


    def filterData(self, kernel_size, mask=False, statnames=[]):
        """
        Call median filter function.
        """
        from progressbar import ProgressBar, Bar, Percentage

        if kernel_size % 2 == 0:
            kernel_size += 1
        print('Window of integer size', kernel_size)
        if len(statnames) == 0:
            statnames = self.name

        pbar = ProgressBar(widgets=[Percentage(), Bar()], maxval=self.nstat).start()
        for scnt, (statname, stat) in enumerate(self.statGen):
            if statname not in statnames:
                continue
            for comp in self.components:
                dat = stat[comp].value
                wgt = stat['w_' + comp].value
                filtered = self.adaptiveMedianFilt(dat, kernel_size)
                if mask:
                    ind = np.isnan(dat) * np.isnan(wgt)
                    filtered[ind] = np.nan
                stat['filt_' + comp] = filtered
            pbar.update(scnt + 1)
        pbar.finish()
       
        return


    def decompose(self, n_comp=1, plot=False, method='pca', dmod=''):
        """
        Peform principal component analysis on a stack of time series.
        """

        # First fill matrices with zero-mean time series for PCA
        Adict = {}
        for comp in self.components:
            Adict[comp] = np.zeros((self.tdec.size, self.nstat))
            for j, (statname, stat) in enumerate(self.statGen):
                dat = stat[dmod + comp].value
                dat -= np.nanmean(dat)
                ind = np.isnan(dat).nonzero()[0]
                dat[ind] = np.nanstd(dat) * np.random.randn(len(ind))
                Adict[comp][:,j] = dat

        from sklearn.decomposition import FastICA, PCA
        if method == 'pca':
            decomposer = PCA(n_components=n_comp, whiten=False)
        elif method == 'ica':
            decomposer = FastICA(n_components=n_comp, whiten=True, max_iter=500)
        else:
            raise NotImplementedError('Unsupported decomposition method')
        
        # Now decompose the time series
        spatial = {}
        temporal = {}
        for comp in self.components:
            temporal[comp] = decomposer.fit_transform(Adict[comp])
            if method == 'pca':
                spatial[comp] = decomposer.components_.squeeze()
            elif method == 'ica':
                spatial[comp] = decomposer.mixing_[:,n_comp-1].squeeze()


        if plot:
            import matplotlib.pyplot as plt
            ax1 = plt.subplot2grid((3,2), (0,0))
            ax2 = plt.subplot2grid((3,2), (1,0))
            ax3 = plt.subplot2grid((3,2), (2,0))
            ax4 = plt.subplot2grid((3,2), (0,1), rowspan=3)
            ax1.plot(self.tdec, temporal['east'], '-b')
            ax2.plot(self.tdec, temporal['north'], '-b')
            ax3.plot(self.tdec, temporal['up'], '-b')
            ax4.quiver(self.lon, self.lat, spatial['east'], spatial['north'],
                scale=1.0)
            plt.show()
        
        return
 

    @staticmethod
    def adaptiveMedianFilt(dat, kernel_size):
        """
        Perform a median filter with a sliding window. For edges, we shrink window.
        """
        assert kernel_size % 2 == 1, 'kernel_size must be odd'

        nobs = dat.size
        filt_data = np.nan * np.ones_like(dat)

        # Beginning region
        halfWindow = 0
        for i in range(kernel_size//2):
            filt_data[i] = nanmedian(dat[i-halfWindow:i+halfWindow+1])
            halfWindow += 1

        # Middle region
        halfWindow = kernel_size // 2
        for i in range(halfWindow, nobs - halfWindow):
            filt_data[i] = nanmedian(dat[i-halfWindow:i+halfWindow+1])

        # Ending region
        halfWindow -= 1
        for i in range(nobs - halfWindow, nobs):
            filt_data[i] = nanmedian(dat[i-halfWindow:i+halfWindow+1])
            halfWindow -= 1

        return filt_data


    def computeStatDistance(self, statname1, statname2):
        """
        Compute the distance between two stations.
        """
        ind1 = (self.name == statname1.lower()).nonzero()[0]
        ind2 = (self.name == statname2.lower()).nonzero()[0]
        assert len(ind1) == 1, 'Cannot find first station'
        assert len(ind2) == 1, 'Cannot find second station'

        # Retrieve lat/lon
        lon1, lat1 = self.lon[ind1[0]], self.lat[ind1[0]]
        lon2, lat2 = self.lon[ind2[0]], self.lat[ind2[0]]

        # Convert to XYZ and compute Cartesian distance
        from topoutil import llh2xyz
        X1 = llh2xyz(lat1, lon1, 0.0, deg=True).squeeze()
        X2 = llh2xyz(lat2, lon2, 0.0, deg=True).squeeze()
        dX = np.linalg.norm(X2 - X1)
        return dX


    @property
    def tstart(self):
        return selt.tdec[0]
    @tstart.setter
    def tstart(self, val):
        raise AttributeError('Cannot set tstart explicitly')

    @property
    def trel(self):
        return self.tdec - self.tdec[0]
    @trel.setter
    def trel(self, val):
        raise AttributeError('Cannot set tstart explicitly')

    @property
    def numObs(self):
        return len(self.tdec)
    @numObs.setter
    def numObs(self, val):
        raise AttributeError('Cannot set numObs explicitly')



class GenericClass:
    pass
