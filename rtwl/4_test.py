import multiprocessing as mp
from multiprocessing import queues
import time, os
import numpy as np
from scipy.fftpack import fft, ifft
os.system('taskset -p 0xffff %d' % os.getpid())


#----------------------------------------------
class TaskQueue(queues.Queue):
    """modified class multiprocessing.queues.Queue
    """
    def __init__(self, maxsize):
        queues.Queue.__init__(self, maxsize=maxsize)
    #----
    def _feed(self, generator):  
        """private method"""
        while True:
            try:
                item = generator.next()
            except StopIteration:
                self.close()
                break
            print "put     :", item
            self.put(item) #wait here if the queue is full   
    #----
    def feed_async(self, generator):
        """feed the queue asynchronously using a task generator.
        The method tries to keep the queue full.
        Note : the generator order is preserved in the queue
        """
        p = mp.Process(target=TaskQueue._feed, args=(self, generator))
        p.start()
        
#----------------------------------------------
class Worker(mp.Process):
    """get a callable task from the task_queue, put the result into result_queue
    """
    def __init__(self, task_queue, result_queue):
        mp.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue
    #----
    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                print 'exiting : %s' % (proc_name)
                self.result_queue.put(None)
                break
            print 'run     : %s, %s' % (next_task, proc_name)
            taskid, result = next_task()
            self.result_queue.put((taskid, result))

#----------------------------------------------
class Task(object):
    def __init__(self, taskid, func, args):
        self.taskid = taskid
        self.func   = func
        self.args   = args
    #----
    def __call__(self):
        return self.taskid, self.func(self.args)
    #----
    def __str__(self):
        return 'Task #%d' % (self.taskid)
        
#----------------------------------------------
def WorkSession(Func, ArgGenerator, Nworker, Ntask):
    """
    Func  = function
    ArgGenerator = argument generator
    Nworker = number of workers
    Ntask   = maximum number of tasks that can be stored into the task_queue
    """
    #----
    def TaskGenerator():
        taskid = 0
        for args in ArgGenerator:
            yield Task(taskid=taskid, func=Func, args=args)
            taskid += 1
        for w in xrange(Nworker):
            yield None
    #----
    tasks   = TaskQueue(maxsize=Ntask)
    results = mp.Queue(maxsize=1)
     
    workers = [Worker(tasks, results) for i in xrange(Nworker)]
    for w in workers:
        w.start()

    tasks.feed_async(TaskGenerator())

    Nkilled = 0
    while True:
        result = results.get()
        if result is None:
            Nkilled += 1
            if Nkilled == len(workers):
                raise StopIteration
        else:
            yield result

#----------------------------------------------
if __name__ == "__main__":

    # 1 - define the function here
    def process(dataset):
        return ifft(fft(dataset))

    # 2 - define here the argument generator
    def args(Njob):
        for i in xrange(Njob):
            yield np.random.randn(100001)
            
    # 3 - initiate the working session
    results = WorkSession(Func=process, ArgGenerator=args(20), Nworker=10, Ntask=5)
   
    # 4 - generate the results
    for taskid, result in results:
        print 'result  : Task #%d' % taskid







