"""Generate legible figures and an executable companion from frozen inputs."""

import argparse
import csv
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import numpy as np
from matplotlib.colors import Normalize


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE
ZIP = ROOT / "zenodo_export_v3.2.1/Lexicon_C19_Export_Package_v3.2.1_2026-08-31.zip"
SOURCE_LABELS = {
    "Musik-Lexikon": "Riemann/Shedlock (1908)",
    "Complete Encyclopaedia of Music": "Moore (1854)",
    "A Dictionary of Music and Musicians (A.D. 1450-1889)": "Grove (1879-89)",
    "Dictionnaire de la danse": "Desrat (1895)",
    "Meyers Konversations-Lexikon (Music Articles)": "Meyers (1885-90)",
    "Biographie universelle des musiciens": "Fetis/Pougin (1860-80)",
    "Brockhaus-Efron Encyclopaedia (Music Articles)": "Brockhaus-Efron (1896)",
    "Diccionario biographico de musicos portuguezes": "Vieira (1900)",
}


def figures(archive_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        selected = list(csv.DictReader(io.StringIO(archive.read("datasets/master_performance_dataset_v3_2.csv").decode("utf-8"))))
        pool = [json.loads(line) for line in archive.read("validation/all_extracted_entries_v3_2.jsonl").splitlines() if line.strip()]
    count = Counter(row["source_dictionary"] for row in selected)
    parsed = Counter(row["source_dictionary"] for row in pool)
    sources = sorted(count, key=lambda source: -count[source])
    assert set(sources) == set(SOURCE_LABELS)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "pdf.fonttype": 42,
                         "axes.labelcolor": "#202020", "text.color": "#202020"})
    fig, ax = plt.subplots(figsize=(10, 5.3))
    fig.subplots_adjust(left=.34, right=.98, top=.87, bottom=.12)
    y = np.arange(len(sources))
    ax.barh(y, [count[s] for s in sources], color="#216e8c", height=.58)
    ax.set_yticks(y, [SOURCE_LABELS[s] for s in sources], fontsize=12)
    ax.invert_yaxis()
    ax.set_xlim(0, 2250)
    ax.set_xticks([0, 500, 1000])
    ax.set_xlabel("Selected records", loc="left")
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=8)
    for index, source in enumerate(sources):
        ax.text(count[source] + 25, index, f"{count[source]:,}", va="center", fontsize=12)
        ax.text(1740, index, f"{parsed[source]:,}", va="center", ha="right", fontsize=12)
        ax.text(2210, index, f"{100 * count[source] / parsed[source]:.1f}%", va="center", ha="right", fontsize=12)
    ax.text(1740, -.83, "Parsed", ha="right", fontsize=12, fontweight="bold")
    ax.text(2210, -.83, "Yield", ha="right", fontsize=12, fontweight="bold")
    for ext in ("pdf", "png", "svg"):
        fig.savefig(output_dir / f"fig01_corpus_composition_and_yield.{ext}", dpi=300)
    plt.close(fig)

    cats = ["INSTRUMENTS", "VOICE", "MUSIC_CONCEPTS", "DANCE", "PERFORMANCE", "SOUND"]
    grouped = Counter((row["source_dictionary"], row["category"]) for row in selected)
    values = np.array([[100 * grouped[s, c] / count[s] for c in cats] for s in sources])
    masked = np.ma.array(values, mask=np.array([[count[s] < 2] * len(cats) for s in sources]))
    cmap = plt.colormaps["Blues"].copy()
    cmap.set_bad("#eeeeee")
    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.subplots_adjust(left=.36, right=.98, top=.78, bottom=.08)
    ax.imshow(masked, cmap=cmap, norm=Normalize(0, 100), aspect="auto")
    ax.set_xticks(range(len(cats)), ["Instruments", "Voice", "Music\nconcepts", "Dance", "Performance", "Sound"], fontsize=11)
    ax.set_yticks(range(len(sources)), [f"{SOURCE_LABELS[s]}\nn = {count[s]:,}" for s in sources], fontsize=11)
    ax.xaxis.tick_top()
    ax.tick_params(length=0, pad=9)
    for i, source in enumerate(sources):
        for j in range(len(cats)):
            label = "-" if count[source] < 2 else f"{values[i, j]:.1f}"
            ax.text(j, i, label, ha="center", va="center", fontsize=12,
                    color="white" if values[i, j] >= 60 and count[source] > 1 else "#202020")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.36, .94, "Within-source category percentages", fontsize=14)
    fig.text(.36, .88, "Darker cells indicate larger shares; n = selected records.", fontsize=11)
    for ext in ("pdf", "png", "svg"):
        fig.savefig(output_dir / f"fig02_category_profiles_heatmap.{ext}", dpi=300)
    plt.close(fig)


def notebook():
    md = nbformat.v4.new_markdown_cell
    code = nbformat.v4.new_code_cell
    book = nbformat.v4.new_notebook(cells=[
        md("# Lexicon C19 revision experiments\n\nTwo author-run retrieval workflows and rule-order sensitivity tests on the unchanged v3.2.1 release (DOI 10.5281/zenodo.22207277). These are reproducibility demonstrations, not independent user tests or new annotation. Put the downloaded Zenodo ZIP beside this notebook, or set ARCHIVE to its location. Requires Python 3.10+, pandas, NumPy, Matplotlib, and Jupyter. The standalone audit_release.py uses only the standard library."),
        code('from pathlib import Path\nimport json\nimport pandas as pd\nimport audit_release\nfrom prepare_revision_assets import figures\n\nfilename = "Lexicon_C19_Export_Package_v3.2.1_2026-08-31.zip"\ncandidates = [Path(filename)] + [parent / "zenodo_export_v3.2.1" / filename for parent in Path.cwd().parents]\nARCHIVE = next((p for p in candidates if p.is_file()), None)\nassert ARCHIVE is not None, "Download the v3.2.1 Zenodo ZIP and set ARCHIVE."\nOUTPUT = Path("notebook_diagnostics")\n'),
        md("## Verify the frozen release and rerun the tests\n\nThe baseline must reproduce every deposited category/subcategory label before any perturbation is interpreted. The CSV and JSONL remain unchanged. The following cell reruns the rule matching and 100 seeded order permutations; it may take about a minute."),
        code('evidence = audit_release.main(ARCHIVE, OUTPUT)\nassert evidence["archive_md5"] == "18cc1f3ec73d8602318dab35a2cac571"\nassert evidence["baseline_category_and_subcategory_mismatches"] == 0\n{k: evidence[k] for k in ["selected_records", "complete_candidates", "keyword_rule_count", "top_level_collision_records", "label_pair_collision_records"]}'),
        md("## Workflow A Browse lute-related candidates in the selected index\n\nUse the non-empty language cells of the lute alignment row as exact word-boundary queries in headword plus definition. The alignment is a browsing list, not a validated translation resource. Inspect the German Alphabēt result: Laute can denote speech sounds rather than the instrument. Return to the provider source before historical quotation."),
        code('a = pd.read_csv(OUTPUT / "lute_browsing_from_selected.csv")\ndisplay(a.groupby("source_dictionary").size().rename("returned_candidates").to_frame())\ndisplay(a.loc[a["id"].isin(["DE-MEYERS-1885-00036", "DE-MEYERS-1885-00243"]), ["id", "headword", "definition", "source_file", "source_line_start"]])'),
        md("## Workflow B Search beyond the selected index\n\nThe broader musician query searches all parsed candidates, including GENERAL/OTHER. It does not automatically promote them to relevant records. Compare the Kunstpfeifer example with the original selection policy. Missing entries from the printed dictionaries remain outside this parsed pool."),
        code('b = pd.read_csv(OUTPUT / "musician_query_in_complete_pool.csv")\ndisplay(b.groupby("in_selected_index").size().rename("returned_candidates").to_frame())\ndisplay(b.loc[b["id"] == "DE-MEYERS-1885-00235", ["id", "headword", "definition", "category", "source_file", "source_line_start"]])\nevidence["retrieval_demonstrations"]["musician_query_in_complete_pool"]["query_terms"]'),
        md("## Order sensitivity\n\nReversal and random shuffles change labels, not selection membership. Top-level categories and category/subcategory pairs are reported separately. The 100 shuffles are a deterministic stress test, not a sampling confidence interval or an accuracy benchmark."),
        code('sensitivity = pd.read_csv(OUTPUT / "order_sensitivity.csv")\ndisplay(sensitivity.iloc[:1])\ndisplay(sensitivity.iloc[1:][["top_level_changed", "label_pair_changed", "subcategory_only_changed"]].agg(["min", "median", "max"]))\nassert sensitivity["selected_membership_changed"].eq(0).all()'),
        md("## Companion metadata and relation construction\n\nThe 27 alignment rows come from three JSON mappings and 24 fixed extras. The 527 SAME_FAMILY edges enumerate pairs within predefined groups; their counts and weights are not corpus observations. The 12 cross-domain suggestions have no per-edge source evidence and should not be used as historical findings."),
        code('display(pd.Series(evidence["alignment_populated_cells_by_language"], name="populated_cells").to_frame())\ndisplay(pd.Series(evidence["relation_types"], name="rows").to_frame())\ngroups = pd.read_csv(OUTPUT / "semantic_group_sizes.csv")\ndisplay(groups[["group", "term_count", "expected_pair_count", "observed_pair_count"]])\nassert groups["expected_pair_count"].sum() == groups["observed_pair_count"].sum() == 527\nassert evidence["same_family_expected_from_group_pairs"] == 527'),
        md("## Release coverage and processed-file provenance\n\nThese tables are reconstructed from the frozen release, not from newly acquired web pages. The coverage flag identifies processed source traditions; the older Fetis inventory entry is not counted as the later edition. The 19-file table separates recorded inventory identifiers from filename hints. A matching name is not proof of upstream byte identity. Historical retrieval dates, OCR-engine versions and Wikisource revision IDs remain unrecorded. Current revision IDs must not be substituted for acquisition history."),
        code('coverage = pd.read_csv(OUTPUT / "inventory_release_coverage.csv")\nprovenance = pd.read_csv(OUTPUT / "processed_file_provenance.csv", keep_default_na=False)\ndisplay(coverage.loc[coverage["present_in_release"], ["inventory_id", "declaration_file", "complete_candidates", "selected_records"]])\ndisplay(provenance[["source_file", "recorded_inventory_ia_item", "filename_ia_item_hint", "locator_status"]])\nassert coverage["complete_candidates"].sum() == provenance["complete_candidates"].sum() == 25186\nassert coverage["selected_records"].sum() == provenance["selected_records"].sum() == 3760\nassert len(provenance) == 19\nassert provenance["historical_retrieval_date"].eq("not_recorded").all()\nassert provenance["upstream_revision_id"].eq("not_recorded").all()'),
        md("## Publication figures\n\nThe figures are regenerated from the same frozen tables, with larger labels. The one-record Vieira category profile is masked; the record itself is not removed. These refreshed graphics belong to the revision supplement, not to the earlier Zenodo archive."),
        code('from IPython.display import Image, display\nfigures(ARCHIVE, OUTPUT / "figures")\nfor name in ["fig01_corpus_composition_and_yield", "fig02_category_profiles_heatmap"]:\n    display(Image(filename=str(OUTPUT / "figures" / (name + ".png")), width=900))'),
        md("## Interpretation and limits\n\nThe lute workflow retrieves 33 candidates; the broader musician query retrieves 430, of which 407 are outside the selected index. Neither result is a new relevance estimate. Reversal changes 191 broad labels and 317 full label pairs. Missing OCR engine/model provenance and absent CER/WER ground truth remain unresolved in the deposited release. No new source acquisition, human annotation, ontology formalisation, or dataset publication is performed by this notebook.")
    ])
    book.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbformat.write(book, HERE / "04_revision_reuse_examples.ipynb")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ZIP)
    parser.add_argument("--figures-dir", type=Path, default=HERE / "manuscript")
    args = parser.parse_args()
    figures(args.archive, args.figures_dir)
    notebook()
