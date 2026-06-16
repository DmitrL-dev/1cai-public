"""MicroModel — domain-specialized micro-transformer.

Ported from SENTINEL virtualconv-engine.
Pure Python autograd, no external ML dependencies at inference.

Architecture: Input → Linear projection → Transformer block(s) → Score head → sigmoid
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any

from src.micro_swarm.engine import Value


# ──────────────────────────────────────────
# Neural network primitives
# ──────────────────────────────────────────


def _init_matrix(
    nout: int, nin: int, std: float = 0.08
) -> list[list[Value]]:
    """Initialize weight matrix with small random values."""
    return [
        [Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)
    ]


def _linear(x: list[Value], w: list[list[Value]]) -> list[Value]:
    """Dense linear layer: y = W @ x."""
    return [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w]


def _rmsnorm(x: list[Value]) -> list[Value]:
    """Root Mean Square normalization."""
    ms = sum(xi * xi for xi in x) / len(x)
    scale = (ms + 1e-5) ** -0.5
    return [xi * scale for xi in x]


# ──────────────────────────────────────────
# MicroModel config and implementation
# ──────────────────────────────────────────


@dataclass
class MicroModelConfig:
    """Configuration for a MicroModel."""

    n_features: int = 8
    n_embd: int = 16
    n_head: int = 4
    n_layer: int = 1
    seed: int = 42


class MicroModel:
    """Domain-specialized micro-transformer.

    Takes numeric features, produces a score [0,1] and an embedding.
    Pure Python — no external ML dependencies at inference.
    """

    def __init__(self, config: MicroModelConfig | None = None) -> None:
        self._config = config or MicroModelConfig()
        self._rng_state = random.getstate()
        random.seed(self._config.seed)

        c = self._config
        self._w_in = _init_matrix(c.n_embd, c.n_features)

        self._layers: list[dict[str, list[list[Value]]]] = []
        for _ in range(c.n_layer):
            self._layers.append({
                "attn_wq": _init_matrix(c.n_embd, c.n_embd),
                "attn_wk": _init_matrix(c.n_embd, c.n_embd),
                "attn_wv": _init_matrix(c.n_embd, c.n_embd),
                "attn_wo": _init_matrix(c.n_embd, c.n_embd),
                "mlp_fc1": _init_matrix(4 * c.n_embd, c.n_embd),
                "mlp_fc2": _init_matrix(c.n_embd, 4 * c.n_embd),
            })

        self._w_head = _init_matrix(1, c.n_embd)
        self._params = self._collect_params()

        # Adam optimizer buffers
        self._m = [0.0] * len(self._params)
        self._v = [0.0] * len(self._params)
        self._step = 0

        random.setstate(self._rng_state)

    def _collect_params(self) -> list[Value]:
        """Flatten all parameters into a single list."""
        params: list[Value] = []
        for row in self._w_in:
            params.extend(row)
        for layer in self._layers:
            for mat in layer.values():
                for row in mat:
                    params.extend(row)
        for row in self._w_head:
            params.extend(row)
        return params

    @property
    def param_count(self) -> int:
        return len(self._params)

    @property
    def memory_bytes(self) -> int:
        """Approximate memory in bytes (fp32)."""
        return self.param_count * 4

    def forward(
        self, features: list[float]
    ) -> tuple[float, list[float]]:
        """Forward pass: features → (score, embedding).

        Args:
            features: list of floats, length = n_features

        Returns:
            (score: float in [0,1], embedding: list[float] of length n_embd)
        """
        if len(features) != self._config.n_features:
            raise ValueError(
                f"Expected {self._config.n_features} features, "
                f"got {len(features)}"
            )

        x = [Value(f) for f in features]
        x = _linear(x, self._w_in)
        x = _rmsnorm(x)

        c = self._config
        head_dim = c.n_embd // c.n_head

        for layer_weights in self._layers:
            x_res = x
            x = _rmsnorm(x)

            q = _linear(x, layer_weights["attn_wq"])
            k = _linear(x, layer_weights["attn_wk"])
            v = _linear(x, layer_weights["attn_wv"])

            x_attn: list[Value] = []
            for h in range(c.n_head):
                hs = h * head_dim
                x_attn.extend(v[hs: hs + head_dim])

            x = _linear(x_attn, layer_weights["attn_wo"])
            x = [a + b for a, b in zip(x, x_res)]

            x_res = x
            x = _rmsnorm(x)
            x = _linear(x, layer_weights["mlp_fc1"])
            x = [xi.relu() for xi in x]
            x = _linear(x, layer_weights["mlp_fc2"])
            x = [a + b for a, b in zip(x, x_res)]

        embedding = [xi.data for xi in x]
        logit = _linear(x, self._w_head)[0]
        score_value = logit.sigmoid()

        return score_value.data, embedding

    def forward_train(
        self, features: list[float], target: float,
    ) -> tuple[float, "Value"]:
        """Forward pass for training. Returns (score, loss_Value).

        Loss = binary cross-entropy: -[t*log(p) + (1-t)*log(1-p)]
        """
        if len(features) != self._config.n_features:
            raise ValueError(
                f"Expected {self._config.n_features} features, "
                f"got {len(features)}"
            )

        x = [Value(f) for f in features]
        x = _linear(x, self._w_in)
        x = _rmsnorm(x)

        c = self._config
        head_dim = c.n_embd // c.n_head

        for layer_weights in self._layers:
            x_res = x
            x = _rmsnorm(x)
            q = _linear(x, layer_weights["attn_wq"])
            k = _linear(x, layer_weights["attn_wk"])
            v = _linear(x, layer_weights["attn_wv"])
            x_attn: list[Value] = []
            for h in range(c.n_head):
                hs = h * head_dim
                x_attn.extend(v[hs: hs + head_dim])
            x = _linear(x_attn, layer_weights["attn_wo"])
            x = [a + b for a, b in zip(x, x_res)]
            x_res = x
            x = _rmsnorm(x)
            x = _linear(x, layer_weights["mlp_fc1"])
            x = [xi.relu() for xi in x]
            x = _linear(x, layer_weights["mlp_fc2"])
            x = [a + b for a, b in zip(x, x_res)]

        logit = _linear(x, self._w_head)[0]
        score = logit.sigmoid()
        loss = -(target * score.log() + (1 - target) * (1 - score).log())

        return score.data, loss

    def train_step(
        self,
        features: list[float],
        target: float,
        lr: float = 0.01,
        beta1: float = 0.85,
        beta2: float = 0.99,
    ) -> float:
        """Single training step with Adam optimizer. Returns loss."""
        for p in self._params:
            p.grad = 0.0

        _, loss = self.forward_train(features, target)
        loss.backward()

        self._step += 1
        lr_t = lr * (1.0 - self._step / max(self._step + 1000, 1))
        eps = 1e-8

        for i, p in enumerate(self._params):
            self._m[i] = beta1 * self._m[i] + (1 - beta1) * p.grad
            self._v[i] = beta2 * self._v[i] + (1 - beta2) * p.grad**2
            m_hat = self._m[i] / (1 - beta1**self._step)
            v_hat = self._v[i] / (1 - beta2**self._step)
            p.data -= lr_t * m_hat / (v_hat**0.5 + eps)

        return loss.data

    def export_weights(self) -> dict[str, Any]:
        """Export model weights as JSON-serializable dict."""
        return {
            "config": {
                "n_features": self._config.n_features,
                "n_embd": self._config.n_embd,
                "n_head": self._config.n_head,
                "n_layer": self._config.n_layer,
            },
            "weights": [p.data for p in self._params],
            "adam_m": list(self._m),
            "adam_v": list(self._v),
            "step": self._step,
        }

    def load_weights(self, state: dict[str, Any]) -> None:
        """Load weights from exported state dict."""
        weights = state["weights"]
        if len(weights) != len(self._params):
            raise ValueError(
                f"Weight count mismatch: expected {len(self._params)}, "
                f"got {len(weights)}"
            )
        for p, w in zip(self._params, weights):
            p.data = w
        if "adam_m" in state:
            self._m = state["adam_m"]
        if "adam_v" in state:
            self._v = state["adam_v"]
        if "step" in state:
            self._step = state["step"]

    def save(self, path: str) -> None:
        """Save weights to JSON file."""
        with open(path, "w") as f:
            json.dump(self.export_weights(), f)

    @classmethod
    def load(cls, path: str) -> "MicroModel":
        """Load model from JSON file."""
        with open(path) as f:
            state = json.load(f)
        config = MicroModelConfig(**state["config"])
        model = cls(config)
        model.load_weights(state)
        return model
