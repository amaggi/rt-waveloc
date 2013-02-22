import os, time, glob
from obspy.core import read

import am_rt_signal
from options import RtWavelocOptions
from synthetics import generate_random_test_points
from migration import RtMigrator
from plotting import plotMaxXYZ

###############
# stuff that needs doing while I still have 
# realtime functions that are not part of obspy
import obspy.realtime
rt_dict= obspy.realtime.rttrace.REALTIME_PROCESS_FUNCTIONS
rt_dict['neg_to_zero']=(am_rt_signal.neg_to_zero,0)
rt_dict['convolve']=(am_rt_signal.convolve,1)
rt_dict['sw_kurtosis']=(am_rt_signal.sw_kurtosis,1)
rt_dict['dx2']=(am_rt_signal.dx2,2)

###############

n_test=500

# set up options
wo = RtWavelocOptions()
wo.opdict['outdir'] = 'RealDataTest'
wo.opdict['datadir'] = 'RealDataTest'
wo.opdict['data_glob'] = 'YA*MSEED'
wo.opdict['time_grid'] = 'Slow_len.100m.P'
wo.opdict['max_length'] = 120
wo.opdict['safety_margin'] = 20
wo.opdict['syn'] = False
wo.opdict['filt_f0'] = 27.0
wo.opdict['filt_sigma'] = 7.0
wo.opdict['kwin'] = 3.0


# read data

fnames=glob.glob(os.path.join(wo.data_dir, wo.opdict['data_glob']))
obs_list=[]
for name in fnames:
    st=read(name)
    obs_list.append(st[0])

starttime=obs_list[0].stats.starttime
dt=obs_list[0].stats.delta
wo.opdict['dt'] = dt

# split data files to simulate packets of real-time data
obs_split=[]
for obs in obs_list:
    split = obs / 3
    obs_split.append(split)

# generate ttimes_files for test
#generate_random_test_points(wo, n_test, (x0, y0, z0))
generate_random_test_points(wo, n_test)

tic=time.time()

# set up migrator
migrator = RtMigrator(wo)
nsta = migrator.nsta


ntr=len(obs_split[0])
#########################
# start loops
#########################
# loop over segments (simulate real-time data)
for itr in xrange(ntr):
    # update all input streams
    # loop over stations
    data_list=[]
    for ista in xrange(nsta):
        tr = obs_split[ista][itr]
        data_list.append(tr)

    # update data
    migrator.updateData(data_list)

    # update stacks
    migrator.updateStacks()
            
    # update max
    migrator.updateMax()

#########################
# end loops
#########################

tac=time.time()
print "Time taken for four-minute 100Hz real-data test on %d points : %.2f s"%(n_test, tac-tic)

st=migrator.max_out.stats.starttime+110
ed=migrator.max_out.stats.starttime+125
max_out=migrator.max_out.slice(st,ed)
x_out=migrator.x_out.slice(st,ed)
y_out=migrator.y_out.slice(st,ed)
z_out=migrator.z_out.slice(st,ed)
#max_out=migrator.max_out
#x_out=migrator.x_out
#y_out=migrator.y_out
#z_out=migrator.z_out

figname=os.path.join(wo.fig_dir,'test_out.png')
plotMaxXYZ(max_out, x_out, y_out, z_out, figname)
print "View output in file : %s"%figname

