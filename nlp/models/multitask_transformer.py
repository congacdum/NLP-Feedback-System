from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
from torch import nn
import torch.nn.functional as F

from nlp.schema import ASPECTS, SENTIMENTS


@dataclass
class ABSAOutput:
    loss: Optional[torch.Tensor]
    aspect_logits: torch.Tensor
    sentiment_logits: torch.Tensor
    aspect_loss: Optional[torch.Tensor] = None
    sentiment_loss: Optional[torch.Tensor] = None


class MultiTaskABSA(nn.Module):
    """Shared Transformer encoder with aspect and per-aspect sentiment heads."""

    def __init__(
        self,
        backbone_name: str,
        *,
        dropout: float = 0.1,
        lambda_aspect: float = 1.0,
        lambda_sentiment: float = 1.0,
        encoder_config_dir: str | None = None,
    ):
        super().__init__()
        try:
            from transformers import AutoConfig, AutoModel  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional train dependency
            raise RuntimeError("Install requirements-train.txt to use Transformer training.") from exc
        self.backbone_name = backbone_name
        if encoder_config_dir is None:
            # Training path: initialize from the public pretrained backbone.
            self.encoder = AutoModel.from_pretrained(backbone_name)
        else:
            # Runtime path: instantiate the architecture from the config bundled
            # inside the frozen artifact, then load the fine-tuned state_dict.
            # This avoids a hidden network download during Docker/app startup.
            config = AutoConfig.from_pretrained(encoder_config_dir, local_files_only=True)
            self.encoder = AutoModel.from_config(config)
        hidden = int(self.encoder.config.hidden_size)
        self.dropout = nn.Dropout(dropout)
        self.aspect_head = nn.Linear(hidden, len(ASPECTS))
        self.sentiment_head = nn.Linear(hidden, len(ASPECTS) * len(SENTIMENTS))
        self.lambda_aspect = lambda_aspect
        self.lambda_sentiment = lambda_sentiment

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        *,
        aspect_targets: Optional[torch.Tensor] = None,
        sentiment_targets: Optional[torch.Tensor] = None,
        aspect_pos_weight: Optional[torch.Tensor] = None,
        sentiment_class_weight: Optional[torch.Tensor] = None,
    ) -> ABSAOutput:
        enc = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = enc.last_hidden_state[:, 0, :]
        pooled = self.dropout(pooled)
        aspect_logits = self.aspect_head(pooled)
        sentiment_logits = self.sentiment_head(pooled).view(-1, len(ASPECTS), len(SENTIMENTS))

        aspect_loss = None
        sentiment_loss = None
        total_loss = None
        if aspect_targets is not None:
            aspect_loss = F.binary_cross_entropy_with_logits(
                aspect_logits,
                aspect_targets.float(),
                pos_weight=aspect_pos_weight,
            )
        if sentiment_targets is not None:
            flat_logits = sentiment_logits.reshape(-1, len(SENTIMENTS))
            flat_targets = sentiment_targets.reshape(-1).long()
            valid_sentiment_mask = flat_targets != -100
            # CrossEntropy's mean reduction is NaN when every target is the
            # ignore index (a legitimate all-no_aspect batch).  Do not invent
            # sentiment labels: retain a device/dtype-correct zero loss.
            if valid_sentiment_mask.any():
                sentiment_loss = F.cross_entropy(
                    flat_logits[valid_sentiment_mask],
                    flat_targets[valid_sentiment_mask],
                    weight=sentiment_class_weight,
                )
            else:
                sentiment_loss = aspect_logits.new_zeros(())
        if aspect_loss is not None and sentiment_loss is not None:
            total_loss = self.lambda_aspect * aspect_loss + self.lambda_sentiment * sentiment_loss
        elif aspect_loss is not None:
            total_loss = aspect_loss
        elif sentiment_loss is not None:
            total_loss = sentiment_loss
        return ABSAOutput(
            loss=total_loss,
            aspect_logits=aspect_logits,
            sentiment_logits=sentiment_logits,
            aspect_loss=aspect_loss,
            sentiment_loss=sentiment_loss,
        )
