
'''
@Date       : 2024
@Author     : Ye He, Kaibo Xie
@version    : 2.0
'''

import logging

def main(kwargs):
    label = kwargs['label']
    verbose = kwargs['verbose'] 
    sensor = kwargs['sensor']

    if verbose == 1: # -v 
        logging.basicConfig(level=logging.INFO)
    if verbose == 2: # -vv 
        logging.basicConfig(level=logging.DEBUG)

    logging.info('This is INFO messaage')
    logging.debug('This is DEBUG messaage')


    if label == 'GetSignal':
        from . import get_signal
        get_signal.get_signal(sensor)
        
    if label == 'histogram_signal':
        from . import histogram_signal
        histogram_signal.get_signal()

    if label == 'one_histogram':
        from . import histogram
        histogram.main("one")

    if label == 'all_histogram':
        from . import histogram
        histogram.main("all")
