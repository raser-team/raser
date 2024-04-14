from . import *
def main(kwargs):
    label = kwargs['label']

    if label == 'model':
        from . import model
        model.main()
    else:
        raise NameError(label)