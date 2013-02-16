import unittest, os, glob
import numpy as np
from obspy.core import Trace, UTCDateTime
from options import RtWavelocOptions
from hdf5_grids import H5SingleGrid

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticMigrationTests('test_rt_migration'))
    return suite

class SyntheticMigrationTests(unittest.TestCase):

    def setUp(self):
        self.wo = RtWavelocOptions()
        self.wo.verify_base_path()
        self.wo.verify_lib_dir()
        self.wo.opdict['time_grid'] = 'Slow_len.100m.P'

        base_path=self.wo.opdict['base_path']
        lib_path=os.path.join(base_path,'lib')

        time_grid_names = glob.glob(os.path.join(lib_path, \
                self.wo.opdict['time_grid'] + '*.hdf5'))
        self.time_grids=[H5SingleGrid(fname) for fname in time_grid_names]

        self.dt = 0.01


    def test_rt_migration(self):
        # get grid extent from first time-grid
        tgrid = self.time_grids[0]

        # set up three events
        x = np.random.rand(3) * tgrid.grid_info['nx'] * tgrid.grid_info['dx'] \
                + tgrid.grid_info['x_orig']
        y = np.random.rand(3) * tgrid.grid_info['ny'] * tgrid.grid_info['dy'] \
                + tgrid.grid_info['y_orig']
        z = np.random.rand(3) * tgrid.grid_info['nz'] * tgrid.grid_info['dz'] \
                + tgrid.grid_info['z_orig']
        amp = np.random.rand(3)
        t = np.arange(10000) * self.dt
        ot = np.random.rand(3)*70
        starttime=UTCDateTime(1975,12,18)

        for tgrid in self.time_grids:
            ttime = tgrid.value_at_points(x,y,z)
            print ttime+ot
            tr=

if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
