# tdr-convert

The TDR reader and DEVSIM importer in `raser.core.field` are derived from
Juan Sanchez's `tdr-convert` 0.1.7 at commit
`4151e42584bcf78c0d0c2693c3bd693747f634e4`, copyright 2024 DEVSIM LLC.

RASER retains the TDR geometry and dataset reader and the DEVSIM device writer.
The code was separated into `tdr_reader.py` and `tdr_import.py` and adapted to
the Field command flow in 2026.

The derived files are licensed under the
[Apache License 2.0](../../LICENSE-APACHE-2.0). The original attribution is
preserved in the repository-level [NOTICE](../../NOTICE). RASER's own code
remains covered by its repository-level [MIT license](../../LICENSE).
