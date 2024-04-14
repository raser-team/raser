def main(kwargs):
    label = kwargs['label']
        
    if label == 'regincr_sim':
        from . import regincr_sim
        regincr_sim.main()  
    else:
        raise NameError(label)