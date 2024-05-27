from flask import Flask, request, render_template
from strsimpy.jaro_winkler import JaroWinkler
import json
import os
import re

app = Flask(__name__)

# Load dictionary from JSON file
def load_dictionary_from_json():
    current_directory = os.path.dirname(__file__)
    json_file_path = os.path.join(current_directory, 'dictionary.json')

    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return set(map(str, data))

dictionary = load_dictionary_from_json()
jaro = JaroWinkler()

def jarowinkler(str1, str2):
    len1, len2 = len(str1), len(str2)
    max_len = max(len1, len2)
    if max_len == 0:
        return 0.0

    max_dist = max_len // 2 - 1
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if str1[i] == str2[j]:
                s1_matches[i] = s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    si = sj = 0
    for i in range(len1):
        if s1_matches[i]:
            while not s2_matches[sj]:
                sj += 1
            if str1[i] != str2[sj]:
                transpositions += 1
            sj += 1

    transpositions //= 2

    common_chars = sum(1 for s1, s2 in zip(str1, str2) if s1 == s2)
    jaro = ((matches / len1 + matches / len2 + (matches - transpositions) / matches) / 3)
    jaro += min(0.1, 1 / max_len) * common_chars * (1 - jaro)
    return jaro

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/spell', methods=['POST'])
def spell():
    text = request.form['text']
    corrected_text = spell_check(text, dictionary)
    return render_template('index.html', original_text=text, corrected_text=corrected_text)

def capitalize_word(word):
    return word[0].upper() + word[1:].lower() if word else ''

def correct_case(text):
    # Fungsi ini akan mengapitalisasi huruf pertama dari setiap kalimat dan setelah tanda petik
    sentences = re.split(r'(?<=[.!?])\s+', text)
    corrected_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            # Mengapitalisasi huruf pertama dalam kalimat
            sentence = sentence[0].upper() + sentence[1:]
            # Mengapitalisasi huruf pertama dalam tanda petik
            sentence = re.sub(r'([\'"])(\s*)(\w)', lambda match: match.group(1) + match.group(2) + match.group(3).upper(), sentence)
            corrected_sentences.append(sentence)
    return ' '.join(corrected_sentences)


def assemble_text(words):
    """Assembles words into a sentence, handling spaces around punctuation, brackets, quotes, and backticks correctly."""
    text = ''
    quote_counts = {"'": 0, '"': 0, '‘': 0, '’': 0}  # Track occurrences of each quote type
    changes = []  # This list will store the indices where changes occur
    
    for i, word in enumerate(words):
        original_length = len(text)
        next_word = words[i + 1] if i + 1 < len(words) else ''
        
        if word in {'.', ',', ':', ';', '!', '?'}:
            # Ensure no space before these punctuations
            if text.endswith(' '):
                changes.append(len(text) - 1)  # Mark space before punctuation as changed
                text = text[:-1]
            text += word
        elif word in {'-', '/', '≠', '⇒', '→', '≥', '≤', '≈', '~', '÷'}:
            # No spaces around hyphens and slashes
            if text.endswith(' '):
                changes.append(len(text) - 1)  # Mark space before punctuation as changed
                text = text[:-1]
            text += word
        elif word in {'(', '{', '['}:
            # Space before if not start of text and previous character is not a space
            if text and not text.endswith(' '):
                text += ' '
            text += word
        elif word in {')', '}', ']'}:
            # No space before
            if text.endswith(' '):
                text = text[:-1]
            text += word
            # Conditionally add space after based on the next character
            if next_word and next_word not in {'.', ',', ':', ';', '!', '?', ')', '}', ']', '-', '/'}:
                text += ' '
        elif word == '`':
            # Handle backticks according to your specific rules
            if text and not text.endswith(' '):
                text += ' '  # Add space before if there is preceding text
            text += word
            if next_word and not next_word.startswith((' ', '.', ',', ':', ';', '!', '?', '-', '/', ']', ')', '}', '"', "'", '‘', '’')):
                text += ' '  # Add space after if followed by a regular character
        elif word in {'"', "'", '‘', '’'}:
            # Count occurrences of quotes
            quote_counts[word] += 1
            # Handle odd and even occurrences differently
            if quote_counts[word] % 2 == 1:  # Opening quote
                if text and not text.endswith(' '):
                    text += ' '
                text += word
            else:  # Closing quote
                if text.endswith(' '):
                    text = text[:-1]
                text += word
                if next_word and next_word not in {'.', ',', ':', ';', '!', '?', '-', '/', ']', ')', '}', '"', "'", '‘', '’'}:
                    text += ' '
        else:
            # Normal words or numbers
            if text and not text.endswith((' ', '-', '/', '(', '{', '[', "'", '"', '‘', '’', '`')):
                text += ' '
            text += word

        # Ensure space after end punctuation marks
        if word in {'.', '!', '?'} and next_word:
            text += ' '
            
        # Add to changes list if the text length has changed after adding
        if len(text) != original_length:
            changes.append(len(text) - 1)

    return text


def spell_check(text, dictionary):
    words = re.findall(r'\b\w+\b|[\d/]+|[.,!?;:(){}\[\]\'"-]|[@#$%^&*_+=|\\<>]|‘|’|`|~|≠|⇒|→|≥|≤|≈|÷', text, re.UNICODE)
    corrected_text = []
    is_new_sentence = True  # Flag to indicate the start of a new sentence

    for i, word in enumerate(words):
        original_word = word  # Store the original word for comparison
        lower_word = word.lower()

        if word in {'.', ',', ':', ';', '!', '?'}:
            corrected_text.append(word)
            if word in {'.', '!', '?'}:
                is_new_sentence = True
            continue

        if word in {'-', '/', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '=', '+', '[', ']', '{', '}', '|', '\\', ';', ':', '"', '\'', '<', '>', ',', '.', '?'}:
            corrected_text.append(word)
            continue

        suggestions = []
        max_score = 0
        for dictionary_word in dictionary:
            score = jarowinkler(lower_word, dictionary_word.lower())
            if score > max_score:
                max_score = score
                suggestions = [dictionary_word]
            elif score == max_score:
                suggestions.append(dictionary_word)

        if max_score >= 0.8:
            if len(suggestions) > 1:
                # If multiple suggestions with the same high score, handle differently
                highlight_text = ', '.join(s.capitalize() if is_new_sentence else s.lower() for s in suggestions)
                word_to_display = f"<span class='highlight'>{lower_word} (suggestions: {highlight_text})</span>"
                corrected_text.append(word_to_display)
            else:
                best_match = suggestions[0]
                best_match_cased = best_match.capitalize() if is_new_sentence else best_match.lower()
                if original_word != best_match_cased:
                    corrected_text.append(f"<span class='highlight'>{best_match_cased}</span>")
                else:
                    corrected_text.append(best_match_cased)
        else:
            # Append the word as is if no close matches are found
            corrected_text.append(original_word)

        is_new_sentence = False  # Reset the flag unless set by punctuation

    result_text = assemble_text(corrected_text)
    return result_text

if __name__ == "__main__":
    app.run(debug=True)