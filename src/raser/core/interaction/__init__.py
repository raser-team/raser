
def main(kwargs):
    label = kwargs['label']
    if label == "energy_deposit":
        from . import g4_sic_energy_deposition
        g4_sic_energy_deposition.main()
    else:
        raise NameError(label)