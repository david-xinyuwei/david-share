import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.corpus import stopwords


# Download the stopwords if not already downloaded
nltk.download("stopwords")
nltk.download("punkt")
stop_words = set(stopwords.words("english"))


def preprocess_text(text):
    # Tokenize the text
    tokens = nltk.word_tokenize(text)
    # Convert to lower case
    tokens = [word.lower() for word in tokens]
    # Remove punctuation
    tokens = [word for word in tokens if word.isalnum()]
    # Remove stopwords
    tokens = [word for word in tokens if word not in stop_words]
    return " ".join(tokens)


def extract_keywords(text, n=5):
    # Preprocess the text
    preprocessed_text = preprocess_text(text)
    # Use TfidfVectorizer to extract keywords
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([preprocessed_text])
    # Get feature names (keywords)
    feature_names = vectorizer.get_feature_names_out()
    # Get tf-idf scores
    tfidf_scores = tfidf_matrix.toarray()[0]
    # Create a dictionary of keywords and their scores
    keywords_scores = {
        feature_names[i]: tfidf_scores[i] for i in range(len(feature_names))
    }
    # Sort keywords by score
    sorted_keywords = sorted(keywords_scores.items(), key=lambda x: x[1], reverse=True)
    # Return the top n keywords
    return [keyword for keyword, score in sorted_keywords[:n]]
