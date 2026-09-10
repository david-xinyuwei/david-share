import collections


def leading_correct_count(matches):
    length = 0
    for correct in matches:
        if not correct:
            break
        length += 1
    return length


def repetition_statistics(units, ngram_size=4):
    if ngram_size < 1:
        raise ValueError("ngram_size must be positive")
    grams = [tuple(units[index:index + ngram_size])
             for index in range(max(0, len(units) - ngram_size + 1))]
    counts = collections.Counter(grams)
    return {
        "ngram_count": len(grams),
        "repeat_fraction": 1.0 - len(counts) / len(grams) if grams else 0.0,
        "max_count": max(counts.values(), default=0),
    }