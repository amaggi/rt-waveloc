import unittest, os, glob
import numpy as np
import am_rt_signal
from numpy.testing import assert_array_almost_equal
from obspy.realtime import RtTrace 
from obspy import read


def suite():
    suite = unittest.TestSuite()
    suite.addTest(RtTests('test_rt_example'))
    suite.addTest(RtTests('test_rt_offset'))
    return suite

    
class RtTests(unittest.TestCase):

    def setUp(self):
        import obspy.realtime
        rt_dict= obspy.realtime.rttrace.REALTIME_PROCESS_FUNCTIONS
        rt_dict['offset']=(am_rt_signal.offset,0)

        # set up traces
        self.data_trace = read('test_data/YA.UV15.00.HHZ.MSEED')[0]
        self.traces = self.data_trace / 3

    def test_rt_example(self):

        # filter in one bloc
        data_trace = self.data_trace.copy()
        data_trace.filter('bandpass', freqmin=4.0, freqmax=10.0)

        # setup filtering of real-time trace
        rt_trace = RtTrace()
        #rt_trace.registerRtProcess(filter,type='bandpass',options={'freqmin':4.0, 'freqmax':10.0})

        # run rt processing
        for tr in self.traces:
            tr.detrend(type='demean')
            tr.filter('bandpass', freqmin=4.0, freqmax=10.0)
            rt_trace.append(tr, gap_overlap_check=True)


        diff=data_trace.copy()
        diff.data=rt_trace.data-data_trace.data
        #diff.plot()
        self.assertAlmostEquals(np.mean(np.abs(diff)),0.0)
    
    def test_rt_offset(self):

        offset=500

        data_trace = self.data_trace.copy()
        data_trace.data += offset

        rt_trace=RtTrace()
        rt_trace.registerRtProcess('offset',offset=offset)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)


        diff=self.data_trace.copy()
        diff.data=rt_trace.data-self.data_trace.data
        self.assertAlmostEquals(np.mean(np.abs(diff)),offset)

   

if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
