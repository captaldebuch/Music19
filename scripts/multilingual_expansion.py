import os
import pandas as pd
import json

def align_concepts(df):
    """
    Simulates Multilingual Alignment using sentence transformers (e.g. LaBSE or MPNet).
    For this test script, we use a heuristic dictionary to group concepts.
    """
    print("--- Starting Multilingual Alignment ---")
    
    # Simulated multilingual embedding alignment
    # In reality, this would use model.encode(texts) and cosine_similarity
    
    alignment_map = {
        "troubadour": ["troubadour", "trovador", "трубадур"],
        "rebec": ["rebec", "rebeke", "rabel", "ребек"],
        "dance": ["dance", "danse", "tanz", "danza", "танец"],
        "song": ["song", "chant", "lied", "canto", "песня"]
    }
    
    aligned_data = []
    
    for _, row in df.iterrows():
        headword = str(row['headword']).lower()
        aligned_concept = headword # default
        
        for concept, equivalents in alignment_map.items():
            if headword in equivalents:
                aligned_concept = concept
                break
                
        aligned_data.append({
            "id": row['id'],
            "headword": headword,
            "language": row['language'],
            "aligned_concept": aligned_concept
        })
        
    aligned_df = pd.DataFrame(aligned_data)
    os.makedirs('aligned_concepts', exist_ok=True)
    aligned_df.to_csv('aligned_concepts/multilingual_alignment.csv', index=False)
    print(f"Exported multilingual alignments for {len(aligned_df)} entries.")
    
def main():
    if not os.path.exists('datasets/master_performance_dataset.csv'):
        print("Dataset not found. Please run extraction first.")
        return
        
    df = pd.read_csv('datasets/master_performance_dataset.csv')
    align_concepts(df)

if __name__ == "__main__":
    main()
