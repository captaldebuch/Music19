# Lexicon C19: published dataset and article replication

Xavier Fresquet. [A Multilingual Corpus of Historical Music Lexicography from the Long Nineteenth Century](https://doi.org/10.3390/data11110302), *Data* 11(11), 302 (2026).

Download the [Zenodo v3.2.1 ZIP](https://zenodo.org/records/22207277). The four scripts in `scripts/` and the clean publication-analysis notebook in `notebooks/` come from that archive. The files in `article/` implement the separate article supplement: retrieval examples, figure generation and rule-order sensitivity. The original OCR inputs are not distributed here.

From this directory, using Python 3.10 or later:

~~~sh
python article/audit_release.py --archive /path/to/Lexicon_C19_Export_Package_v3.2.1_2026-08-31.zip --output-dir diagnostics
~~~

Expected: 3,760 selected records, 25,186 candidates and zero category/subcategory mismatches when replaying the original rule order. This is a reproducibility check, not independent validation. For the interactive article notebook, install `article/requirements.txt`, start Jupyter from `article/` and set the archive path in its first code cell.

Replication code and executable notebooks: [MIT](LICENSE-CODE). Cite the [version DOI](https://doi.org/10.5281/zenodo.22207277) for the frozen data; the [concept DOI](https://doi.org/10.5281/zenodo.21588976) covers dataset versions.
