import pandas as pd
import os


related_word_path = os.path.join(os.path.dirname(__file__), "related_word.csv")


def get_related_words(path: str, seperator: str="|"):
    """
    :param path:
    :param seperator:
    :return: {word: related word list}
    """
    result = {}
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        name = row['keyword'].strip().lower()
        words = list(set(row['related'].split(seperator)))
        result[name] = words

    return result


related_words = get_related_words(related_word_path)


def get_neighbours(word):
    word = word.strip().lower()
    return related_words.get(word, [])
