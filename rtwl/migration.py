import h5py
import numpy as np

class RtMigrator(object):
    """
    Class of objects for real-time migration.
    """

    # attributes
    x=np.array([])
    y=np.array([])
    z=np.array([])
    ttimes_matrix=np.empty((0,0), dtype=float)
    npts=0
    nsta=0


    def __init__(self,ttimes_fnames):
        """
        Initialize from a set of travel-times as hdf5 files
        """
        # get basic lengths
        f=h5py.File(ttimes_fnames[0],'r')
        # copy the x, y, z data over
        self.x = np.array(f['x'][:])
        self.y = np.array(f['y'][:])
        self.z = np.array(f['z'][:])
        f.close()
        # read the files
        ttimes_list = []
        sta_dict={}
        i=0
        for fname in ttimes_fnames:
            f=h5py.File(fname,'r')
            # update the list of ttimes
            ttimes_list.append(np.array(f['ttimes']))
            sta=f['ttimes'].attrs['station']
            f.close()
            # update the dictionary of station names
            sta_dict[sta]=i
            i=i+1
        # stack the ttimes into a numpy array
        self.ttimes_matrix=np.vstack(ttimes_list)
        (self.nsta,self.npts) = self.ttimes_matrix.shape

#        ttimes_matrix=np.round(ttimes_matrix / self.dt) * self.dt






