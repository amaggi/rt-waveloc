import unittest, os, glob
import numpy as np
import am_rt_signal
from numpy.testing import assert_array_almost_equal
from obspy.realtime import RtTrace 
from obspy import read, Stream


def suite():
    suite = unittest.TestSuite()
    suite.addTest(RtTests('test_rt_offset'))
    suite.addTest(RtTests('test_rt_scale'))
    suite.addTest(RtTests('test_rt_mean'))
    suite.addTest(RtTests('test_rt_variance'))
    suite.addTest(RtTests('test_rt_dx2'))
    suite.addTest(RtTests('test_rt_kurtosis'))
    suite.addTest(RtTests('test_rt_neg_to_zero'))
    suite.addTest(RtTests('test_rt_kurt_grad'))
    suite.addTest(RtTests('test_rt_gaussian_filter'))
    suite.addTest(RtTests('test_kwin_bank'))
    suite.addTest(FilterTests('test_bp_filterbank'))
    suite.addTest(FilterTests('test_gaussian_filter'))
    return suite

    
class RtTests(unittest.TestCase):

    def setUp(self):
        import obspy.realtime
        rt_dict= obspy.realtime.rttrace.REALTIME_PROCESS_FUNCTIONS
#        rt_dict['offset']=(am_rt_signal.offset,0)
#        rt_dict['kurtosis']=(am_rt_signal.kurtosis,3)
        rt_dict['mean']=(am_rt_signal.mean,1)
        rt_dict['variance']=(am_rt_signal.variance,2)
        rt_dict['dx2']=(am_rt_signal.dx2,2)
        rt_dict['neg_to_zero']=(am_rt_signal.neg_to_zero,0)
        rt_dict['convolve']=(am_rt_signal.convolve,1)

        # set up traces
        self.data_trace = read('test_data/YA.UV15.00.HHZ.MSEED')[0]
        # note : we are going to produce floating point output, so we need
        # floating point input seismograms
        x=self.data_trace.data.astype(np.float32)
        self.data_trace.data=x
        self.traces = self.data_trace / 3

    def test_rt_offset(self):

        offset=500

        rt_trace=RtTrace()
        rt_trace.registerRtProcess('offset',offset=offset)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)


        diff=self.data_trace.copy()
        diff.data=rt_trace.data-self.data_trace.data
        self.assertAlmostEquals(np.mean(np.abs(diff)),offset)

    def test_rt_scale(self):

        data_trace = self.data_trace.copy()

        fact=1/np.std(data_trace.data)

        data_trace.data *= fact

        rt_trace=RtTrace()
        rt_trace.registerRtProcess('scale',factor=fact)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)

        diff=self.data_trace.copy()
        diff.data=rt_trace.data-data_trace.data
        self.assertAlmostEquals(np.mean(np.abs(diff)),0.0)


    # skip this if not on a machine with a recent waveloc installed
    def test_rt_kurtosis(self):
        from waveloc.filters import rec_kurtosis
        win=3.0
        data_trace = self.data_trace.copy()

        sigma=float(np.std(data_trace.data))
        fact = 1/sigma

        dt=data_trace.stats.delta
        C1=dt/float(win)

        x=data_trace.data
        ktrace=data_trace.copy()
        ktrace.data=rec_kurtosis(x*fact,C1)

        rt_trace=RtTrace()
        rt_trace.registerRtProcess('scale',factor=fact)
        rt_trace.registerRtProcess('kurtosis',win=win)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)
   
        diff=self.data_trace.copy()
        diff.data=rt_trace.data-ktrace.data
        self.assertAlmostEquals(np.mean(np.abs(diff)),0.0)

    def test_rt_neg_to_zero(self):

        data_trace=self.data_trace.copy()
        max_val=np.max(data_trace.data)
        
        rt_trace=RtTrace()
        rt_trace.registerRtProcess('neg_to_zero')

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)

        max_val_test=np.max(rt_trace.data)
        min_val_test=np.min(rt_trace.data)
        self.assertEqual(max_val, max_val_test)
        self.assertEqual(0.0, min_val_test)

    def test_rt_mean(self):

        win=0.05

        data_trace=self.data_trace.copy()

        rt_single=RtTrace()
        rt_trace=RtTrace()
        rt_trace.registerRtProcess('mean',win=win)
        rt_single.registerRtProcess('mean',win=win)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)
        rt_single.append(data_trace, gap_overlap_check = True)

        newtr=self.data_trace.copy()
        newtr.data=newtr.data-rt_trace.data
        assert_array_almost_equal(rt_single, rt_trace)
        self.assertAlmostEqual(np.mean(newtr.data),0.0,0)

    def test_rt_variance(self):

        win=10

        data_trace=self.data_trace.copy()

        rt_single=RtTrace()
        rt_trace=RtTrace()
        rt_trace.registerRtProcess('variance',win=win)
        rt_single.registerRtProcess('variance',win=win)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)
        rt_single.append(data_trace, gap_overlap_check = True)

        assert_array_almost_equal(rt_single, rt_trace)

    def test_rt_dx2(self):

        win=10

        data_trace=self.data_trace.copy()

        rt_single=RtTrace()
        rt_trace=RtTrace()
        rt_trace.registerRtProcess('dx2',win=win)
        rt_trace.registerRtProcess('boxcar',width=50)
        rt_single.registerRtProcess('dx2',win=win)
        rt_single.registerRtProcess('boxcar',width=50)

        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)
        rt_single.append(data_trace, gap_overlap_check = True)

        assert_array_almost_equal(rt_single, rt_trace)


    def test_rt_kurt_grad(self):
        win=3.0 
        data_trace = self.data_trace.copy()

        sigma=float(np.std(data_trace.data))
        fact = 1/sigma

        rt_trace=RtTrace()
        rt_trace_single = RtTrace()

        for rtt in [rt_trace, rt_trace_single]:
            rtt.registerRtProcess('scale',factor=fact)
            rtt.registerRtProcess('kurtosis',win=win)
            rtt.registerRtProcess('boxcar',width=50)
            rtt.registerRtProcess('differentiate')
            rtt.registerRtProcess('neg_to_zero')

        rt_trace_single.append(data_trace)
        
        for tr in self.traces:
            rt_trace.append(tr, gap_overlap_check = True)

        diff=self.data_trace.copy()
        diff.data=rt_trace_single.data - rt_trace.data
        self.assertAlmostEquals(np.mean(np.abs(diff)), 0.0, 5)

    def test_kwin_bank(self):
        win_list=[1.0, 3.0, 9.0] 
        n_win = len(win_list)

        data_trace = self.data_trace.copy()

        sigma=float(np.std(data_trace.data))
        fact = 1/sigma

        # One RtTrace for processing before the kurtosis
        rt_trace=RtTrace()
        rt_trace.registerRtProcess('scale',factor=fact)

        # One RtTrace per kurtosis window
        kurt_traces=[]
        for i in xrange(n_win):
            rtt=RtTrace()
            rtt.registerRtProcess('kurtosis',win=win_list[i])
            kurt_traces.append(rtt)

        # One RrTrace for post-processing the max kurtosis window
        max_kurt=RtTrace()
        max_kurt.registerRtProcess('differentiate')
        max_kurt.registerRtProcess('neg_to_zero')

        for tr in self.traces:
            # prepare memory for kurtosis
            kurt_tr=tr.copy() 
            # do initial processing
            proc_trace=rt_trace.append(tr, gap_overlap_check = True)
            kurt_output=[]
            for i in xrange(n_win):
                # pass output of initial processing to the kwin bank
                ko=kurt_traces[i].append(proc_trace, gap_overlap_check = True)
                # append the output to the kurt_output list
                kurt_output.append(ko.data)
            # stack the output of the kwin bank and find maximum
            kurt_stack=np.vstack(tuple(kurt_output))
            kurt_tr.data=np.max(kurt_stack,axis=0)
            # append to the max_kurt RtTrace for post-processing
            max_kurt.append(kurt_tr)

        #max_kurt.plot()

    def test_rt_gaussian_filter(self):
        from am_signal import gaussian_filter

        data_trace = self.data_trace.copy()
        gauss5,tshift = gaussian_filter(1.0, 5.0, 0.01)

        rt_trace=RtTrace()
        rt_single=RtTrace()
        for rtt in [rt_trace, rt_single]:
            rtt.registerRtProcess('convolve',conv_signal=gauss5)

        rt_single.append(data_trace, gap_overlap_check = True)

        for tr in self.traces:
            # pre-apply inversed time-shift before appending data
            tr.stats.starttime -= tshift
            rt_trace.append(tr, gap_overlap_check = True)

        # test the waveforms are the same
        diff=self.data_trace.copy()
        diff.data=rt_trace.data-rt_single.data
        self.assertAlmostEquals(np.mean(np.abs(diff)),0.0)
        # test the time-shifts
        starttime_diff=rt_single.stats.starttime-self.data_trace.stats.starttime
        self.assertAlmostEquals(starttime_diff,0.0)



@unittest.skip('Skipping filter tests')
class FilterTests(unittest.TestCase):

    def setUp(self):
        # set up traces
        self.data_trace = read('test_data/YA.UV15.00.HHZ.MSEED')[0]
        # note : we are going to produce floating point output, so we need
        # floating point input seismograms
        x=self.data_trace.data.astype(np.float32)
        self.data_trace.data=x
        self.traces = self.data_trace / 3

    def test_bp_filterbank(self):
        st=Stream()
        fst=Stream()
        data_trace=self.data_trace.copy()
        data_trace.data=np.zeros(400)
        data_trace.data[200]=1*2*np.pi
        freqmin=1.0
        freqmax=4.0
        freq_step=(freqmax-freqmin)/2.0
        n_bank=5
        for i in xrange(n_bank):
            dtrace=data_trace.copy()
            dtrace.filter('bandpass',freqmin=freqmin+i*freq_step, \
                    freqmax=freqmax+i*freq_step, zerophase=True)
            st.append(dtrace)
            ftrace=self.data_trace.copy()
            ftrace.data=np.convolve(ftrace.data,dtrace.data,'same')
            #ftrace.plot()



    def test_gaussian_filter(self):
        from am_signal import gaussian_filter
        import matplotlib.pyplot as plt

        gauss1, t=gaussian_filter(1.0, 1.0, 0.01)
        gauss5, t=gaussian_filter(1.0, 5.0, 0.01)

        self.assertAlmostEquals(t[np.argmax(gauss1)],0)

        data_trace1=self.data_trace.copy()
        data_trace5=self.data_trace.copy()
        data_trace1.data=np.convolve(data_trace1.data,gauss1,'same')
        data_trace5.data=np.convolve(data_trace5.data,gauss5,'same')

if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
