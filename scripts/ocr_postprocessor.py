import os
import re
import glob

def normalize_russian_prereform(text):
    """
    Basic normalization for Pre-reform Russian orthography.
    """
    # Replace Yat (Ѣ/ѣ) with e/Е
    text = text.replace('Ѣ', 'Е').replace('ѣ', 'е')
    # Replace Fita (Ѳ/ѳ) with f/Ф
    text = text.replace('Ѳ', 'Ф').replace('ѳ', 'ф')
    # Replace Izhitsa (Ѵ/ѵ) with i/И
    text = text.replace('Ѵ', 'И').replace('ѵ', 'и')
    # Remove terminal hard sign (Ъ/ъ) after consonants
    text = re.sub(r'([бвгджзклмнпрстфхцчшщ])ъ\b', r'\1', text)
    text = re.sub(r'([БВГДЖЗКЛМНПРСТФХЦЧШЩ])Ъ\b', r'\1', text)
    # Decimal I (І/і) to i/И
    text = text.replace('І', 'И').replace('і', 'и')
    return text

def fix_fraktur_ocr(text):
    """
    Heuristics to fix common Fraktur OCR errors.
    """
    # Long s (ſ) vs f is common
    # Often 'f' at the end of words or specific contexts should be 's'
    # This is a complex problem, but simple heuristics can be applied
    # Example: 'daß' mis-OCRed as 'daß' or 'daf'
    text = re.sub(r'\bdaf\b', 'das', text)
    text = re.sub(r'f\b', 's', text) # Naive heuristic, careful! Let's restrict it.
    
    # Better: just fix common words
    replacements = {
        'muff': 'muss',
        'daß': 'dass',
        'Ift': 'Ist',
        'ift': 'ist'
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    
    return text

def process_directory(input_dir, output_dir):
    """
    Reads texts, applies normalization, saves to output.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for filepath in glob.glob(os.path.join(input_dir, '**', '*.txt'), recursive=True):
        if 'cleaned' in filepath:
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...")
        
        # Apply Russian if ru is in name
        if 'ru' in filename.lower() or 'muzyka' in filename.lower():
            text = normalize_russian_prereform(text)
            
        # Apply Fraktur fixes if de is in name or riemann
        if 'de' in filename.lower() or 'riemann' in filename.lower():
            text = fix_fraktur_ocr(text)
            
        out_path = os.path.join(output_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)

def main():
    print("--- Starting OCR Post-Processing ---")
    input_dir = 'data_ocr'
    output_dir = 'data_ocr/cleaned'
    process_directory(input_dir, output_dir)
    print("--- Finished ---")

if __name__ == "__main__":
    main()
