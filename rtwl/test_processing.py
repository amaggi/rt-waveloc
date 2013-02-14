import unittest, os, glob
import numpy as np
from numpy.testing import assert_array_almost_equal
from obspy.realtime import RtTrace
from obspy import read


def suite():
    suite = unittest.TestSuite()
    suite.addTest(RtTests('test_rt_example'))
    return suite

    
class RtTests(unittest.TestCase):

    def setUp(self):
        pass

    def test_rt_example(self):

        # set up traces
        data_trace = read('test_data/YA.UV15.00.HHZ.MSEED')[0]
        traces = data_trace / 3

        #npts
        npts1=len(data_trace)

        # filter in one bloc
        data_trace.filter('bandpass', freqmin=4.0, freqmax=10.0)

        # setup filtering of real-time trace
        rt_trace = RtTrace()
        #rt_trace.registerRtProcess(filter,type='bandpass',options={'freqmin':4.0, 'freqmax':10.0})

        # run rt processing
        for tr in traces:
            tr.detrend(type='demean')
            tr.filter('bandpass', freqmin=4.0, freqmax=10.0)
            rt_trace.append(tr, gap_overlap_check=True)

        npts2=len(rt_trace)

        print npts1, npts2
        diff=data_trace.copy()
        diff.data=rt_trace.data-data_trace.data
        #assert_array_almost_equal(data_trace.data, rt_trace.data, 1)
        diff.plot()
    




   

if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
