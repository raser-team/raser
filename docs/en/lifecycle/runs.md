# Run records

_Experiments, scans, and run records in `src/raser/lifecycle/`_

---

## Input

A run is determined by the device, the defaults, and the experiment
configuration.

The **device** lives at its default registered location `work/<device>/`, and
its default bias is part of the [device definition](../components/device.md).

The **defaults** come from three places:

| Origin | Content |
| --- | --- |
| Device definition | Bias, irradiation, and other device state |
| Workflow | Which source, front end, ADC, and G4Setup are used, and the events per job; kept in the application directory, for example `src/raser/apps/cce/charge_collection.json` |
| [Component](../components/README.md) definitions | The values in the selected source, G4Setup, and other files |

An **experiment** is a folder with one `config.json` that states only what
differs from the defaults and what is scanned:

```json
{
  "workflow": "cce",
  "device": "HPK-Si-PiN",
  "set": {"events_per_job": 20},
  "scan": {"voltage": [200, 300]}
}
```

| Key | Meaning |
| --- | --- |
| `set` | Values this experiment changes for good; every point uses them. The example sets the events per job to 20 |
| `scan` | Values to try one by one; each value is a point. The example has two points, 200 V and 300 V; several parameters run all their combinations |

The parameter names in `set` and `scan` are command options (such as `voltage`) or
addresses in the device, source, and G4Setup definitions (such as
`source.par_energy`). The user decides where an experiment folder lives and where
it runs; `work/` is the recommended location.

## Run

When the current directory has no `config.json`, a command lands in the folder
named after the workflow under the device and generates `config.json`:

```bash
raser cce HPK-Si-PiN -s 4        # work/HPK-Si-PiN/cce/
```

Inside an experiment folder, `raser -s 4` is equivalent to the sub-command form
above.

Without a scan one point runs; with a scan every point runs. A scan can also be
given directly on the command line:

```bash
raser cce HPK-Si-PiN -s 4 --scan voltage=200,300
```

| Option | Meaning |
| --- | --- |
| `-s <n>` | Number of [jobs](jobs.md) each seed folder is split into |
| `-b` | Submit the jobs to the [cluster](jobs.md#run) |
| `--seed <n>` | Fixed seed |
| `--dry-run` | Only show what would run |

One command creates a seed folder for every point and then runs it as jobs;
[Jobs](jobs.md) describes how jobs are generated and executed locally or on the
cluster.

Changing experiment parameters keeps the solved fields of the device.

## Output

A scan opens sub-folders automatically. Their flat names contain only the
parameters that changed, for example `voltage_300_al_0.05/`. The unchanged
point stays at the root of the experiment folder. A `"name"` line in
`config.json` supplies a name template.

Every point holds one level of seed folders. The default seed is taken from
the timestamp and the folder is named by that timestamp; a fixed seed uses
`seed_42/`.

`run.json` in the seed folder records the configuration and commit of that
run. Running a fixed seed again reruns when the configuration or commit differs
from the record, and the earlier result is kept. Uncommitted changes in the
working tree produce a warning.

```text
work/HPK-Si-PiN/cce/
├── config.json
├── 2026_1112_133122/
│   ├── run.json
│   └── batch/
├── seed_42/
│   ├── run.json
│   └── batch/
├── voltage_300/
│   └── 2026_1112_133210/
│       ├── run.json
│       └── batch/
└── analysis/
```

Each job writes its products to `batch/` of its seed folder; [Jobs](jobs.md#output)
lists them. Summary results are written under `analysis/`.
