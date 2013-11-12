import os, time
from options import RtWavelocOptions
from synthetics import make_synthetic_data, generate_random_test_points
from migration import RtMigrator
from plotting import plotMaxXYZ


# set up options
wo = RtWavelocOptions()
wo.opdict['base_path'] = 'test_data'
wo.opdict['outdir'] = 'SynTest'
wo.opdict['time_grid'] = 'Slow_len.100m.P'
wo.opdict['max_length'] = 120
wo.opdict['safety_margin'] = 20
wo.opdict['dt'] = 0.01
wo.opdict['syn'] = True
wo.opdict['syn_npts'] = 30

# make synthetic data
obs_list, ot, (x0,y0,z0) = make_synthetic_data(wo)

starttime=obs_list[0].stats.starttime
dt=obs_list[0].stats.delta

# split data files to simulate packets of real-time data
obs_split=[]
for obs in obs_list:
    split = obs / 3
    obs_split.append(split)

# generate ttimes_files for test
generate_random_test_points(wo, 
        (x0, y0, z0)
        )


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
n_test = wo.opdict['syn_npts']

print "Time taken for two-minute 100Hz synthetic test on %d points : %.2f s"%(n_test, tac-tic)

#st=migrator.max_out.stats.starttime+45
#ed=migrator.max_out.stats.starttime+55
st=migrator.max_out.stats.starttime
ed=migrator.max_out.stats.endtime
max_out=migrator.max_out.slice(st,ed)
x_out=migrator.x_out.slice(st,ed)
y_out=migrator.y_out.slice(st,ed)
z_out=migrator.z_out.slice(st,ed)

figname=os.path.join(wo.fig_dir,'synthetic_test_out.png')
plotMaxXYZ(max_out, x_out, y_out, z_out, figname)
print "View output in file : %s"%figname

