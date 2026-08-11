from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from nlp.preprocessing.text import normalize_text
from nlp.schema import ASPECTS, SENTIMENTS


def _feature_union() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            max_features=7000,
        )),
        ("char", TfidfVectorizer(
            lowercase=True,
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            sublinear_tf=True,
            max_features=9000,
        )),
    ])


@dataclass
class TfidfABSA:
    """Runnable classical ABSA baseline with a shared TF-IDF representation.

    This model is intentionally lightweight and deterministic enough for the demo
    application. It is a baseline, not the planned final Transformer model.
    """

    feature_extractor: FeatureUnion = field(default_factory=_feature_union)
    aspect_models: Dict[str, LogisticRegression] = field(default_factory=dict)
    sentiment_models: Dict[str, LogisticRegression] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=lambda: {a: 0.5 for a in ASPECTS})
    model_version: str = "baseline-absa-v0"

    def fit(self, records: Sequence[Mapping]) -> "TfidfABSA":
        texts = [normalize_text(str(r["text"])) for r in records]
        X = self.feature_extractor.fit_transform(texts)

        for aspect in ASPECTS:
            y = np.array([
                int(any(a["aspect"] == aspect for a in r.get("annotations", [])))
                for r in records
            ])
            model = LogisticRegression(
                max_iter=1500,
                class_weight="balanced",
                solver="liblinear",
                random_state=42,
            )
            model.fit(X, y)
            self.aspect_models[aspect] = model

            indices, labels = [], []
            for i, r in enumerate(records):
                for ann in r.get("annotations", []):
                    if ann["aspect"] == aspect:
                        indices.append(i)
                        labels.append(ann["sentiment"])
                        break
            if len(set(labels)) >= 2:
                sm = LogisticRegression(
                    max_iter=1500,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=42,
                )
                sm.fit(X[indices], labels)
                self.sentiment_models[aspect] = sm
        return self

    def set_thresholds(self, thresholds: Mapping[str, float]) -> None:
        for aspect in ASPECTS:
            if aspect in thresholds:
                self.thresholds[aspect] = float(thresholds[aspect])

    def _full_prediction(self, texts: Sequence[str]) -> List[dict]:
        cleaned = [normalize_text(t) for t in texts]
        X = self.feature_extractor.transform(cleaned)
        out = [
            {
                "text": text,
                "aspect_scores": {},
                "sentiment_scores": {},
                "sentiment_by_aspect": {},
                "aspects": [],
                "model_version": self.model_version,
                "backend": "tfidf_logistic_baseline",
            }
            for text in cleaned
        ]

        for aspect in ASPECTS:
            am = self.aspect_models[aspect]
            probs = am.predict_proba(X)
            pos_idx = list(am.classes_).index(1)
            aspect_probs = probs[:, pos_idx]

            sentiment_payloads: List[dict] = [{} for _ in cleaned]
            sentiment_labels: List[str] = ["neutral" for _ in cleaned]
            if aspect in self.sentiment_models:
                sm = self.sentiment_models[aspect]
                s_probs = sm.predict_proba(X)
                for i, row in enumerate(s_probs):
                    payload = {str(cls): float(p) for cls, p in zip(sm.classes_, row)}
                    # Ensure schema is stable even when fixture lacks a class.
                    for s in SENTIMENTS:
                        payload.setdefault(s, 0.0)
                    sentiment_payloads[i] = payload
                    sentiment_labels[i] = str(sm.classes_[int(np.argmax(row))])

            for i in range(len(cleaned)):
                a_score = float(aspect_probs[i])
                out[i]["aspect_scores"][aspect] = a_score
                out[i]["sentiment_scores"][aspect] = sentiment_payloads[i]
                out[i]["sentiment_by_aspect"][aspect] = sentiment_labels[i]
                if a_score >= self.thresholds.get(aspect, 0.5):
                    s_label = sentiment_labels[i]
                    s_score = float(sentiment_payloads[i].get(s_label, 0.0)) if sentiment_payloads[i] else 0.0
                    out[i]["aspects"].append({
                        "aspect": aspect,
                        "sentiment": s_label,
                        "aspect_score": a_score,
                        "sentiment_score": s_score,
                    })
        for item in out:
            item["status"] = "ok" if item["aspects"] else "no_aspect"
        return out

    def predict_full(self, texts: Sequence[str]) -> List[dict]:
        return self._full_prediction(texts)

    def analyze(self, text: str) -> dict:
        return self._full_prediction([text])[0]


@dataclass
class LinearSVMABSA:
    """Traditional TF-IDF + LinearSVC ABSA benchmark.

    `decision_function` values are transformed monotonically for Dev threshold
    tuning and visualization; they are scores, not calibrated probabilities.
    This benchmark exists for the academic comparison requested by the project.
    The runtime demo uses `TfidfABSA` because its LogisticRegression heads expose
    stable probabilities directly.
    """

    feature_extractor: FeatureUnion = field(default_factory=_feature_union)
    aspect_models: Dict[str, object] = field(default_factory=dict)
    sentiment_models: Dict[str, object] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=lambda: {a: 0.5 for a in ASPECTS})
    model_version: str = "linear-svm-absa-v0"

    def fit(self, records: Sequence[Mapping]) -> "LinearSVMABSA":
        from sklearn.svm import LinearSVC
        texts = [normalize_text(str(r["text"])) for r in records]
        X = self.feature_extractor.fit_transform(texts)
        for aspect in ASPECTS:
            y = np.array([int(any(a["aspect"] == aspect for a in r.get("annotations", []))) for r in records])
            am = LinearSVC(class_weight="balanced", random_state=42)
            am.fit(X, y)
            self.aspect_models[aspect] = am
            indices, labels = [], []
            for i, r in enumerate(records):
                for ann in r.get("annotations", []):
                    if ann["aspect"] == aspect:
                        indices.append(i); labels.append(ann["sentiment"]); break
            if len(set(labels)) >= 2:
                sm = LinearSVC(class_weight="balanced", random_state=42)
                sm.fit(X[indices], labels)
                self.sentiment_models[aspect] = sm
        return self

    def set_thresholds(self, thresholds: Mapping[str, float]) -> None:
        for aspect in ASPECTS:
            if aspect in thresholds:
                self.thresholds[aspect] = float(thresholds[aspect])

    @staticmethod
    def _sigmoid(x):
        x = np.asarray(x, dtype=float)
        return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))

    @staticmethod
    def _softmax(x):
        x = np.asarray(x, dtype=float)
        x = x - np.max(x, axis=-1, keepdims=True)
        e = np.exp(x)
        return e / np.maximum(e.sum(axis=-1, keepdims=True), 1e-12)

    def predict_full(self, texts: Sequence[str]) -> List[dict]:
        cleaned = [normalize_text(t) for t in texts]
        X = self.feature_extractor.transform(cleaned)
        out = [{
            "text": text, "aspect_scores": {}, "sentiment_scores": {},
            "sentiment_by_aspect": {}, "aspects": [], "model_version": self.model_version,
            "backend": "tfidf_linear_svm_baseline",
        } for text in cleaned]
        for aspect in ASPECTS:
            am = self.aspect_models[aspect]
            a_scores = self._sigmoid(am.decision_function(X))
            sentiment_payloads = [{} for _ in cleaned]
            sentiment_labels = ["neutral" for _ in cleaned]
            if aspect in self.sentiment_models:
                sm = self.sentiment_models[aspect]
                raw = np.asarray(sm.decision_function(X))
                if raw.ndim == 1:
                    raw = np.column_stack([-raw, raw])
                probs = self._softmax(raw)
                for i, row in enumerate(probs):
                    payload = {str(cls): float(p) for cls, p in zip(sm.classes_, row)}
                    for sent in SENTIMENTS:
                        payload.setdefault(sent, 0.0)
                    sentiment_payloads[i] = payload
                    sentiment_labels[i] = str(sm.classes_[int(np.argmax(row))])
            for i in range(len(cleaned)):
                a_score = float(a_scores[i])
                out[i]["aspect_scores"][aspect] = a_score
                out[i]["sentiment_scores"][aspect] = sentiment_payloads[i]
                out[i]["sentiment_by_aspect"][aspect] = sentiment_labels[i]
                if a_score >= self.thresholds.get(aspect, 0.5):
                    sent = sentiment_labels[i]
                    out[i]["aspects"].append({
                        "aspect": aspect, "sentiment": sent, "aspect_score": a_score,
                        "sentiment_score": float(sentiment_payloads[i].get(sent, 0.0)) if sentiment_payloads[i] else 0.0,
                    })
        for item in out:
            item["status"] = "ok" if item["aspects"] else "no_aspect"
        return out

    def analyze(self, text: str) -> dict:
        return self.predict_full([text])[0]
