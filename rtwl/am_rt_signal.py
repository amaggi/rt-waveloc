import sys
import numpy as np
from obspy.core.trace import Trace, UTCDateTime
from obspy.realtime.rtmemory import RtMemory

def offset(trace, offset=0.0, rtmemory_list=None):
    """
    Add the specified offset to the data.

    :type trace: :class:`~obspy.core.trace.Trace`
    :param trace: :class:`~obspy.core.trace.Trace` object to append to this RtTrace
    :type offset: float, optional
    :param offset: offset (default is 0.0)
    :type rtmemory_list: list of :class:`~obspy.realtime.rtmemory.RtMemory`, optional
    :param rtmemory_list: Persistent memory used by this process for specified trace
    :rtype: Numpy :class:`numpy.ndarray`
    :return: Processed trace data from appended Trace object
    """

    if not isinstance(trace, Trace):
        msg = "Trace parameter must be an obspy.core.trace.Trace object."
        raise ValueError(msg)

    trace.data += offset
    return trace.data

def kurtosis(trace, win=3.0, rtmemory_list=None):
    """
    Apply recursive kurtosis calculation on data. Recursive kurtosis is computed
    using the Chassande-Mottin (2002) formulation adjusted to give the kurtosis 
    of a gaussian distribution = 0.0.

    :type trace: :class:`~obspy.core.trace.Trace`
    :param trace: :class:`~obspy.core.trace.Trace` object to append to this RtTrace
    :type win: float, optional
    :param win: window length in seconds for the kurtosis (default is 3.0 s)
    :type rtmemory_list: list of :class:`~obspy.realtime.rtmemory.RtMemory`, optional
    :param rtmemory_list: Persistent memory used by this process for specified trace
    :rtype: Numpy :class:`numpy.ndarray`
    :return: Processed trace data from appended Trace object
    """


    if not isinstance(trace, Trace):
        msg = "Trace parameter must be an obspy.core.trace.Trace object."
        raise ValueError(msg)
    
    # if this is the first appended trace, the rtmemory_list will be None
    if not rtmemory_list:
        rtmemory_list = [RtMemory(), RtMemory(), RtMemory()]

    # deal with case of empty trace
    sample = trace.data
    if np.size(sample) < 1:
        return sample

    # get simple info from trace
    npts=len(sample)
    dt=trace.stats.delta

    # set some constants for the kurtosis calulation
    C1 = dt/float(win)
    a1 = 1.0 - C1
    C2 = (1.0 - a1*a1)/2.0
    bias = -3*C1 - 3.0

    # prepare the output array
    kappa4 = np.empty(npts, sample.dtype)

    # initialize the real-time memory needed to store
    # the recursive kurtosis coefficients until the
    # next bloc of data is added
    rtmemory_mu1 = rtmemory_list[0]
    rtmemory_mu2 = rtmemory_list[1]
    rtmemory_k4_bar = rtmemory_list[2]

    # there are three memory objects, one for each "last" coefficient
    # that needs carrying over
    # initialize mu1_last to 0
    if not rtmemory_mu1.initialized:
        memory_size_input  = 1
        memory_size_output = 0
        rtmemory_mu1.initialize(sample.dtype, memory_size_input,\
                                memory_size_output, 0, 0)

    # initialize mu2_last (sigma) to 1
    if not rtmemory_mu2.initialized:
        memory_size_input  = 1
        memory_size_output = 0
        rtmemory_mu2.initialize(sample.dtype, memory_size_input,\
                                memory_size_output, 1, 0)

    # initialize k4_bar_last to 0
    if not rtmemory_k4_bar.initialized:
        memory_size_input  = 1
        memory_size_output = 0
        rtmemory_k4_bar.initialize(sample.dtype, memory_size_input,\
                                memory_size_output, 0, 0)

    mu1_last = rtmemory_mu1.input[0]
    mu2_last = rtmemory_mu2.input[0]
    k4_bar_last = rtmemory_k4_bar.input[0]

    # do recursive kurtosis
    for i in xrange(npts):
        mu1 = a1*mu1_last + C1*sample[i]
        dx2 = (sample[i]-mu1_last)*(sample[i]-mu1_last)
        mu2 = a1*mu2_last + C2*dx2
        dx2 = dx2 / mu2_last
        k4_bar = (1+C1 - 2*C1*dx2)*k4_bar_last + C1 * dx2 * dx2
        kappa4[i] = k4_bar + bias
        mu1_last=mu1
        mu2_last=mu2
        k4_bar_last=k4_bar

    rtmemory_mu1.input[0] = mu1_last
    rtmemory_mu2.input[0] = mu2_last
    rtmemory_k4_bar.input[0] = k4_bar_last

    return kappa4
