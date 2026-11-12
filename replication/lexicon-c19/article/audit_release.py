"""Read the frozen Zenodo ZIP and write separate revision diagnostics.

No source tables, annotations, manuscripts, or deposited files are modified.
Run with Python 3.10+; only the standard library is required.
"""

import ast
import argparse
import csv
import hashlib
import io
import json
import random
import re
import statistics
import sys
import zipfile
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE
ZIP = ROOT / "zenodo_export_v3.2.1/Lexicon_C19_Export_Package_v3.2.1_2026-08-31.zip"
OUT = HERE / "diagnostics"
SEED = 4566439
N_PERMUTATIONS = 100


def write_csv(name, rows, fields):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def supporting_tables(tree, inventory, pool, selected, groups, relations):
    """Expose construction and locator evidence without treating hints as history."""
    group_rows = []
    for group, terms in groups.items():
        observed = [r for r in relations if r["group"] == group and r["relation_type"] == "SAME_FAMILY"]
        expected = {frozenset((a, b)) for i, a in enumerate(terms) for b in terms[i + 1:]}
        assert len(terms) == len(set(terms))
        assert len(observed) == len(expected) == len(terms) * (len(terms) - 1) // 2
        assert {frozenset((r["source"], r["target"])) for r in observed} == expected
        group_rows.append({"group": group, "term_count": len(terms),
                           "expected_pair_count": len(expected), "observed_pair_count": len(observed),
                           "terms": json.dumps(terms, ensure_ascii=False)})
    assert sum(r["expected_pair_count"] for r in group_rows) == 527
    write_csv("semantic_group_sizes.csv", group_rows, list(group_rows[0]))

    # Read the deposited declarations, not the current local build implementation.
    main_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    extra = next(ast.literal_eval(n.value) for n in main_node.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "extra_inventory" for t in n.targets))
    source_ids = {
        "Complete Encyclopaedia of Music": "EN-MOORE-1854",
        "A Dictionary of Music and Musicians (A.D. 1450-1889)": "EN-GROVE-1879",
        "Musik-Lexikon": "DE-RIEMANN-1882",
        "Dictionnaire de la danse": "FR-DESRAT-1895",
        "Diccionario biographico de musicos portuguezes": "PT-VIEIRA-1900",
        "Biographie universelle des musiciens": "FR-FETIS-1860",
        "Meyers Konversations-Lexikon (Music Articles)": "DE-MEYERS-1885",
        "Brockhaus-Efron Encyclopaedia (Music Articles)": "RU-BROCKHAUS-1896",
    }
    assert set(source_ids) == {r["source_dictionary"] for r in pool}
    inventory_by_id = {r["id"]: r for r in inventory}
    assert "FR-FETIS-1860" not in inventory_by_id
    coverage = []
    for item in [*inventory, extra["FR-FETIS-1860"]]:
        sources = {s for s, identifier in source_ids.items() if identifier == item["id"]}
        coverage.append({"inventory_id": item["id"], "inventory_title": item["title"],
                         "declaration_file": "scripts/build_dataset.py" if item["id"] == "FR-FETIS-1860" else "metadata/dictionary_inventory.json",
                         "present_in_release": bool(sources),
                         "complete_candidates": sum(r["source_dictionary"] in sources for r in pool),
                         "selected_records": sum(r["source_dictionary"] in sources for r in selected),
                         "notes": "Different edition from the processed 1860-series witness; not counted as that witness."
                         if item["id"] == "FR-FETIS-1835" else "Counts aggregate processed files of this source tradition." if sources else "Not represented by this release's parsed candidates."})
    assert sum(r["complete_candidates"] for r in coverage) == len(pool)
    assert sum(r["selected_records"] for r in coverage) == len(selected)
    write_csv("inventory_release_coverage.csv", coverage, list(coverage[0]))

    files = Counter((r["source_dictionary"], r["source_file"]) for r in pool)
    selected_files = Counter((r["source_dictionary"], r["source_file"]) for r in selected)
    provenance = []
    for (source, filename), count in sorted(files.items()):
        item_id = source_ids[source]
        # The older Fetis entry supplies a related-work locator, not edition proof.
        locator_id = "FR-FETIS-1835" if item_id == "FR-FETIS-1860" else item_id
        item = inventory_by_id[locator_id]
        basename = Path(filename).name
        hint = basename.removesuffix("_djvu.txt") if basename.endswith("_djvu.txt") else ""
        recorded = item.get("ia_identifier") or ""
        if hint and hint == recorded:
            status = "inventory_and_filename_agree_not_byte_verified"
        elif hint:
            status = "filename_hint_differs_from_inventory_item"
        elif recorded:
            status = "related_inventory_item_only_file_mapping_unresolved"
        else:
            status = "collection_url_only_revision_unrecorded"
        notes = "No upstream byte match or acquisition timestamp established."
        if item_id == "FR-FETIS-1860":
            notes += " Locator is from the older Fetis project-inventory entry; it is not evidence for the edition or every volume."
        if item_id == "EN-GROVE-1879" and hint != recorded:
            notes += " Project inventory names volume 1; filename indicates a different volume."
        provenance.append({"source_dictionary": source, "source_file": filename,
                           "complete_candidates": count, "selected_records": selected_files[source, filename],
                           "locator_inventory_id": locator_id, "recorded_inventory_url": item.get("source_url") or "",
                           "recorded_inventory_ia_item": recorded, "processed_filename": basename,
                           "filename_ia_item_hint": hint, "locator_status": status,
                           "historical_retrieval_date": "not_recorded", "upstream_revision_id": "not_recorded",
                           "upstream_ocr_engine_version": "not_recorded", "raw_file_sha256": "not_in_release",
                           "evidence_files": "metadata/dictionary_inventory.json; scripts/build_dataset.py; validation/all_extracted_entries_v3_2.jsonl",
                           "notes": notes})
    assert len(provenance) == 19
    assert sum(r["complete_candidates"] for r in provenance) == len(pool)
    assert sum(r["selected_records"] for r in provenance) == len(selected)
    write_csv("processed_file_provenance.csv", provenance, list(provenance[0]))
    return {"semantic_group_rows": len(group_rows), "group_pair_sets_verified": True,
            "inventory_rows": len(coverage), "present_source_traditions": sum(r["present_in_release"] for r in coverage),
            "processed_file_rows": len(provenance), "historical_retrieval_dates_recovered": 0,
            "upstream_revision_ids_recovered": 0, "source": "frozen_release_only"}


def main(archive_path=None, output_dir=None):
    global OUT
    archive_path = Path(archive_path) if archive_path else ZIP
    if output_dir:
        OUT = Path(output_dir)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        script_bytes = archive.read("scripts/build_dataset.py")
        selected_bytes = archive.read("datasets/master_performance_dataset_v3_2.csv")
        pool_bytes = archive.read("validation/all_extracted_entries_v3_2.jsonl")
        selected = list(csv.DictReader(io.StringIO(selected_bytes.decode("utf-8"))))
        pool = [json.loads(line) for line in pool_bytes.decode("utf-8").splitlines() if line.strip()]
        alignments = list(csv.DictReader(io.StringIO(archive.read("datasets/multilingual_lexicon.csv").decode("utf-8"))))
        relations = list(csv.DictReader(io.StringIO(archive.read("datasets/semantic_relations.csv").decode("utf-8"))))
        taxonomy = json.loads(archive.read("metadata/performance_taxonomy.json"))
        inventory = json.loads(archive.read("metadata/dictionary_inventory.json"))
    assert hashlib.sha256(selected_bytes).hexdigest() == "a82a89cde3125edd5fa2009fcb2a4da6acc1c2509bed22c03eccb67211054374"
    assert hashlib.sha256(pool_bytes).hexdigest() == "4dce413d982c9765c90f12c8d815349a81e30cd557f9aa2a264855f4d5ab5259"

    # Parse constants without executing the deposited build script or its main().
    tree = ast.parse(script_bytes.decode("utf-8"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"ONTOLOGY", "SEMANTIC_GROUPS"}:
                    constants[target.id] = ast.literal_eval(node.value)
    rules = list(constants["ONTOLOGY"].items())
    patterns = [re.compile(r"\b" + re.escape(term) + r"\b") for term, _ in rules]
    selected_ids = {row["id"] for row in selected}
    assert len(selected_ids) == len(selected) == 3760
    assert len({row["id"] for row in pool}) == len(pool) == 25186
    selected_by_id = {row["id"]: row for row in selected}
    for row in pool:
        assert row["predicted_relevant"] == (row["id"] in selected_ids)
        if row["id"] in selected_ids:
            assert all(str(row[field]) == value for field, value in selected_by_id[row["id"]].items())

    matches = []
    mismatches = []
    for row in pool:
        text = (row["headword"] + " " + row["definition"]).lower()
        hits = [i for i, pattern in enumerate(patterns) if pattern.search(text)]
        matches.append(hits)
        label = rules[hits[0]][1] if hits else ("GENERAL", "OTHER")
        if label != (row["category"], row["subcategory"]):
            mismatches.append(row["id"])
    if mismatches:
        raise RuntimeError(f"Frozen-rule baseline mismatch for {len(mismatches)} rows: {mismatches[:5]}")

    OUT.mkdir(parents=True, exist_ok=True)
    supporting = supporting_tables(tree, inventory, pool, selected, constants["SEMANTIC_GROUPS"], relations)
    write_csv("ordered_keyword_rules.csv", [
        {"rank": i + 1, "keyword": term, "category": label[0], "subcategory": label[1]}
        for i, (term, label) in enumerate(rules)
    ], ["rank", "keyword", "category", "subcategory"])

    collision_rows = []
    for row, hits in zip(pool, matches):
        cats = {rules[i][1][0] for i in hits}
        labels = {rules[i][1] for i in hits}
        if len(labels) > 1:
            collision_rows.append({
                "id": row["id"], "source_dictionary": row["source_dictionary"],
                "headword": row["headword"], "baseline_category": row["category"],
                "baseline_subcategory": row["subcategory"],
                "category_count": len(cats), "label_pair_count": len(labels),
                "matched_rules": json.dumps([rules[i][0] for i in hits], ensure_ascii=False),
            })
    write_csv("rule_collisions.csv", collision_rows, ["id", "source_dictionary", "headword", "baseline_category", "baseline_subcategory", "category_count", "label_pair_count", "matched_rules"])

    rng = random.Random(SEED)
    permutations = [("reverse_all_rules", list(reversed(range(len(rules)))))]
    for i in range(N_PERMUTATIONS):
        order = list(range(len(rules)))
        rng.shuffle(order)
        permutations.append((f"shuffle_{i + 1:03d}", order))
    sensitivity = []
    reverse_rows = []
    for name, order in permutations:
        rank = {index: position for position, index in enumerate(order)}
        changed_category = changed_pair = subcategory_only = 0
        for row, hits in zip(pool, matches):
            if not hits:
                continue
            label = rules[min(hits, key=rank.__getitem__)][1]
            cat_changed = label[0] != row["category"]
            pair_changed = label != (row["category"], row["subcategory"])
            changed_category += cat_changed
            changed_pair += pair_changed
            subcategory_only += pair_changed and not cat_changed
            if name == "reverse_all_rules" and pair_changed:
                reverse_rows.append({"id": row["id"], "headword": row["headword"], "baseline_category": row["category"], "baseline_subcategory": row["subcategory"], "reversed_category": label[0], "reversed_subcategory": label[1]})
        sensitivity.append({"permutation": name, "top_level_changed": changed_category,
                            "label_pair_changed": changed_pair, "subcategory_only_changed": subcategory_only,
                            "top_level_changed_percent_selected": round(100 * changed_category / len(selected), 4),
                            "label_pair_changed_percent_selected": round(100 * changed_pair / len(selected), 4),
                            "selected_membership_changed": 0})
    write_csv("order_sensitivity.csv", sensitivity, list(sensitivity[0]))
    write_csv("reverse_order_changed_labels.csv", reverse_rows, ["id", "headword", "baseline_category", "baseline_subcategory", "reversed_category", "reversed_subcategory"])

    # Demonstrations of retrieval, not relevance assessments or external-user tests.
    lute = next(row for row in alignments if row["concept"] == "lute")
    lute_terms = sorted({value.lower() for key, value in lute.items() if key != "concept" and value})
    queries = {
        "lute_browsing_from_selected": ("selected", lute_terms),
        "musician_query_in_complete_pool": ("complete_pool", ["musician", "musicians", "musicien", "musiciens", "musiker", "músico", "músicos", "музыкант", "музыканты"]),
    }
    retrieval_summary = {}
    for name, (scope, terms) in queries.items():
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")\b")
        rows = []
        for row in pool:
            if scope == "selected" and row["id"] not in selected_ids:
                continue
            text = (row["headword"] + " " + row["definition"]).lower()
            found = sorted(set(pattern.findall(text)))
            if found:
                rows.append({"id": row["id"], "in_selected_index": row["id"] in selected_ids,
                             "source_dictionary": row["source_dictionary"], "headword": row["headword"],
                             "category": row["category"], "subcategory": row["subcategory"],
                             "matched_terms": "; ".join(found), "definition": row["definition"],
                             "source_file": row["source_file"], "source_line_start": row["source_line_start"]})
        rows.sort(key=lambda row: row["id"])
        write_csv(name + ".csv", rows, ["id", "in_selected_index", "source_dictionary", "headword", "category", "subcategory", "matched_terms", "definition", "source_file", "source_line_start"])
        retrieval_summary[name] = {"scope": scope, "query_terms": terms, "returned": len(rows),
                                   "within_selected_index": sum(row["in_selected_index"] for row in rows),
                                   "outside_selected_index": sum(not row["in_selected_index"] for row in rows),
                                   "counts_by_source": dict(Counter(row["source_dictionary"] for row in rows)),
                                   "human_relevance_checked": False}

    shuffles = sensitivity[1:]
    ocr_metadata_fields = sorted({key for item in inventory for key in item if any(token in key.lower() for token in ("ocr", "cer", "wer", "engine", "model"))})
    summary = {
        "source_archive": archive_path.name,
        "archive_md5": hashlib.md5(archive_path.read_bytes()).hexdigest(),
        "input_sha256": {"selected_csv": hashlib.sha256(selected_bytes).hexdigest(), "candidate_jsonl": hashlib.sha256(pool_bytes).hexdigest(), "build_dataset_py": hashlib.sha256(script_bytes).hexdigest()},
        "python": sys.version, "selected_records": len(selected), "complete_candidates": len(pool),
        "selected_rows_identical_to_pool": True, "baseline_category_and_subcategory_mismatches": 0,
        "rdf_ontology_files_in_archive": [name for name in names if name.endswith((".rdf", ".ttl", ".owl", ".nt", ".n3", ".jsonld"))],
        "keyword_rule_count": len(rules), "keyword_counts_by_category": dict(Counter(label[0] for _, label in rules)),
        "top_level_collision_records": sum(row["category_count"] > 1 for row in collision_rows),
        "label_pair_collision_records": len(collision_rows),
        "reverse_order": sensitivity[0], "shuffle_seed": SEED, "shuffle_count": N_PERMUTATIONS,
        "shuffle_top_level_changed": {"min": min(row["top_level_changed"] for row in shuffles), "median": statistics.median(row["top_level_changed"] for row in shuffles), "max": max(row["top_level_changed"] for row in shuffles)},
        "shuffle_label_pair_changed": {"min": min(row["label_pair_changed"] for row in shuffles), "median": statistics.median(row["label_pair_changed"] for row in shuffles), "max": max(row["label_pair_changed"] for row in shuffles)},
        "alignment_rows": len(alignments), "alignment_taxonomy_rows": len(taxonomy["multilingual_alignment_targets"]),
        "alignment_extra_rows": len(alignments) - len(taxonomy["multilingual_alignment_targets"]),
        "alignment_populated_cells_by_language": {lang: sum(bool(row.get(lang)) for row in alignments) for lang in alignments[0] if lang != "concept"},
        "relation_rows": len(relations), "relation_types": dict(Counter(row["relation_type"] for row in relations)),
        "same_family_expected_from_group_pairs": sum(len(members) * (len(members) - 1) // 2 for members in constants["SEMANTIC_GROUPS"].values()),
        "relation_group_count": len(constants["SEMANTIC_GROUPS"]), "relation_fields": list(relations[0]),
        "supporting_tables": supporting,
        "upstream_ocr_metadata_field_names": ocr_metadata_fields,
        "raw_ocr_files_in_archive": [name for name in names if name.startswith("data_ocr/")],
        "retrieval_demonstrations": retrieval_summary,
        "limitations": ["Order perturbation measures label stability, not correctness.", "No new human annotation or OCR accuracy measurement.", "Queries demonstrate author-run workflows, not independently evaluated reusability.", "No deposited files or submitted manuscripts changed."],
    }
    (OUT / "evidence_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ZIP)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(main(args.archive, args.output_dir), ensure_ascii=False, indent=2))
