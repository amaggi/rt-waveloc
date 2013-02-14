import sys
import numpy as np
from obspy.core.trace import Trace, UTCDateTime
from obspy.realtime.rtmemory import RtMemory

def offset(trace, offset=0.0, rtmemory_list=None):
    if not isinstance(trace, Trace):
        msg = "Trace parameter must be an obspy.core.trace.Trace object."
        raise ValueError(msg)
    trace.data += offset
    return trace.data

