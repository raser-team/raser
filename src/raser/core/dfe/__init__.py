

def main(kwargs):
    label = kwargs['label']
        
    if label == 'regincr':
        from . import regincr
        regincr.main()
    elif label == 'regincr2stage':
        from . import regincr2stage
        regincr2stage.main()
    else:
        raise NameError(label)
    