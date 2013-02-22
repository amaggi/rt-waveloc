import numpy as np
import matplotlib.pyplot as plt

def plotMaxXYZ(tr_max, tr_x, tr_y, tr_z, filename):

    npts = tr_max.stats.npts
    dt = tr_max.stats.delta
    starttime = tr_max.stats.starttime

    t = np.arange(npts)*dt

    plt.clf()
    fig = plt.figure()

    fig.suptitle('Summary traces starting at %s'%starttime.isoformat())

    p = plt.subplot(4,1,1, frameon=False)
    pos=list(p.get_position().bounds)
    fig.text(pos[0], pos[1]+pos[3], '(a)', fontsize=12)
    p.tick_params(labelsize=10)
    plt.scatter(t, tr_max.data, s=40, c=tr_max.data, marker='.', linewidths=(0,), clip_on=False)
    p.xaxis.set_ticks_position('none')
    p.xaxis.set_ticks(())
    plt.ylabel(tr_max.stats.station, size=10)
    p.yaxis.set_ticks_position('right')
    p.set_ylim(0,max(tr_max.data))

    p=plt.subplot(4,1,2, frameon=False)
    pos=list(p.get_position().bounds)
    fig.text(pos[0], pos[1]+pos[3], '(b)', fontsize=12)
    p.tick_params(labelsize=10)
    plt.scatter(t, tr_x.data, s=40, c=tr_max.data, marker='.', linewidths=(0,), clip_on=False)
    p.xaxis.set_ticks_position('none')
    p.xaxis.set_ticks(())
    plt.ylabel(tr_x.stats.station, size=10)
    p.yaxis.set_ticks_position('right')
    p.set_ylim(min(tr_x.data),max(tr_x.data))

    p=plt.subplot(4,1,3, frameon=False)
    pos=list(p.get_position().bounds)
    fig.text(pos[0], pos[1]+pos[3], '(c)', fontsize=12)
    p.tick_params(labelsize=10)
    plt.scatter(t, tr_y.data, s=40, c=tr_max.data, marker='.', linewidths=(0,), clip_on=False)
    p.xaxis.set_ticks_position('none')
    p.xaxis.set_ticks(())
    plt.ylabel(tr_y.stats.station, size=10)
    p.yaxis.set_ticks_position('right')
    p.set_ylim(min(tr_y.data),max(tr_y.data))

    p=plt.subplot(4,1,4, frameon=False)
    pos=list(p.get_position().bounds)
    fig.text(pos[0], pos[1]+pos[3], '(d)', fontsize=12)
    p.tick_params(labelsize=10)
    plt.scatter(t, tr_z.data, s=40, c=tr_max.data, marker='.', linewidths=(0,), clip_on=False)
    p.xaxis.set_ticks_position('bottom')
    plt.xlabel('Time (s)', size=10)
    plt.ylabel(tr_z.stats.station, size=10)
    p.yaxis.set_ticks_position('right')
    p.set_ylim(min(tr_z.data),max(tr_z.data))

    #plt.show()
    plt.savefig(filename)

