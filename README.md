# RASER

> Version 5.0 · Python 3.11 · Semiconductor-detector simulation

RASER (**RA**diation **SE**miconducto**R**) connects detector fields, particle
interactions, induced-current calculation, electronics, and experiment-level
workflows through one command-line interface.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18905684.svg)](https://doi.org/10.5281/zenodo.18905684)

---

## 🚀 Use RASER

After activating a prepared environment, use the public CLI:

```bash
raser --help
raser signal HPK-Si-PiN
```

Common workflows include:

| Goal | Command |
| --- | --- |
| Solve the electric and weighting fields | `raser field HPK-Si-PiN` |
| Generate a signal | `raser signal HPK-Si-PiN` |
| Run a CCE study | `raser cce NJU-PiN` |
| Run a time-resolution study | `raser timeres NJU-PiN` |

Use `raser <command> --help` for the current options. Generated fields and runs
are stored under `work/`.

## 📚 Documentation

- [Documentation / 文档](docs/README.md)
- [Container build routes](bootstrap/README.md)
- [Repository working rules](AGENTS.md)

## 🔖 Citation

The archived RASER v4.0 release is available from
[Zenodo](https://doi.org/10.5281/zenodo.18905684). Cite the software release and
the relevant detector-study publication when reporting results produced with
RASER.

RASER is distributed under the [MIT License](LICENSE).
