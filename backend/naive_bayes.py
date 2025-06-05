import numpy as np
from collections import defaultdict, Counter
import re

class NaiveBayesMoodClassifier:
    def __init__(self):
        self.mood_word_counts = defaultdict(Counter)
        self.mood_counts = Counter()
        self.vocab = set()
        self.mood_priors = {}
        self.word_probs = defaultdict(dict)

    def tokenize(self, text):
        # Simple whitespace and punctuation tokenizer
        return re.findall(r'\b\w+\b', text.lower())

    def fit(self, training_data):
        """
        training_data: list of tuples (lyrics, moods)
        moods can be a string (single mood) or a list of strings (multi-mood)
        """
        for lyrics, moods in training_data:
            if isinstance(moods, str):
                moods = [moods]
            tokens = self.tokenize(lyrics)
            for mood in moods:
                self.mood_word_counts[mood].update(tokens)
                self.mood_counts[mood] += 1
            self.vocab.update(tokens)
        total = sum(self.mood_counts.values())
        self.mood_priors = {mood: count / total for mood, count in self.mood_counts.items()}
        # Calculate word probabilities with Laplace smoothing
        for mood in self.mood_word_counts:
            total_words = sum(self.mood_word_counts[mood].values())
            for word in self.vocab:
                self.word_probs[mood][word] = (
                    self.mood_word_counts[mood][word] + 1
                ) / (total_words + len(self.vocab))

    def predict(self, lyrics, threshold=0.1):
        tokens = self.tokenize(lyrics)
        mood_scores = {}
        for mood in self.mood_priors:
            # Start with log prior
            log_prob = np.log(self.mood_priors[mood])
            for word in tokens:
                if word in self.vocab:
                    log_prob += np.log(self.word_probs[mood].get(word, 1 / (sum(self.mood_word_counts[mood].values()) + len(self.vocab))))
            mood_scores[mood] = log_prob
        # Convert log-probs to probabilities
        max_log = max(mood_scores.values())
        exp_scores = {mood: np.exp(score - max_log) for mood, score in mood_scores.items()}
        total = sum(exp_scores.values())
        probs = {mood: exp_scores[mood] / total for mood in exp_scores}
        # Return all moods above threshold (default 0.1)
        return [mood for mood, prob in probs.items() if prob >= threshold]