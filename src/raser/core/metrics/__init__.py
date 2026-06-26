"""Waveform and signal-derived metrics."""


def main(kwargs):
    if kwargs["det_name"] == "HPK-Si-LGAD-CCE":
        from . import charge_distribution

        charge_distribution.main()
    else:
        from . import waveform_stats

        waveform_stats.main(kwargs)
