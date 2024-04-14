from . import foo
def main(kwargs):
    label = kwargs['label']

    if label == 'foo':
        foo.main()
    else:
        raise NameError(label)