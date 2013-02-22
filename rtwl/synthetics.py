import os, glob
import numpy as np
from obspy.core import UTCDateTime, Trace
from hdf5_grids import H5SingleGrid, interpolateTimeGrid

def make_synthetic_data(waveloc_options):
    """
    Creates a synthetic data set from the time grids.
    """

    wo = waveloc_options

    
    # set up some synthetic parameters
    dt=0.01
    t = np.arange(12000) * dt
    ot = 50
    starttime=UTCDateTime()
    g_width=0.2

    # get grid extent from first time-grid
    time_grid_names = glob.glob(wo.grid_glob)
    time_grids=[H5SingleGrid(fname) for fname in time_grid_names]
    tgrid = time_grids[0]

    # set up an event at the center of the grid
    x = 0.5 * tgrid.grid_info['nx'] * tgrid.grid_info['dx'] \
            + tgrid.grid_info['x_orig']
    y = 0.5 * tgrid.grid_info['ny'] * tgrid.grid_info['dy'] \
            + tgrid.grid_info['y_orig']
    z = 0.5 * tgrid.grid_info['nz'] * tgrid.grid_info['dz'] \
                + tgrid.grid_info['z_orig']

    # create observations
    obs_list=[]
    for tgrid in time_grids:
        ttime = tgrid.value_at_point(x,y,z)
        ttime = np.round(ttime / dt) * dt
        tobs = ttime+ot
        # set up stats
        sta=tgrid.grid_info['station']
        stats={'network':'ST', 'station':sta,\
                'channel':'HHZ', 'npts':len(t), 'delta':dt,\
                'starttime':starttime}
        # set up seismogram
        seis=  np.exp(-0.5*(t-tobs)**2 / (g_width**2) ) 
        tr = Trace(data=seis,header=stats)
        obs_list.append(tr)
        #tr.plot()

    return obs_list, ot, (x,y,z)

def generate_random_test_points(waveloc_options,npts,loc0=None):
    """
    Generates ttimes files for npts random test points including x0, y0, z0.
    """
    wo = waveloc_options

    # get grid extent from first time-grid
    time_grid_names = glob.glob(wo.grid_glob)
    tgrid=H5SingleGrid(time_grid_names[0]) 

    x_range=tgrid.grid_info['nx']*tgrid.grid_info['dx']
    y_range=tgrid.grid_info['ny']*tgrid.grid_info['dy']
    z_range=tgrid.grid_info['nz']*tgrid.grid_info['dz']

    # generate points
    x_test=np.random.rand(npts)*x_range + tgrid.grid_info['x_orig']
    y_test=np.random.rand(npts)*y_range + tgrid.grid_info['y_orig']
    z_test=np.random.rand(npts)*z_range + tgrid.grid_info['z_orig']
    x=np.empty(npts)
    y=np.empty(npts)
    z=np.empty(npts)
    x[:]=x_test
    y[:]=y_test
    z[:]=z_test
    if not loc0 == None:
        (x0, y0, z0) = loc0
        x[0]=x0
        y[0]=y0
        z[0]=z0

    # generate files
    ttimes_path=wo.ttimes_dir
    time_grid_names = glob.glob(wo.grid_glob)
    base_names=[os.path.basename(fname) for fname in time_grid_names]
    tt_names=[os.path.join(ttimes_path,base_name) for base_name in base_names]

    for i in xrange(len(time_grid_names)):
        outname,ext=os.path.splitext(tt_names[i])
        outname = outname +'_ttimes.hdf5'
        interpolateTimeGrid(time_grid_names[i], outname, x, y, z)



