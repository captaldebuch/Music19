"""Build and execute the publication analysis notebook for Lexicon C19."""

from pathlib import Path

import nbformat as nbf
from nbconvert import HTMLExporter
from nbconvert.preprocessors import ExecutePreprocessor


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOK_DIR / "03_publication_analysis.ipynb"
EXECUTED_PATH = NOTEBOOK_DIR / "03_publication_analysis_executed.ipynb"
HTML_PATH = ROOT / "publications" / "analysis_outputs" / "Lexicon_C19_publication_analysis.html"


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


cells = [
    markdown(
        """
# Lexicon C19 publication analysis

**Dataset:** `master_performance_dataset_v3_2_candidate.csv`  
**Purpose:** technical validation, musicological exploration, and publication figures  
**Evidential status:** computational release candidate; no human content annotation is claimed

This notebook is the shared analytical record for the proposed *Data* Data Descriptor and the companion digital-heritage musicology article. It distinguishes **pipeline outputs** from historical prevalence. The eight source traditions differ in genre, language, digitisation, completeness, and sampling frame, so raw totals must not be read as direct measures of nineteenth-century musical importance.

The notebook is fully executable from the repository, exports publication figures in PNG, SVG, and PDF, writes reusable CSV tables, and creates a machine-readable analysis manifest.
"""
    ),
    code(
        """
from pathlib import Path
from collections import Counter
import hashlib
import json
import platform
import re

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path("..").resolve()
DATA_PATH = ROOT / "datasets" / "master_performance_dataset_v3_2_candidate.csv"
POOL_PATH = ROOT / "validation" / "all_extracted_entries_v3_2_candidate.jsonl"
OUT_DIR = ROOT / "publications" / "analysis_outputs"
FIG_DIR = OUT_DIR / "figures"
TABLE_DIR = OUT_DIR / "tables"
for directory in (OUT_DIR, FIG_DIR, TABLE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

SOURCE_SHORT = {
    "Complete Encyclopaedia of Music": "Moore (1854)",
    "A Dictionary of Music and Musicians (A.D. 1450-1889)": "Grove (1879-89)",
    "Musik-Lexikon": "Riemann/Shedlock (1908)",
    "Biographie universelle des musiciens": "Fetis/Pougin (1860)",
    "Dictionnaire de la danse": "Desrat (1895)",
    "Meyers Konversations-Lexikon (Music Articles)": "Meyers (1885-90)",
    "Brockhaus-Efron Encyclopaedia (Music Articles)": "Brockhaus-Efron (1896)",
    "Diccionario biographico de musicos portuguezes": "Vieira (1900)",
}
SOURCE_ORDER = [
    "Fetis/Pougin (1860)", "Moore (1854)", "Grove (1879-89)",
    "Meyers (1885-90)", "Desrat (1895)", "Brockhaus-Efron (1896)",
    "Vieira (1900)", "Riemann/Shedlock (1908)",
]
CATEGORY_ORDER = ["INSTRUMENTS", "PERFORMANCE", "VOICE", "MUSIC_CONCEPTS", "DANCE", "SOUND"]
COLORS = {
    "ink": "#243447", "blue": "#2667A8", "teal": "#2A9D8F", "gold": "#E9C46A",
    "coral": "#E76F51", "red": "#C44536", "violet": "#6C5B7B", "grey": "#74828F",
}
CATEGORY_COLORS = dict(zip(CATEGORY_ORDER, ["#3B6FB6", "#5E4FA2", "#2A9D8F", "#E9C46A", "#E76F51", "#74828F"]))

sns.set_theme(style="whitegrid", context="notebook")
mpl.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.titlesize": 14,
    "axes.labelsize": 10.5, "axes.titleweight": "bold", "axes.edgecolor": "#B7C0C8",
    "axes.linewidth": 0.8, "grid.color": "#E8ECEF", "grid.linewidth": 0.7,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "savefig.dpi": 320, "savefig.bbox": "tight", "svg.fonttype": "none",
})

def save_figure(fig, stem):
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(FIG_DIR / f"{stem}.{suffix}", bbox_inches="tight")
    plt.show()

print(f"Python {platform.python_version()} | pandas {pd.__version__} | matplotlib {mpl.__version__}")
"""
    ),
    markdown(
        """
## 1. Load the frozen release candidate

The selected table contains entries assigned by ordered multilingual keyword rules to one of six broad categories. The full candidate pool also retains `GENERAL/OTHER` spans and provides the denominator for extraction-yield diagnostics. Neither table is a manually annotated gold standard.
"""
    ),
    code(
        """
df = pd.read_csv(DATA_PATH, keep_default_na=True)
pool = pd.read_json(POOL_PATH, lines=True)
df["source_short"] = df["source_dictionary"].map(SOURCE_SHORT)
pool["source_short"] = pool["source_dictionary"].map(SOURCE_SHORT)

assert df["source_short"].notna().all(), "Unmapped source name in selected dataset"
assert pool["source_short"].notna().all(), "Unmapped source name in candidate pool"

sha256 = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
print(f"Selected records: {len(df):,} | fields: {df.shape[1] - 1} | source traditions: {df.source_short.nunique()}")
print(f"Parsed candidates: {len(pool):,} | selected: {pool.predicted_relevant.sum():,}")
print(f"Candidate CSV SHA-256: {sha256}")
df.head(3)
"""
    ),
    markdown(
        """
## 2. Structural and provenance checks

These tests support the integrity of the release package. They do **not** estimate entry-detection recall. A separate 200-record single-annotator audit completed on 31 August 2026 estimates selected-candidate precision and broad-category accuracy for sampled selected records only; full double annotation and page-recall measurement remain deferred to a later student internship.
"""
    ),
    code(
        """
required = [
    "id", "headword", "normalized_headword", "category", "subcategory", "definition",
    "source_dictionary", "source_file", "source_line_start", "source_text_language",
    "publication_year", "confidence_score", "article_type",
]
checks = [
    ("Expected row count", len(df) == 3760, f"{len(df):,}"),
    ("Required fields present", set(required).issubset(df.columns), f"{len(required)} checked"),
    ("Identifiers unique", df.id.is_unique, f"{df.id.duplicated().sum()} duplicates"),
    ("Identifiers non-empty", df.id.notna().all(), f"{df.id.isna().sum()} missing"),
    ("Local source provenance complete", df.source_file.notna().all(), f"{df.source_file.isna().sum()} missing"),
    ("Source line provenance complete", df.source_line_start.notna().all(), f"{df.source_line_start.isna().sum()} missing"),
    ("Category vocabulary controlled", set(df.category) <= set(CATEGORY_ORDER), ", ".join(sorted(df.category.unique()))),
    ("Confidence bounded 0-1", df.confidence_score.between(0, 1).all(), f"{df.confidence_score.min():.3f}-{df.confidence_score.max():.3f}"),
    ("Printed page field populated", df.page.notna().all(), f"{df.page.notna().sum():,}/{len(df):,}"),
]
checks_df = pd.DataFrame(checks, columns=["check", "passed", "detail"])
checks_df.to_csv(TABLE_DIR / "technical_validation_checks.csv", index=False)
checks_df
"""
    ),
    code(
        """
missing = (df.drop(columns="source_short").isna().mean() * 100).sort_values(ascending=False).rename("missing_percent")
missing.to_csv(TABLE_DIR / "field_missingness.csv", header=True)
display(missing.to_frame().head(12).round(1))

definition_lengths = df.definition.fillna("").str.len()
print(f"Definitions at the 800-character cap: {(definition_lengths >= 800).sum():,} ({(definition_lengths >= 800).mean():.1%})")
print(f"Median definition excerpt: {definition_lengths.median():.0f} characters")
"""
    ),
    markdown(
        """
## 3. Corpus composition and extraction yield

The corpus is strongly concentrated in three English-language processed witnesses. Candidate-to-selected ratios also vary by source because the inputs include full-volume OCR, specialist dictionaries, biographical dictionaries, and curated music-article collections. This figure is a diagnostic of the pipeline and sampling frames.
"""
    ),
    code(
        """
source_stats = (
    pool.groupby("source_short", observed=True)
    .agg(parsed_candidates=("id", "size"), selected_records=("predicted_relevant", "sum"))
    .assign(selection_rate=lambda x: x.selected_records / x.parsed_candidates)
    .reindex(SOURCE_ORDER)
)
source_stats["corpus_share"] = source_stats.selected_records / source_stats.selected_records.sum()
source_stats.to_csv(TABLE_DIR / "source_composition.csv")
source_stats.style.format({"selection_rate": "{:.1%}", "corpus_share": "{:.1%}"})
"""
    ),
    code(
        """
plot_stats = source_stats.sort_values("selected_records")
fig, axes = plt.subplots(1, 2, figsize=(13.5, 6), gridspec_kw={"width_ratios": [1.45, 1]})

y = np.arange(len(plot_stats))
axes[0].barh(y, plot_stats.parsed_candidates, color="#DDE5EB", height=0.68, label="Parsed candidates")
axes[0].barh(y, plot_stats.selected_records, color=COLORS["blue"], height=0.68, label="Selected records")
axes[0].set_yticks(y, plot_stats.index)
axes[0].set_xlabel("Records")
axes[0].set_title("A. Candidate and selected records")
axes[0].legend(frameon=False, loc="lower right")
axes[0].grid(axis="y", visible=False)

axes[1].barh(y, plot_stats.selection_rate * 100, color=COLORS["teal"], height=0.68)
axes[1].set_yticks(y, [])
axes[1].set_xlabel("Selected from parsed candidates (%)")
axes[1].set_title("B. Rule-based selection rate")
axes[1].grid(axis="y", visible=False)
for i, value in enumerate(plot_stats.selection_rate * 100):
    axes[1].text(value + 0.8, i, f"{value:.1f}%", va="center", fontsize=9)

fig.suptitle("Corpus composition reflects heterogeneous sampling frames", x=0.06, ha="left", fontsize=17, fontweight="bold")
fig.text(0.06, 0.01, "Counts are pipeline outputs, not estimates of historical prevalence.", color=COLORS["grey"], fontsize=10)
save_figure(fig, "fig01_corpus_composition_and_yield")
"""
    ),
    markdown(
        """
## 4. Source-specific category profiles

Within-source percentages make sources of different sizes visually comparable, but they remain shaped by the ordered keyword ontology and extraction process. The chart is most useful for identifying cases that merit close reading, such as Desrat's dance concentration or the prominence of performance-context labels in Fétis/Pougin.
"""
    ),
    code(
        """
category_counts = pd.crosstab(df.source_short, df.category).reindex(index=SOURCE_ORDER, columns=CATEGORY_ORDER, fill_value=0)
category_pct = category_counts.div(category_counts.sum(axis=1), axis=0) * 100
category_counts.to_csv(TABLE_DIR / "category_counts_by_source.csv")
category_pct.to_csv(TABLE_DIR / "category_percent_by_source.csv")

fig, ax = plt.subplots(figsize=(11.5, 6.2))
sns.heatmap(category_pct, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=0.8,
            linecolor="white", cbar_kws={"label": "Within-source share (%)"}, ax=ax)
ax.set_xlabel("")
ax.set_ylabel("")
ax.set_title("Rule-based category profiles vary sharply by source", loc="left", pad=16)
fig.text(0.125, 0.01, "Within-source percentages; Vieira has only one selected record and should not be compared inferentially.", color=COLORS["grey"])
save_figure(fig, "fig02_category_profiles_heatmap")
"""
    ),
    code(
        """
fig, ax = plt.subplots(figsize=(12.5, 6.5))
left = np.zeros(len(category_pct))
for category in CATEGORY_ORDER:
    values = category_pct[category].to_numpy()
    ax.barh(category_pct.index, values, left=left, label=category.replace("_", " ").title(),
            color=CATEGORY_COLORS[category], height=0.7)
    left += values
ax.set_xlim(0, 100)
ax.set_xlabel("Within-source category share (%)")
ax.set_ylabel("")
ax.set_title("Each source constructs a different computational profile", loc="left", pad=14)
ax.legend(ncol=3, frameon=False, bbox_to_anchor=(0, -0.14), loc="upper left")
ax.grid(axis="y", visible=False)
save_figure(fig, "fig03_category_profiles_stacked")
"""
    ),
    markdown(
        """
## 5. Confidence as an uncertainty proxy

`confidence_score` is a heuristic based on OCR surface features. It is not a calibrated probability and does not measure historical reliability. Its value is comparative: it reveals where the pipeline itself anticipates noisy text and where inspection should begin.
"""
    ),
    code(
        """
confidence_summary = df.groupby("source_short").confidence_score.agg(["count", "mean", "median", "std", "min", "max"]).reindex(SOURCE_ORDER)
confidence_summary["below_0_4_share"] = df.assign(low=df.confidence_score < 0.4).groupby("source_short").low.mean().reindex(SOURCE_ORDER)
confidence_summary.to_csv(TABLE_DIR / "confidence_by_source.csv")

fig, ax = plt.subplots(figsize=(12.5, 6.2))
plot_df = df[df.source_short != "Vieira (1900)"].copy()
sns.boxplot(data=plot_df, y="source_short", x="confidence_score", order=[s for s in SOURCE_ORDER if s != "Vieira (1900)"],
            color="#79B7B2", fliersize=1.5, linewidth=0.9, ax=ax)
ax.axvline(0.4, color=COLORS["red"], linestyle="--", linewidth=1.2, label="Documented low-confidence threshold")
ax.set_xlim(0, 1.01)
ax.set_xlabel("Heuristic OCR confidence score")
ax.set_ylabel("")
ax.set_title("OCR-confidence distributions differ by processed witness", loc="left", pad=14)
ax.legend(frameon=False, loc="lower right")
save_figure(fig, "fig04_confidence_by_source")
"""
    ),
    markdown(
        """
## 6. Rule-derived semantic tags

Semantic tags are transparent keyword matches rather than learned topics. The chart reports the share of records in each source receiving a given tag. It is suited to retrieval and comparison of pipeline behaviour, not to claims about national character or historical salience.
"""
    ),
    code(
        """
tag_rows = []
for _, row in df.iterrows():
    tags = [t.strip() for t in str(row.semantic_tags).split(";") if t.strip() and t.strip() != "Neutral"]
    for tag in tags:
        tag_rows.append((row.source_short, tag))
tags_df = pd.DataFrame(tag_rows, columns=["source_short", "tag"])
top_tags = tags_df.tag.value_counts().head(10).index.tolist()
tag_counts = pd.crosstab(tags_df.source_short, tags_df.tag).reindex(index=SOURCE_ORDER, columns=top_tags, fill_value=0)
tag_pct = tag_counts.div(df.source_short.value_counts().reindex(SOURCE_ORDER), axis=0) * 100
tag_pct.to_csv(TABLE_DIR / "semantic_tag_percent_by_source.csv")

fig, ax = plt.subplots(figsize=(12.5, 6.2))
sns.heatmap(tag_pct, annot=True, fmt=".1f", cmap="mako_r", linewidths=0.7, linecolor="white",
            cbar_kws={"label": "Records carrying tag (%)"}, ax=ax)
ax.set_xlabel("")
ax.set_ylabel("")
ax.set_title("Keyword-derived semantic signals are source-specific", loc="left", pad=14)
save_figure(fig, "fig05_semantic_tag_profiles")
"""
    ),
    markdown(
        """
## 7. Exact lexical overlap

The following Jaccard matrix compares sets of normalized headwords. Low overlap can arise from language differences, OCR corruption, translation, source genre, editorial policy, or genuinely different vocabulary. It therefore measures **surface interoperability**, not conceptual distance.
"""
    ),
    code(
        """
headword_sets = {
    source: set(group.normalized_headword.dropna().astype(str).str.strip()) - {""}
    for source, group in df.groupby("source_short")
}
jaccard = pd.DataFrame(index=SOURCE_ORDER, columns=SOURCE_ORDER, dtype=float)
for a in SOURCE_ORDER:
    for b in SOURCE_ORDER:
        union = headword_sets[a] | headword_sets[b]
        jaccard.loc[a, b] = len(headword_sets[a] & headword_sets[b]) / len(union) if union else np.nan
jaccard.to_csv(TABLE_DIR / "headword_jaccard.csv")

fig, ax = plt.subplots(figsize=(10.5, 8.2))
mask = np.triu(np.ones_like(jaccard, dtype=bool), k=1)
sns.heatmap(jaccard * 100, mask=mask, annot=True, fmt=".2f", cmap="crest", linewidths=0.8,
            linecolor="white", square=True, cbar_kws={"label": "Exact-headword Jaccard (%)", "shrink": 0.7}, ax=ax)
ax.set_xlabel("")
ax.set_ylabel("")
ax.set_title("Exact normalized-headword overlap is limited", loc="left", pad=14)
save_figure(fig, "fig06_exact_headword_overlap")
"""
    ),
    code(
        """
headword_sources = (
    df.groupby("normalized_headword")
    .agg(source_count=("source_short", "nunique"), record_count=("id", "size"),
         sources=("source_short", lambda x: "; ".join(sorted(set(x)))))
    .query("source_count >= 2")
    .sort_values(["source_count", "record_count"], ascending=False)
)
headword_sources.to_csv(TABLE_DIR / "cross_source_headwords.csv")
display(headword_sources.head(25))
"""
    ),
    markdown(
        """
## 8. Three musicological retrieval domains

Dance, voice, and instruments provide tractable entry points for source-specific close reading. The figure reports how records in each computational category are distributed across sources. It does not imply that the source with the most recovered records historically valued the domain most.
"""
    ),
    code(
        """
domains = ["DANCE", "VOICE", "INSTRUMENTS"]
domain_counts = category_counts[domains]
domain_within_category = domain_counts.div(domain_counts.sum(axis=0), axis=1) * 100
domain_within_category.to_csv(TABLE_DIR / "source_share_within_musicological_domains.csv")

fig, axes = plt.subplots(1, 3, figsize=(15, 6), sharey=True)
domain_colors = {"DANCE": COLORS["coral"], "VOICE": COLORS["teal"], "INSTRUMENTS": COLORS["blue"]}
for ax, domain in zip(axes, domains):
    vals = domain_within_category[domain].sort_values()
    ax.barh(vals.index, vals.values, color=domain_colors[domain], height=0.65)
    ax.set_title(domain.title())
    ax.set_xlabel("Share of selected domain records (%)")
    ax.grid(axis="y", visible=False)
    for i, value in enumerate(vals.values):
        if value >= 3:
            ax.text(value + 0.7, i, f"{value:.0f}%", va="center", fontsize=8)
axes[0].set_ylabel("")
fig.suptitle("Musicological retrieval domains have different source centres", x=0.06, ha="left", fontsize=17, fontweight="bold")
fig.text(0.06, 0.01, "Source shares within each rule-derived category; use as a guide to close reading.", color=COLORS["grey"])
save_figure(fig, "fig07_musicological_retrieval_domains")
"""
    ),
    markdown(
        """
## 9. Witness chronology and corpus scale

The processed witness date is not always the date of the original work. Most importantly, the local Riemann text is J. S. Shedlock's English translation (fourth edition, 1908) of a work first published in German in 1882. Analyses must identify it as a translation witness.
"""
    ),
    code(
        """
witness_year = {
    "Fetis/Pougin (1860)": 1860, "Moore (1854)": 1854, "Grove (1879-89)": 1884,
    "Meyers (1885-90)": 1888, "Desrat (1895)": 1895, "Brockhaus-Efron (1896)": 1896,
    "Vieira (1900)": 1900, "Riemann/Shedlock (1908)": 1908,
}
timeline = source_stats.copy()
timeline["witness_year"] = pd.Series(witness_year)
timeline.to_csv(TABLE_DIR / "witness_timeline.csv")

fig, ax = plt.subplots(figsize=(13, 5.8))
y = np.arange(len(SOURCE_ORDER))
sizes = 35 + 300 * np.sqrt(timeline.loc[SOURCE_ORDER, "selected_records"] / timeline.selected_records.max())
ax.hlines(y, 1835, [witness_year[s] for s in SOURCE_ORDER], color="#D6DDE2", linewidth=2)
ax.scatter([witness_year[s] for s in SOURCE_ORDER], y, s=sizes, color=COLORS["violet"], alpha=0.85, edgecolor="white", linewidth=1)
for i, source in enumerate(SOURCE_ORDER):
    year = witness_year[source]
    ax.text(year + 1.2, i, f"{year}  {source}", va="center", fontsize=9)
ax.set_yticks([])
ax.set_xlim(1833, 1935)
ax.set_xlabel("Approximate processed-witness year")
ax.set_title("The corpus spans unlike editions, translations, and reference genres", loc="left", pad=14)
ax.grid(axis="y", visible=False)
save_figure(fig, "fig08_witness_timeline")
"""
    ),
    markdown(
        """
## 10. Data Descriptor visual overview

This four-panel dashboard brings the main descriptive and quality-control views together for the Data Descriptor. It combines source and category composition with two diagnostics that should shape reuse: the relation between rule-selection rate and surface-confidence, and field completeness by source. As elsewhere in the notebook, plotted counts describe the released computational object rather than historical prevalence.
"""
    ),
    code(
        """
overall_categories = df.category.value_counts().reindex(CATEGORY_ORDER, fill_value=0)
overall_category_pct = overall_categories / overall_categories.sum() * 100
quality_fields = [
    "headword", "definition", "source_file", "source_line_start", "confidence_score",
    "semantic_tags", "geographic_refs", "historical_refs", "etymology", "cross_refs",
]
field_completeness = (
    df.assign(**{field: df[field].notna() for field in quality_fields})
    .groupby("source_short")[quality_fields]
    .mean()
    .reindex(SOURCE_ORDER) * 100
)
field_completeness.to_csv(TABLE_DIR / "field_completeness_by_source.csv")

overview = source_stats.join(confidence_summary[["median"]].rename(columns={"median": "median_confidence"}))
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.08], hspace=0.38, wspace=0.28)

ax = fig.add_subplot(gs[0, 0])
source_plot = source_stats.selected_records.sort_values()
ax.barh(source_plot.index, source_plot.values, color=COLORS["blue"], height=0.66)
ax.set_title("A. Selected records by processed witness", loc="left")
ax.set_xlabel("Rule-selected records")
ax.grid(axis="y", visible=False)
for i, value in enumerate(source_plot.values):
    ax.text(value + 18, i, f"{value:,}", va="center", fontsize=8.5)
ax.set_xlim(0, source_plot.max() * 1.18)

ax = fig.add_subplot(gs[0, 1])
category_plot = overall_categories.sort_values()
category_color_plot = [CATEGORY_COLORS[c] for c in category_plot.index]
ax.barh([c.replace("_", " ").title() for c in category_plot.index], category_plot.values,
        color=category_color_plot, height=0.66)
ax.set_title("B. Overall rule-derived category composition", loc="left")
ax.set_xlabel("Selected records")
ax.grid(axis="y", visible=False)
for i, (count, pct) in enumerate(zip(category_plot.values, overall_category_pct[category_plot.index])):
    ax.text(count + 18, i, f"{count:,} ({pct:.1f}%)", va="center", fontsize=8.5)
ax.set_xlim(0, category_plot.max() * 1.25)

ax = fig.add_subplot(gs[1, 0])
bubble_sizes = 70 + 420 * np.sqrt(overview.selected_records / overview.selected_records.max())
ax.scatter(overview.selection_rate * 100, overview.median_confidence, s=bubble_sizes,
           c=COLORS["teal"], alpha=0.82, edgecolors="white", linewidths=1.2)
label_offsets = {
    "Fetis/Pougin (1860)": (-10, -16),
    "Moore (1854)": (8, 9),
    "Grove (1879-89)": (8, -15),
    "Meyers (1885-90)": (7, 7),
    "Desrat (1895)": (8, -14),
    "Brockhaus-Efron (1896)": (7, -6),
    "Vieira (1900)": (7, 6),
    "Riemann/Shedlock (1908)": (-4, -17),
}
for source, row in overview.iterrows():
    short_label = source.replace("Riemann/Shedlock", "Riemann").replace("Brockhaus-Efron", "Brockhaus")
    offset = label_offsets[source]
    ax.annotate(short_label.split(" (")[0], (row.selection_rate * 100, row.median_confidence),
                xytext=offset, textcoords="offset points", fontsize=8)
ax.set_xlabel("Rule-based selection rate (%)")
ax.set_ylabel("Median OCR-surface confidence")
ax.set_ylim(0.25, 1.06)
ax.set_title("C. Selection yield and surface quality are distinct", loc="left")

ax = fig.add_subplot(gs[1, 1])
sns.heatmap(field_completeness, cmap="YlGnBu", vmin=0, vmax=100, linewidths=0.45,
            linecolor="white", cbar_kws={"label": "Populated records (%)", "shrink": 0.82}, ax=ax)
ax.set_title("D. Field completeness by processed witness", loc="left")
ax.set_xlabel("")
ax.set_ylabel("")
ax.set_xticklabels([x.replace("_", " ") for x in quality_fields], rotation=42, ha="right", fontsize=8)
ax.set_yticklabels(ax.get_yticklabels(), fontsize=8)

fig.suptitle("Lexicon C19 v3.2 at a glance", x=0.055, ha="left", fontsize=20, fontweight="bold")
fig.text(0.055, 0.015,
         "Selected records, categories, and quality diagnostics are outputs of heterogeneous source and extraction pipelines.",
         color=COLORS["grey"], fontsize=10)
save_figure(fig, "fig09_data_descriptor_overview")
"""
    ),
    markdown(
        """
## 11. Reproducible findings and limitations

The quantitative evidence supports a methodological and critical interpretation:

1. **Composition:** Moore, Grove, and the Riemann/Shedlock translation dominate the selected table; aggregate totals largely describe those processed witnesses.
2. **Recoverability:** selection rates differ sharply across source pipelines and input genres, making direct count comparison unsafe.
3. **Computational profiles:** category and tag distributions can identify passages and contrasts for close reading, especially Desrat's dance vocabulary, but cannot establish historical prevalence without source-level recall estimates.
4. **Interoperability:** exact lexical overlap is low and confounded by multilingualism, translation, OCR, and editorial genre.
5. **Known gaps:** page is empty, definitions are excerpted, Fétis main-series volume 1 is absent, Vieira extraction is effectively non-analytical, and confidence is uncalibrated.
6. **Deferred validation:** human content annotation and page-level recall estimation are planned as a later internship deliverable and are not claimed for this release.

This bounded evidential position is suitable for a transparent computational dataset release. It also motivates a musicological article on how reference genres and digitisation pipelines shape the historical categories that become searchable and countable.
"""
    ),
    code(
        """
summary = {
    "generated_utc": pd.Timestamp.utcnow().isoformat(),
    "dataset": DATA_PATH.name,
    "dataset_sha256": sha256,
    "selected_records": int(len(df)),
    "fields": int(df.shape[1] - 1),
    "parsed_candidates": int(len(pool)),
    "source_traditions": int(df.source_short.nunique()),
    "duplicate_ids": int(df.id.duplicated().sum()),
    "records_with_page": int(df.page.notna().sum()),
    "definitions_at_800_char_cap": int((definition_lengths >= 800).sum()),
    "largest_three_source_share": float(df.source_short.value_counts().head(3).sum() / len(df)),
    "figure_stems": sorted({p.stem for p in FIG_DIR.glob("*.png")}),
    "table_files": sorted(p.name for p in TABLE_DIR.glob("*.csv")),
    "human_annotation_status": "200-record single-annotator audit complete as article-level evidence; full double annotation and page recall deferred",
    "manual_audit_sample_size": 200,
    "manual_audit_completed": 200,
    "manual_audit_real_relevant": 194,
    "manual_audit_selection_precision": 0.970,
    "manual_audit_category_accuracy": 0.897,
    "html_report": "Lexicon_C19_publication_analysis.html",
}
(OUT_DIR / "analysis_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

lines = [
    "# Lexicon C19 analysis summary", "",
    f"- Dataset: `{summary['dataset']}`", f"- SHA-256: `{sha256}`",
    f"- Selected records: {len(df):,}", f"- Parsed candidates: {len(pool):,}",
    f"- Source traditions: {df.source_short.nunique()}",
    f"- Largest three sources: {summary['largest_three_source_share']:.1%} of selected records",
    f"- Duplicate identifiers: {summary['duplicate_ids']}",
    f"- Records with printed page: {summary['records_with_page']}",
    f"- Definitions at 800-character cap: {summary['definitions_at_800_char_cap']:,}",
    "- Manual audit: 200/200 rows complete; selected-candidate precision 97.0%; broad-category accuracy 89.7%", "",
    "## Outputs", "",
    f"- Figures: {len(summary['figure_stems'])} designs in PNG, SVG, and PDF",
    f"- Tables: {len(summary['table_files'])} CSV files",
    "- Executed notebook: `notebooks/03_publication_analysis_executed.ipynb`", "",
    "## Interpretation rule", "",
    "All counts and profiles are outputs of heterogeneous OCR, segmentation, and ordered keyword rules. They are evidence about the released computational resource and starting points for source-specific close reading, not direct measures of historical prevalence.",
]
(OUT_DIR / "ANALYSIS_SUMMARY.md").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
summary
"""
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
        "title": "Lexicon C19 publication analysis",
    },
)
NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, NOTEBOOK_PATH)

executor = ExecutePreprocessor(timeout=600, kernel_name="python3")
executor.preprocess(notebook, {"metadata": {"path": str(NOTEBOOK_DIR)}})
nbf.write(notebook, EXECUTED_PATH)

exporter = HTMLExporter(template_name="lab")
html, _ = exporter.from_notebook_node(notebook)
HTML_PATH.write_text(html, encoding="utf-8")

print(f"Wrote {NOTEBOOK_PATH}")
print(f"Wrote {EXECUTED_PATH}")
print(f"Wrote {HTML_PATH}")
