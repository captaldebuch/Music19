import pandas as pd
import gensim
from gensim import corpora
from gensim.models import LdaModel
import spacy
import re

def preprocess_text(text, nlp, stop_words):
    """
    Clean, tokenize, and lemmatize text.
    """
    # Remove punctuation and numbers
    text = re.sub(r'[^\w\s]', '', str(text).lower())
    doc = nlp(text)
    # Filter out stopwords, short words, and non-alphabetic
    tokens = [token.lemma_ for token in doc if not token.is_stop and len(token.lemma_) > 2 and token.is_alpha]
    return tokens

def main():
    print("Loading dataset...")
    df = pd.read_csv('datasets/master_performance_dataset.csv')
    
    # We'll focus on performance-related entries first, or just use all for a broad view
    # For now, all entries.
    docs = df['definition'].tolist()
    
    print("Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_sm")
    except:
        print("Downloading en_core_web_sm...")
        import os
        os.system("python -m spacy download en_core_web_sm --quiet")
        nlp = spacy.load("en_core_web_sm")

    print("Preprocessing text (this may take a while)...")
    processed_docs = [preprocess_text(doc, nlp, nlp.Defaults.stop_words) for doc in docs[:2000]] # Limit to 2000 for speed in this test
    
    print("Building dictionary and corpus...")
    dictionary = corpora.Dictionary(processed_docs)
    # Filter extremes to reduce noise
    dictionary.filter_extremes(no_below=5, no_above=0.5)
    corpus = [dictionary.doc2bow(doc) for doc in processed_docs]
    
    print("Training LDA model...")
    num_topics = 10
    lda_model = LdaModel(corpus=corpus, id2word=dictionary, num_topics=num_topics, passes=10, random_state=42)
    
    print("\n--- Topics Identified ---")
    results = []
    for idx, topic in lda_model.print_topics(-1):
        print(f"Topic {idx}: {topic}")
        results.append(f"Topic {idx}: {topic}")
    
    # Save results
    os.makedirs('reports', exist_ok=True)
    with open('reports/topic_model_summary.md', 'w') as f:
        f.write("# Topic Modeling Results\n\n")
        f.write("Model: LDA (Gensim)\n")
        f.write(f"Dataset: {len(processed_docs)} entries from master_performance_dataset.csv\n\n")
        for res in results:
            f.write(f"- {res}\n")

if __name__ == "__main__":
    main()
