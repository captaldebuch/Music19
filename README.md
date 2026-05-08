# Music19: Lexicon of Performance

This folder contains the processing pipeline for the **Music19** project, focusing on the evolution of musical terminology from the Medieval period to the 19th century.

## 🚀 Main Components

- **`scripts/build_dataset.py`**: The core extraction pipeline. It handles OCR noise filtering, multilingual concept alignment, and generates semantic relation networks.
- **`scripts/graph_builder.py`**: Constructs Knowledge Graphs from extracted musical terms.
- **`scripts/topic_modeler.py`**: Performs LDA and other topic modeling techniques on the musicological corpus.
- **`notebooks/`**: Contains exploratory data analysis and visualization of the results.

## 📊 Data Requirements
This project processes a large corpus of JSON and PDF files. Due to size and copyright, the raw corpus is not included. The scripts expect a `corpus/` directory in the project root.
