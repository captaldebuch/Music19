import os
import json
import re
import csv

def load_taxonomy(path):
    with open(path, 'r') as f:
        return json.load(f)

def extract_entities(text):
    """
    Extract named performers, composers, and instrument makers.
    Uses regex heuristics for baseline extraction.
    """
    entities = []
    # Match capitalized names after specific keywords
    composer_pattern = re.compile(r'(?:composed by|music by|written by|composer) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)', re.IGNORECASE)
    maker_pattern = re.compile(r'(?:made by|maker|built by|invented by) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)', re.IGNORECASE)
    performer_pattern = re.compile(r'(?:performed by|sung by|singer|dancer) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)', re.IGNORECASE)
    
    for match in composer_pattern.finditer(text):
        entities.append(f"Composer: {match.group(1)}")
    for match in maker_pattern.finditer(text):
        entities.append(f"Maker: {match.group(1)}")
    for match in performer_pattern.finditer(text):
        entities.append(f"Performer: {match.group(1)}")
        
    return "; ".join(set(entities)) if entities else "None"

def tag_semantic_field(text):
    """
    Simulated LLM semantic tagging using keyword heuristics for emotional and social metadata.
    """
    text_lower = text.lower()
    tags = []
    
    semantic_map = {
        "Sacred": ["church", "mass", "god", "liturgy", "sacred", "holy", "divine", "prayer"],
        "Mournful": ["sad", "mourn", "dirge", "funeral", "elegy", "weep", "sorrow"],
        "Peasant/Folk": ["peasant", "folk", "village", "rustic", "rural", "country"],
        "Courtly/Elite": ["court", "king", "royal", "noble", "elite", "aristocrat"],
        "Festive": ["festival", "feast", "celebration", "joy", "dance", "merry"]
    }
    
    for tag, keywords in semantic_map.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
            
    return "; ".join(tags) if tags else "Neutral"

def extract_entries_from_text(text, dictionary_id, inventory_item):
    """
    Surgically extract headwords and definitions using regex.
    """
    # Pattern: Line start, 2-50 uppercase letters/spaces/punctuation, period/comma, space
    # Ensuring no newlines in the headword part.
    pattern = re.compile(r'^([A-Z\s\.,\-\(\)\']{2,60})[\.,]\s+(.+)$', re.MULTILINE)
    
    entries = []
    matches = pattern.finditer(text)
    
    for match in matches:
        headword = match.group(1).strip()
        definition = match.group(2).strip()
        
        # Additional validation:
        if "\n" in headword or len(headword) < 2:
            continue
            
        # Clean headword
        clean_headword = re.sub(r'[\.,]$', '', headword).strip()
        
        # Filter out common noise like "PAGE", "VOLUME", "INDEX"
        if clean_headword in ["THE", "OF", "AND", "TO", "A", "IN", "THAT", "IS", "WITH"]:
            continue
            
        entries.append({
            "id": f"{dictionary_id}-{len(entries)+1:05d}",
            "language": inventory_item['language'],
            "headword": clean_headword,
            "normalized_headword": clean_headword.lower(),
            "definition": definition,
            "entities": extract_entities(definition),
            "semantic_tags": tag_semantic_field(definition),
            "source_dictionary": inventory_item['title'],
            "author": inventory_item['author'],
            "publication_year": inventory_item['year'],
            "source_text": match.group(0)
        })
    
    return entries

def categorize_entry(entry, taxonomy):
    """
    Assign category and subcategory based on keywords in headword/definition.
    """
    content = (entry['headword'] + " " + entry['definition']).lower()
    
    for category, terms in taxonomy['categories'].items():
        if isinstance(terms, list):
            for term in terms:
                if term.lower() in content:
                    entry['category'] = category
                    entry['subcategory'] = term
                    return
        elif isinstance(terms, dict):
            for subcat, subterms in terms.items():
                for term in subterms:
                    if term.lower() in content:
                        entry['category'] = category
                        entry['subcategory'] = f"{subcat}: {term}"
                        return
    
    entry['category'] = "GENERAL"
    entry['subcategory'] = "OTHER"

def main():
    taxonomy = load_taxonomy('metadata/performance_taxonomy.json')
    with open('metadata/dictionary_inventory.json', 'r') as f:
        inventory = {item['id']: item for item in json.load(f)}
    
    results = []
    
    # Mapping directory names to inventory IDs
    dir_to_id = {
        "completeencyclop00moor": "EN-MOORE-1854",
        "dictionaryofmusi00riem": "DE-RIEMANN-1882", # Using the ID from inventory
        "dictionaryofmusi01grovuoft": "EN-GROVE-1879"
    }
    
    for dir_name, inv_id in dir_to_id.items():
        dir_path = os.path.join('data_ocr', dir_name)
        if not os.path.exists(dir_path): continue
        
        for file_name in os.listdir(dir_path):
            if file_name.endswith('.txt'):
                file_path = os.path.join(dir_path, file_name)
                print(f"Extracting from {file_path}...")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                inv_item = inventory[inv_id]
                entries = extract_entries_from_text(text, inv_id, inv_item)
                
                for entry in entries:
                    categorize_entry(entry, taxonomy)
                    results.append(entry)
                
                print(f"Found {len(entries)} entries.")

    # Save to CSV
    output_path = 'datasets/master_performance_dataset.csv'
    keys = ["id", "language", "headword", "normalized_headword", "category", "subcategory", "entities", "semantic_tags", "definition", "source_dictionary", "author", "publication_year", "source_text"]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Total entries extracted: {len(results)}")
    print(f"Dataset saved to {output_path}")

if __name__ == "__main__":
    main()
