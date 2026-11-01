"""Ten preprocessing, evaluation, and model-diagnosis repairs."""
from functools import partial

from ..common import make

p = partial(make, "data_science")

PROBLEMS = [
    p("scaler-fit-before-split", "The scaler learns from the test set",
      "A preprocessing step standardizes the test features with statistics that also include the test rows, so the evaluation sees information it should not have.",
      "Input.train and input.test are lists of numbers. Fit the scaler on the training rows only: compute their mean and population standard deviation, then transform each test value as (value - mean) / spread. Round each transformed value to four decimal places. When the training spread is zero, return 0.0 for every test value.",
      '''
      def solve(data):
          train = data["train"]
          mean = sum(train) / len(train)
          variance = sum((value - mean) ** 2 for value in train) / len(train)
          spread = variance ** 0.5
          if spread == 0:
              return [0.0 for _ in data["test"]]
          return [round((value - mean) / spread, 4) for value in data["test"]]
      ''', ('train = data["train"]', 'train = data["train"] + data["test"]'),
      [({"train": [0, 10], "test": [0, 10]}, [-1.0, 1.0]), ({"train": [1, 5], "test": [9]}, [3.0]), ({"train": [2, 2], "test": [2, 8]}, [0.0, 0.0]), ({"train": [4, 8], "test": [0, 4, 8, 12]}, [-3.0, -1.0, 1.0, 3.0]), ({"train": [5], "test": [5, 7]}, [0.0, 0.0])],
      ["Which rows may the scaler look at before the model is evaluated?", "Fitting on training and test rows together leaks test information into the evaluation.", "Compute the mean and spread from data[\"train\"] alone, then apply those values to data[\"test\"]."], ["preprocessing", "leakage", "standardization"], "medium"),
    p("recall-denominator", "Recall blames the predictions",
      "A classifier report computes recall with the predicted-positive count, so it reports precision a second time and hides every missed positive.",
      "Input.actual and input.predicted are equally long lists of 0/1 labels. Compute true positives, false positives, and false negatives. Return {precision, recall, f1} with each value rounded to four decimal places; use 0.0 when its denominator or the F1 sum is zero.",
      '''
      def solve(data):
          actual, predicted = data["actual"], data["predicted"]
          tp = sum(a == 1 and p == 1 for a, p in zip(actual, predicted))
          fp = sum(a == 0 and p == 1 for a, p in zip(actual, predicted))
          fn = sum(a == 1 and p == 0 for a, p in zip(actual, predicted))
          precision = tp / (tp + fp) if tp + fp else 0.0
          recall = tp / (tp + fn) if tp + fn else 0.0
          f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
          return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
      ''', ('tp / (tp + fn)', 'tp / (tp + fp)'),
      [({"actual": [1, 1, 1, 1, 0, 0, 0, 0], "predicted": [1, 1, 0, 0, 1, 0, 0, 0]}, {"precision": 0.6667, "recall": 0.5, "f1": 0.5714}), ({"actual": [1, 0, 1, 0], "predicted": [1, 0, 0, 0]}, {"precision": 1.0, "recall": 0.5, "f1": 0.6667}), ({"actual": [1, 1], "predicted": [0, 0]}, {"precision": 0.0, "recall": 0.0, "f1": 0.0}), ({"actual": [0, 0, 0, 1], "predicted": [1, 1, 0, 1]}, {"precision": 0.3333, "recall": 1.0, "f1": 0.5}), ({"actual": [1, 1, 1, 0, 0], "predicted": [1, 0, 1, 0, 0]}, {"precision": 1.0, "recall": 0.6667, "f1": 0.8}), ({"actual": [], "predicted": []}, {"precision": 0.0, "recall": 0.0, "f1": 0.0})],
      ["Which positives should recall count in its denominator?", "Recall asks what fraction of the actual positives were found, so its denominator is true positives plus false negatives.", "Divide true positives by the number of actual positives, not by the number of predicted positives."], ["metrics", "classification", "evaluation"], "medium"),
    p("auc-tie-handling", "AUC treats a tie as a win",
      "A ranking evaluation counts every equal score as a correct ordering, inflating AUC whenever the model cannot separate two examples.",
      "Input.scores and input.labels are equally long lists, with labels 0/1. AUC is the fraction of positive-negative pairs ordered correctly, counting a tied pair as one half. Return the AUC rounded to four decimal places, or 0.5 when either class is absent.",
      '''
      def solve(data):
          positives = [s for s, y in zip(data["scores"], data["labels"]) if y == 1]
          negatives = [s for s, y in zip(data["scores"], data["labels"]) if y == 0]
          if not positives or not negatives:
              return 0.5
          wins = ties = 0
          for p in positives:
              for n in negatives:
                  if p > n:
                      wins += 1
                  elif p == n:
                      ties += 1
          return round((wins + 0.5 * ties) / (len(positives) * len(negatives)), 4)
      ''', ('wins + 0.5 * ties', 'wins + ties'),
      [({"scores": [1, 2, 2, 0], "labels": [1, 0, 1, 0]}, 0.625), ({"scores": [3, 3, 1], "labels": [1, 0, 1]}, 0.25), ({"scores": [5], "labels": [1]}, 0.5), ({"scores": [1, 2, 3, 4], "labels": [0, 0, 1, 1]}, 1.0), ({"scores": [2, 2, 2, 1], "labels": [0, 1, 0, 1]}, 0.25)],
      ["How much credit does a pair with equal scores deserve?", "A tie gives no evidence that the positive outranks the negative, so it contributes one half rather than a full win.", "Add 0.5 per tied pair before dividing by the number of positive-negative pairs."], ["metrics", "ranking", "roc-auc"], "medium"),
    p("balanced-class-weights", "Balanced weights favor the majority class",
      "A class-weight helper returns each class's prevalence, so the majority class receives the largest weight instead of the smallest.",
      "Input.labels is a list of integer class labels. Balanced class weight is the number of samples divided by the number of classes times that class's count. Return {\"weights\": [[label, weight], ...]} sorted by label, with each weight rounded to four decimal places.",
      '''
      def solve(data):
          labels = data["labels"]
          counts = {}
          for label in labels:
              counts[label] = counts.get(label, 0) + 1
          total = len(labels)
          return {"weights": [[label, round(total / (len(counts) * counts[label]), 4)]
                              for label in sorted(counts)]}
      ''', ('total / (len(counts) * counts[label])', 'counts[label] / total'),
      [({"labels": [0, 0, 0, 1]}, {"weights": [[0, 0.6667], [1, 2.0]]}), ({"labels": [1, 1, 2, 3]}, {"weights": [[1, 0.6667], [2, 1.3333], [3, 1.3333]]}), ({"labels": [5]}, {"weights": [[5, 1.0]]}), ({"labels": [0, 1]}, {"weights": [[0, 1.0], [1, 1.0]]}), ({"labels": [2, 2, 2, 2, 0, 0, 0, 1, 1]}, {"weights": [[0, 1.0], [1, 1.5], [2, 0.75]]}), ({"labels": []}, {"weights": []})],
      ["Should a rare class weigh more or less than a common class?", "Balanced weighting gives each class an equal total contribution, so rarer classes receive larger per-sample weights.", "Divide the sample count by the class count times each class's own count."], ["imbalanced-data", "class-weights", "training"], "easy"),
    p("kmeans-farthest-centroid", "Clustering picks the farthest centroid",
      "A k-means assignment step sends every point to its least similar centroid, so clusters drift apart instead of tightening.",
      "Input.points and input.centroids are lists of equally sized coordinate lists. Assign each point to the centroid with the smallest squared Euclidean distance; break ties with the lowest centroid index. Return the assignment indices in point order.",
      '''
      def solve(data):
          assignments = []
          for point in data["points"]:
              distances = [sum((a - b) ** 2 for a, b in zip(point, centroid)) for centroid in data["centroids"]]
              assignments.append(min(range(len(distances)), key=lambda i: distances[i]))
          return assignments
      ''', ('min(range(len(distances))', 'max(range(len(distances))'),
      [({"points": [[0, 0], [10, 0], [5, 5]], "centroids": [[0, 0], [10, 0]]}, [0, 1, 0]), ({"points": [[1, 1]], "centroids": [[0, 0], [2, 2], [1, 0]]}, [2]), ({"points": [], "centroids": [[0, 0]]}, []), ({"points": [[3, 4], [6, 8]], "centroids": [[0, 0], [3, 4]]}, [1, 1]), ({"points": [[0, 5]], "centroids": [[0, 0], [0, 10], [0, 5]]}, [2]), ({"points": [[2, 2]], "centroids": [[0, 0], [4, 4]]}, [0])],
      ["Does a point belong to the centroid it is nearest or farthest from?", "Assignment minimizes distance; maximizing it separates points from their natural cluster.", "Pick the centroid index with the minimum squared distance, and keep the first index on a tie."], ["clustering", "k-means", "distance"], "easy"),
    p("cross-validation-fold-sizes", "Cross-validation drops the remainder",
      "A fold builder divides the row index by a rounded fold size, so leftover rows pile into the final fold and the folds are no longer balanced.",
      "Input.n is a nonnegative row count and input.k is a positive fold count. Assign row indices 0 through n-1 round-robin to folds by index modulo k. Return the list of fold sizes.",
      '''
      def solve(data):
          counts = [0] * data["k"]
          for index in range(data["n"]):
              counts[index % data["k"]] += 1
          return counts
      ''', ('counts[index % data["k"]] += 1', 'counts[index // ((data["n"] + data["k"] - 1) // data["k"])] += 1'),
      [({"n": 10, "k": 3}, [4, 3, 3]), ({"n": 10, "k": 4}, [3, 3, 2, 2]), ({"n": 0, "k": 3}, [0, 0, 0]), ({"n": 7, "k": 3}, [3, 2, 2]), ({"n": 13, "k": 4}, [4, 3, 3, 3]), ({"n": 5, "k": 2}, [3, 2])],
      ["How should rows be distributed when n is not divisible by k?", "Round-robin assignment gives the first n mod k folds one extra row each, keeping every pair of fold sizes within one.", "Assign each index to the fold index modulo k instead of dividing by a fixed fold size."], ["validation", "cross-validation", "folds"], "medium"),
    p("precision-at-k-denominator", "Precision@k measures recall instead",
      "A search report divides the relevant results in the top k by all relevant results, so it reports recall while claiming to measure precision.",
      "Input.ranked is a list of 0/1 relevance flags in rank order and input.k is a positive integer no greater than the list length. Precision@k is the number of relevant flags among the first k results divided by k. Return the value rounded to four decimal places.",
      '''
      def solve(data):
          top = data["ranked"][:data["k"]]
          return round(sum(top) / data["k"], 4)
      ''', ('/ data["k"]', '/ sum(data["ranked"])'),
      [({"ranked": [1, 0, 0, 0, 1, 1], "k": 2}, 0.5), ({"ranked": [1, 1, 0, 0], "k": 3}, 0.6667), ({"ranked": [0, 0, 1, 1, 0], "k": 4}, 0.5), ({"ranked": [1], "k": 1}, 1.0), ({"ranked": [1, 0, 1, 0, 1, 0, 1], "k": 5}, 0.6), ({"ranked": [0, 1, 0, 0, 0], "k": 3}, 0.3333)],
      ["What is the denominator when precision is measured at rank k?", "Precision@k asks how many of the k returned results are relevant, regardless of how many relevant results exist overall.", "Divide the relevant count in the first k results by k itself."], ["ranking", "metrics", "precision"], "easy"),
    p("sample-variance-denominator", "Sample variance divides by the sample size",
      "A statistics helper divides the squared deviations by n, so it reports the population variance even when the values are a sample used to estimate a larger population.",
      "Input.values is a list of numbers. Return the sample variance, dividing the squared deviations from the mean by n - 1, rounded to four decimal places. Return 0.0 when there are fewer than two values.",
      '''
      def solve(data):
          values = data["values"]
          if len(values) < 2:
              return 0.0
          mean = sum(values) / len(values)
          return round(sum((x - mean) ** 2 for x in values) / (len(values) - 1), 4)
      ''', ('/ (len(values) - 1)', '/ len(values)'),
      [({"values": [0, 10]}, 50.0), ({"values": [1, 2, 3, 4]}, 1.6667), ({"values": [5]}, 0.0), ({"values": []}, 0.0), ({"values": [2, 4, 4, 4, 5, 5, 7, 9]}, 4.5714), ({"values": [-2, 0, 2]}, 4.0)],
      ["Is the data the whole population or a sample from it?", "A sample variance estimates the population spread, so dividing by n - 1 corrects the downward bias of dividing by n.", "Divide the squared deviations by one less than the number of values."], ["statistics", "variance", "descriptive-stats"], "easy"),
    p("majority-baseline-test-accuracy", "The baseline grades itself on training data",
      "A baseline report predicts the most common training label but scores accuracy against the training rows, so its reported score says nothing about generalization.",
      "Input.train and input.test are nonempty lists of integer labels. Predict the most frequent training label, breaking ties toward the smallest label. Return {\"label\": predicted, \"accuracy\": the fraction of test rows equal to it rounded to four decimal places}.",
      '''
      def solve(data):
          labels = data["test"]
          counts = {}
          for label in data["train"]:
              counts[label] = counts.get(label, 0) + 1
          label = min(counts, key=lambda value: (-counts[value], value))
          correct = sum(value == label for value in labels)
          return {"label": label, "accuracy": round(correct / len(labels), 4)}
      ''', ('labels = data["test"]', 'labels = data["train"]'),
      [({"train": [0, 0, 1], "test": [0, 1, 0, 0]}, {"label": 0, "accuracy": 0.75}), ({"train": [1, 1, 0], "test": [1, 0]}, {"label": 1, "accuracy": 0.5}), ({"train": [2, 1, 1, 2], "test": [2, 2]}, {"label": 1, "accuracy": 0.0}), ({"train": [3], "test": [3, 3, 3]}, {"label": 3, "accuracy": 1.0}), ({"train": [0, 0, 0, 1, 1], "test": [1, 1, 1, 0]}, {"label": 0, "accuracy": 0.25})],
      ["Which rows should a baseline be scored on?", "A baseline estimates how a model will behave on unseen data, so it must be scored on the test rows, not the rows that chose its prediction.", "Choose the label from data[\"train\"] but count correct predictions in data[\"test\"]."], ["evaluation", "baseline", "class-imbalance"], "medium"),
    p("linear-regression-intercept", "The regression line misses its intercept",
      "A least-squares helper adds the slope-mean term while computing the intercept, so the fitted line no longer passes through the data's center.",
      "Input.points contains [x, y] pairs with at least two distinct x values. Fit an ordinary least-squares line through the points. Return {\"slope\": slope, \"intercept\": intercept} with both values rounded to four decimal places.",
      '''
      def solve(data):
          points = data["points"]
          mean_x = sum(x for x, _ in points) / len(points)
          mean_y = sum(y for _, y in points) / len(points)
          denominator = sum((x - mean_x) ** 2 for x, _ in points)
          slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
          return {"slope": round(slope, 4), "intercept": round(mean_y - slope * mean_x, 4)}
      ''', ('mean_y - slope * mean_x', 'mean_y + slope * mean_x'),
      [({"points": [[1, 2], [2, 4], [3, 6]]}, {"slope": 2.0, "intercept": 0.0}), ({"points": [[0, 1], [2, 5]]}, {"slope": 2.0, "intercept": 1.0}), ({"points": [[1, 3], [2, 3], [3, 3]]}, {"slope": 0.0, "intercept": 3.0}), ({"points": [[1, 1], [2, 2], [4, 4]]}, {"slope": 1.0, "intercept": 0.0}), ({"points": [[0, 5], [10, 15]]}, {"slope": 1.0, "intercept": 5.0}), ({"points": [[2, 1], [4, 5], [6, 9]]}, {"slope": 2.0, "intercept": -3.0})],
      ["Which point must an ordinary least-squares line always pass through?", "The fitted line passes through the means of x and y, so intercept = mean(y) - slope * mean(x).", "Subtract the slope-mean product from the mean of y."], ["regression", "least-squares", "modeling"], "easy"),
]
