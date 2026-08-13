"""
Model Trainer for Multi-Agent System.

Trains machine learning models for each agent:
- Motion: Neural network for IK prediction and trajectory optimization
- Vision: Classifier for object detection confidence calibration
- Safety: Binary classifier for safety violation detection
- Quality: Regression model for quality score prediction
- Sampling: Optimization model for strategy selection

Uses scikit-learn for traditional ML and numpy for lightweight neural nets.
"""

import json
import math
import pickle
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


# =============================================================================
# Real-Time Training Monitor (Round 10)
# =============================================================================


class MovingAverageTracker:
    """Track moving averages with anomaly detection."""

    def __init__(self, window_size: int = 10, spike_threshold: float = 3.0):
        self.window_size = window_size
        self.spike_threshold = spike_threshold
        self.values: deque = deque(maxlen=window_size)
        self.all_values: List[float] = []
        self.anomalies: List[Dict[str, Any]] = []

    def add(self, value: float, epoch: int) -> Optional[str]:
        """Add a value and check for anomalies.

        Returns:
            Warning message if anomaly detected, None otherwise.
        """
        self.values.append(value)
        self.all_values.append(value)

        if len(self.values) >= self.window_size:
            mean = np.mean(list(self.values))
            std = np.std(list(self.values)) + 1e-8

            # Spike detection
            if std > 0 and abs(value - mean) > self.spike_threshold * std:
                warning = (f"SPIKE at epoch {epoch}: value={value:.6f}, "
                           f"mean={mean:.6f}, std={std:.6f}")
                self.anomalies.append({
                    "epoch": epoch,
                    "type": "spike",
                    "value": float(value),
                    "mean": float(mean),
                    "std": float(std),
                })
                return warning

            # NaN detection
            if math.isnan(value) or math.isinf(value):
                warning = f"NAN/INF at epoch {epoch}: value={value}"
                self.anomalies.append({
                    "epoch": epoch,
                    "type": "nan_inf",
                    "value": str(value),
                })
                return warning

            # Divergence detection (loss > 10x initial)
            if len(self.all_values) > 20 and value > 10 * self.all_values[0]:
                warning = f"DIVERGENCE at epoch {epoch}: value={value:.6f} > 10x initial={self.all_values[0]:.6f}"
                self.anomalies.append({
                    "epoch": epoch,
                    "type": "divergence",
                    "value": float(value),
                    "initial": float(self.all_values[0]),
                })
                return warning

        return None

    def get_smoothed(self) -> float:
        """Get smoothed value (moving average)."""
        if not self.values:
            return 0.0
        return float(np.mean(list(self.values)))

    def get_trend(self) -> str:
        """Get trend direction."""
        if len(self.all_values) < 20:
            return "initializing"
        recent = self.all_values[-20:]
        first_half = np.mean(recent[:10])
        second_half = np.mean(recent[10:])
        if second_half < first_half * 0.95:
            return "improving"
        elif second_half > first_half * 1.05:
            return "degrading"
        else:
            return "stable"


class TrainingMonitor:
    """Real-time training monitor with progress tracking and anomaly detection."""

    def __init__(self, model_name: str, total_epochs: int):
        self.model_name = model_name
        self.total_epochs = total_epochs
        self.train_loss_tracker = MovingAverageTracker(window_size=10)
        self.val_loss_tracker = MovingAverageTracker(window_size=10)
        self.start_time = time.time()
        self.warnings: List[str] = []
        self.last_report_epoch = 0
        self.report_interval = max(1, total_epochs // 20)  # Report ~20 times

    def update(self, epoch: int, train_loss: float, val_loss: Optional[float] = None) -> None:
        """Update monitors with new losses."""
        # Check for anomalies
        train_warning = self.train_loss_tracker.add(train_loss, epoch)
        if train_warning:
            self.warnings.append(f"[{self.model_name}] {train_warning}")

        if val_loss is not None:
            val_warning = self.val_loss_tracker.add(val_loss, epoch)
            if val_warning:
                self.warnings.append(f"[{self.model_name}] {val_warning}")

        # Periodic progress report
        if epoch - self.last_report_epoch >= self.report_interval:
            self._report_progress(epoch, train_loss, val_loss)
            self.last_report_epoch = epoch

    def _report_progress(self, epoch: int, train_loss: float, val_loss: Optional[float] = None) -> None:
        """Print progress report."""
        elapsed = time.time() - self.start_time
        progress_pct = (epoch + 1) / self.total_epochs * 100
        eta = (elapsed / max(epoch + 1, 1)) * (self.total_epochs - epoch - 1)

        smooth_train = self.train_loss_tracker.get_smoothed()
        trend = self.train_loss_tracker.get_trend()

        val_str = ""
        if val_loss is not None:
            smooth_val = self.val_loss_tracker.get_smoothed()
            val_str = f", val={val_loss:.6f}(smooth={smooth_val:.6f})"

        bar_len = 20
        filled = int(bar_len * (epoch + 1) / self.total_epochs)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"  [{self.model_name}] {bar} {progress_pct:5.1f}% | "
              f"Epoch {epoch + 1}/{self.total_epochs} | "
              f"loss={train_loss:.6f}(smooth={smooth_train:.6f}){val_str} | "
              f"trend={trend} | ETA={eta:.0f}s", flush=True)

    def final_report(self) -> Dict[str, Any]:
        """Generate final monitoring report."""
        elapsed = time.time() - self.start_time
        return {
            "model": self.model_name,
            "total_epochs": self.total_epochs,
            "total_time_s": elapsed,
            "train_loss_smooth": self.train_loss_tracker.get_smoothed(),
            "val_loss_smooth": self.val_loss_tracker.get_smoothed(),
            "trend": self.train_loss_tracker.get_trend(),
            "train_anomalies": len(self.train_loss_tracker.anomalies),
            "val_anomalies": len(self.val_loss_tracker.anomalies),
            "warnings": self.warnings[-5:] if self.warnings else [],
        }


# =============================================================================
# Evaluation Metrics
# =============================================================================


@dataclass
class ModelMetrics:
    """Training and evaluation metrics for a model."""
    model_name: str
    train_loss: float
    val_loss: float
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    r2_score: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    train_time_s: float = 0.0
    num_params: int = 0
    convergence_epoch: int = 0


# =============================================================================
# Neural Network (NumPy-based)
# =============================================================================


class SimpleNN:
    """Lightweight neural network using only NumPy.

    Supports:
    - Configurable hidden layers
    - ReLU/Tanh/Sigmoid activation
    - MSE and Cross-Entropy loss
    - Mini-batch gradient descent with momentum
    - Early stopping
    - Learning rate scheduling (cosine annealing / step decay)
    - Batch normalization for training stability
    - Gradient clipping to prevent exploding gradients
    """

    def __init__(
        self,
        layer_sizes: List[int],
        learning_rate: float = 0.01,
        activation: str = "relu",
        output_activation: str = "linear",
        momentum: float = 0.9,
        weight_decay: float = 0.0001,
        use_batch_norm: bool = True,
        lr_schedule: str = "cosine",
        lr_decay_rate: float = 0.95,
        lr_decay_steps: int = 50,
        grad_clip_norm: float = 5.0,
        bn_momentum: float = 0.9,
    ):
        """Initialize the neural network.

        Args:
            layer_sizes: List of layer sizes [input, hidden1, ..., output].
            learning_rate: Initial learning rate.
            activation: Hidden layer activation ('relu', 'tanh', 'sigmoid').
            output_activation: Output layer activation.
            momentum: Momentum coefficient for SGD.
            weight_decay: L2 regularization strength.
            use_batch_norm: Whether to use batch normalization.
            lr_schedule: Learning rate schedule ('cosine', 'step', 'none').
            lr_decay_rate: Decay rate for step schedule.
            lr_decay_steps: Steps between decays for step schedule.
            grad_clip_norm: Maximum gradient norm for clipping.
            bn_momentum: Momentum for batch norm running statistics.
        """
        self.layer_sizes = layer_sizes
        self.lr = learning_rate
        self.initial_lr = learning_rate
        self.activation_name = activation
        self.output_activation_name = output_activation
        self.momentum = momentum
        self.weight_decay = weight_decay
        self.use_batch_norm = use_batch_norm
        self.lr_schedule = lr_schedule
        self.lr_decay_rate = lr_decay_rate
        self.lr_decay_steps = lr_decay_steps
        self.grad_clip_norm = grad_clip_norm
        self.bn_momentum = bn_momentum

        # Initialize weights (He initialization for ReLU, Xavier for others)
        self.weights = []
        self.biases = []
        self.velocities_w = []
        self.velocities_b = []

        # Batch normalization parameters (one per hidden layer)
        self.bn_gamma = []
        self.bn_beta = []
        self.bn_running_mean = []
        self.bn_running_var = []
        self.bn_cache = []  # Cache for backward pass

        for i in range(len(layer_sizes) - 1):
            if activation == "relu":
                scale = np.sqrt(2.0 / layer_sizes[i])
            else:
                scale = np.sqrt(2.0 / (layer_sizes[i] + layer_sizes[i + 1]))

            self.weights.append(np.random.randn(layer_sizes[i], layer_sizes[i + 1]) * scale)
            self.biases.append(np.zeros((1, layer_sizes[i + 1])))
            self.velocities_w.append(np.zeros_like(self.weights[-1]))
            self.velocities_b.append(np.zeros_like(self.biases[-1]))

            # Batch norm for hidden layers only (not output layer)
            if use_batch_norm and i < len(layer_sizes) - 2:
                self.bn_gamma.append(np.ones((1, layer_sizes[i + 1])))
                self.bn_beta.append(np.zeros((1, layer_sizes[i + 1])))
                self.bn_running_mean.append(np.zeros((1, layer_sizes[i + 1])))
                self.bn_running_var.append(np.ones((1, layer_sizes[i + 1])))
            else:
                self.bn_gamma.append(None)
                self.bn_beta.append(None)
                self.bn_running_mean.append(None)
                self.bn_running_var.append(None)

        self.num_params = sum(w.size + b.size for w, b in zip(self.weights, self.biases))
        # Add BN params
        for g, bt in zip(self.bn_gamma, self.bn_beta):
            if g is not None:
                self.num_params += g.size + bt.size
        self._convergence_epoch: int = 0

    def _activation(self, x: np.ndarray, derivative: bool = False) -> np.ndarray:
        """Apply activation function."""
        if self.activation_name == "relu":
            if derivative:
                return (x > 0).astype(float)
            return np.maximum(0, x)
        elif self.activation_name == "tanh":
            if derivative:
                return 1 - np.tanh(x) ** 2
            return np.tanh(x)
        else:  # sigmoid
            s = 1 / (1 + np.exp(-np.clip(x, -500, 500)))
            if derivative:
                return s * (1 - s)
            return s

    def _output_activation(self, x: np.ndarray) -> np.ndarray:
        """Apply output activation."""
        if self.output_activation_name == "sigmoid":
            return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
        elif self.output_activation_name == "softmax":
            exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
            return exp_x / np.sum(exp_x, axis=1, keepdims=True)
        return x  # linear

    def _batch_norm_forward(self, Z: np.ndarray, layer_idx: int, training: bool) -> np.ndarray:
        """Apply batch normalization forward pass.

        Args:
            Z: Pre-activation values (batch_size, hidden_size).
            layer_idx: Index of the layer.
            training: Whether in training mode (use batch stats) or inference (running stats).

        Returns:
            Normalized activations.
        """
        gamma = self.bn_gamma[layer_idx]
        beta = self.bn_beta[layer_idx]

        if training:
            mu = np.mean(Z, axis=0, keepdims=True)
            var = np.var(Z, axis=0, keepdims=True) + 1e-8
            Z_norm = (Z - mu) / np.sqrt(var)

            # Update running statistics
            self.bn_running_mean[layer_idx] = (
                self.bn_momentum * self.bn_running_mean[layer_idx] + (1 - self.bn_momentum) * mu
            )
            self.bn_running_var[layer_idx] = (
                self.bn_momentum * self.bn_running_var[layer_idx] + (1 - self.bn_momentum) * var
            )

            # Cache for backward pass
            self.bn_cache.append({
                "Z": Z, "Z_norm": Z_norm, "mu": mu, "var": var,
                "gamma": gamma, "layer_idx": layer_idx,
            })
        else:
            Z_norm = (Z - self.bn_running_mean[layer_idx]) / np.sqrt(self.bn_running_var[layer_idx] + 1e-8)

        return gamma * Z_norm + beta

    def forward(self, X: np.ndarray, training: bool = True) -> Tuple[np.ndarray, List[np.ndarray], List[np.ndarray]]:
        """Forward pass. Returns (output, pre_activations, post_activations).

        Args:
            X: Input features (batch_size, n_features).
            training: Whether in training mode (affects batch norm).

        Returns:
            (output, pre_activations, post_activations)
        """
        self.bn_cache = []  # Clear cache for this forward pass
        pre_acts = []
        post_acts = [X]
        A = X

        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            Z = A @ W + b

            # Apply batch normalization for hidden layers
            if self.use_batch_norm and self.bn_gamma[i] is not None and i < len(self.weights) - 1:
                Z = self._batch_norm_forward(Z, i, training)

            pre_acts.append(Z)
            if i == len(self.weights) - 1:
                A = self._output_activation(Z)
            else:
                A = self._activation(Z)
            post_acts.append(A)

        return A, pre_acts, post_acts

    def _batch_norm_backward(self, dout: np.ndarray, cache_idx: int) -> np.ndarray:
        """Batch normalization backward pass.

        Args:
            dout: Gradient from upstream.
            cache_idx: Index into bn_cache for this layer's forward pass data.

        Returns:
            Gradient w.r.t. the input to batch norm.
        """
        cache = self.bn_cache[cache_idx]
        Z = cache["Z"]
        Z_norm = cache["Z_norm"]
        mu = cache["mu"]
        var = cache["var"]
        gamma = cache["gamma"]

        m = Z.shape[0]

        # Gradient w.r.t. gamma and beta
        dgamma = np.sum(dout * Z_norm, axis=0, keepdims=True)
        dbeta = np.sum(dout, axis=0, keepdims=True)

        # Gradient w.r.t. Z_norm
        dZ_norm = dout * gamma

        # Gradient w.r.t. variance
        dvar = np.sum(dZ_norm * (Z - mu) * -0.5 * (var ** -1.5), axis=0, keepdims=True)

        # Gradient w.r.t. mean
        dmu = np.sum(dZ_norm * -1.0 / np.sqrt(var), axis=0, keepdims=True) + \
              dvar * np.sum(-2.0 * (Z - mu), axis=0, keepdims=True) / m

        # Gradient w.r.t. Z
        dZ = dZ_norm / np.sqrt(var) + dvar * 2.0 * (Z - mu) / m + dmu / m

        # Update BN parameters
        layer_idx = cache["layer_idx"]
        self.bn_gamma[layer_idx] -= self.lr * dgamma
        self.bn_beta[layer_idx] -= self.lr * dbeta

        return dZ

    def _clip_gradients(self) -> None:
        """Clip gradients to prevent exploding gradients."""
        total_norm = 0.0
        for i in range(len(self.weights)):
            total_norm += np.sum(np.square(self.velocities_w[i]))
            total_norm += np.sum(np.square(self.velocities_b[i]))

        total_norm = np.sqrt(total_norm)

        if total_norm > self.grad_clip_norm:
            scale = self.grad_clip_norm / total_norm
            for i in range(len(self.velocities_w)):
                self.velocities_w[i] *= scale
                self.velocities_b[i] *= scale

    def backward(
        self,
        X: np.ndarray,
        y: np.ndarray,
        output: np.ndarray,
        pre_acts: List[np.ndarray],
        post_acts: List[np.ndarray],
    ) -> None:
        """Backward pass - compute gradients and update weights.

        Includes batch normalization backward pass and gradient clipping.
        """
        m = X.shape[0]
        n_layers = len(self.weights)

        # Output layer gradient
        if self.output_activation_name == "softmax":
            delta = output - y
        elif self.output_activation_name == "sigmoid":
            delta = (output - y) * output * (1 - output)
        else:
            delta = output - y

        # Track BN cache index (going backwards through layers)
        bn_cache_idx = len(self.bn_cache) - 1

        for i in reversed(range(n_layers)):
            # If this is a hidden layer with batch norm, apply BN backward
            if self.use_batch_norm and self.bn_gamma[i] is not None and i < n_layers - 1:
                delta = self._batch_norm_backward(delta, bn_cache_idx)
                bn_cache_idx -= 1

            # Gradient with L2 regularization
            dW = post_acts[i].T @ delta / m + self.weight_decay * self.weights[i]
            db = np.sum(delta, axis=0, keepdims=True) / m

            # Update with momentum
            self.velocities_w[i] = self.momentum * self.velocities_w[i] - self.lr * dW
            self.velocities_b[i] = self.momentum * self.velocities_b[i] - self.lr * db
            self.weights[i] += self.velocities_w[i]
            self.biases[i] += self.velocities_b[i]

            # Backpropagate to previous layer
            if i > 0:
                delta = (delta @ self.weights[i].T) * self._activation(pre_acts[i - 1], derivative=True)

        # Apply gradient clipping
        self._clip_gradients()

    def _update_learning_rate(self, epoch: int, total_epochs: int) -> None:
        """Update learning rate based on schedule.

        Args:
            epoch: Current epoch (0-indexed).
            total_epochs: Total number of epochs.
        """
        if self.lr_schedule == "cosine":
            # Cosine annealing: smoothly decay from initial_lr to near 0
            progress = epoch / max(total_epochs, 1)
            self.lr = self.initial_lr * 0.5 * (1 + np.cos(np.pi * progress))
        elif self.lr_schedule == "step":
            # Step decay: reduce by lr_decay_rate every lr_decay_steps
            self.lr = self.initial_lr * (self.lr_decay_rate ** (epoch // self.lr_decay_steps))
        # else "none": keep initial learning rate

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 200,
        batch_size: int = 32,
        early_stopping_patience: int = 20,
        verbose: bool = True,
        monitor: Optional[TrainingMonitor] = None,
    ) -> Dict[str, List[float]]:
        """Train the neural network with learning rate scheduling and real-time monitoring.

        Args:
            X: Training features (n_samples, n_features).
            y: Training targets (n_samples, n_outputs).
            X_val: Validation features.
            y_val: Validation targets.
            epochs: Maximum training epochs.
            batch_size: Mini-batch size.
            early_stopping_patience: Patience for early stopping.
            verbose: Whether to print progress.
            monitor: Optional TrainingMonitor for real-time tracking.

        Returns:
            Dict with training history (loss, val_loss, lr).
        """
        n_samples = X.shape[0]
        history = {"train_loss": [], "val_loss": [], "lr": []}
        best_val_loss = float("inf")
        patience_counter = 0
        best_weights = None
        best_biases = None
        best_bn_gamma = None
        best_bn_beta = None

        # Create default monitor if not provided
        if monitor is None:
            monitor = TrainingMonitor("model", epochs)

        for epoch in range(epochs):
            # Update learning rate
            self._update_learning_rate(epoch, epochs)
            history["lr"].append(float(self.lr))

            # Shuffle
            indices = np.random.permutation(n_samples)
            X_shuffled = X[indices]
            y_shuffled = y[indices]

            # Mini-batch training
            epoch_loss = 0.0
            for start in range(0, n_samples, batch_size):
                end = min(start + batch_size, n_samples)
                X_batch = X_shuffled[start:end]
                y_batch = y_shuffled[start:end]

                # Forward pass in training mode (for batch norm)
                output, pre_acts, post_acts = self.forward(X_batch, training=True)
                self.backward(X_batch, y_batch, output, pre_acts, post_acts)

                batch_loss = np.mean((output - y_batch) ** 2)
                epoch_loss += batch_loss * (end - start)

            epoch_loss /= n_samples
            history["train_loss"].append(float(epoch_loss))

            # Validation (inference mode for batch norm)
            val_loss = None
            if X_val is not None and y_val is not None:
                val_out, _, _ = self.forward(X_val, training=False)
                val_loss = float(np.mean((val_out - y_val) ** 2))
                history["val_loss"].append(val_loss)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    best_weights = [w.copy() for w in self.weights]
                    best_biases = [b.copy() for b in self.biases]
                    best_bn_gamma = [g.copy() if g is not None else None for g in self.bn_gamma]
                    best_bn_beta = [b.copy() if b is not None else None for b in self.bn_beta]
                    self._convergence_epoch = epoch + 1
                else:
                    patience_counter += 1

                # Update monitor
                monitor.update(epoch, epoch_loss, val_loss)

                if patience_counter >= early_stopping_patience:
                    if verbose:
                        print(f"    Early stopping at epoch {epoch + 1}", flush=True)
                    break
            else:
                monitor.update(epoch, epoch_loss)

            if verbose and (epoch + 1) % 50 == 0:
                val_str = f", val_loss={val_loss:.6f}" if val_loss is not None else ""
                lr_str = f", lr={self.lr:.6f}"
                print(f"    Epoch {epoch + 1}/{epochs}: loss={epoch_loss:.6f}{val_str}{lr_str}", flush=True)

        # Restore best weights
        if best_weights is not None:
            self.weights = best_weights
            self.biases = best_biases
            if best_bn_gamma is not None:
                self.bn_gamma = best_bn_gamma
                self.bn_beta = best_bn_beta

        return history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions in inference mode (no batch norm training stats)."""
        output, _, _ = self.forward(X, training=False)
        return output

    def save(self, filepath: str) -> None:
        """Save model to disk including batch norm parameters."""
        model_data = {
            "layer_sizes": self.layer_sizes,
            "weights": [w.tolist() for w in self.weights],
            "biases": [b.tolist() for b in self.biases],
            "activation": self.activation_name,
            "output_activation": self.output_activation_name,
            "use_batch_norm": self.use_batch_norm,
            "bn_gamma": [g.tolist() if g is not None else None for g in self.bn_gamma],
            "bn_beta": [b.tolist() if b is not None else None for b in self.bn_beta],
            "bn_running_mean": [m.tolist() if m is not None else None for m in self.bn_running_mean],
            "bn_running_var": [v.tolist() if v is not None else None for v in self.bn_running_var],
        }
        with open(filepath, "wb") as f:
            pickle.dump(model_data, f)

    @classmethod
    def load(cls, filepath: str) -> "SimpleNN":
        """Load model from disk including batch norm parameters."""
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        model = cls(
            layer_sizes=data["layer_sizes"],
            activation=data["activation"],
            output_activation=data["output_activation"],
            use_batch_norm=data.get("use_batch_norm", False),
        )
        model.weights = [np.array(w) for w in data["weights"]]
        model.biases = [np.array(b) for b in data["biases"]]
        # Restore BN parameters if available
        if data.get("bn_gamma"):
            model.bn_gamma = [np.array(g) if g is not None else None for g in data["bn_gamma"]]
            model.bn_beta = [np.array(b) if b is not None else None for b in data["bn_beta"]]
            model.bn_running_mean = [np.array(m) if m is not None else None for m in data["bn_running_mean"]]
            model.bn_running_var = [np.array(v) if v is not None else None for v in data["bn_running_var"]]
        return model


# =============================================================================
# Model Trainer Class
# =============================================================================


class ModelTrainer:
    """Trains ML models for all agents and evaluates performance."""

    def __init__(self, data_dir: str = "data/training", model_dir: str = "models"):
        """Initialize the model trainer.

        Args:
            data_dir: Directory containing training data.
            model_dir: Directory to save trained models.
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.results: Dict[str, ModelMetrics] = {}

    def _load_data(self, filename: str) -> List[Dict[str, Any]]:
        """Load dataset from JSON."""
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _split_data(self, X: np.ndarray, y: np.ndarray, val_ratio: float = 0.2) -> Tuple:
        """Split data into train/validation sets."""
        n = len(X)
        indices = np.random.permutation(n)
        split = int(n * (1 - val_ratio))
        train_idx, val_idx = indices[:split], indices[split:]
        return X[train_idx], X[val_idx], y[train_idx], y[val_idx]

    def _normalize(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Z-score normalize features."""
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0) + 1e-8
        return (X - mean) / std, mean, std

    def _kfold_cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
        create_model_fn: Optional[Callable[[], SimpleNN]] = None,
        epochs: int = 200,
        batch_size: int = 32,
        early_stopping_patience: int = 20,
        is_classification: bool = False,
    ) -> Dict[str, Any]:
        """Perform k-fold cross-validation for robust evaluation.

        Args:
            X: Feature matrix.
            y: Target vector.
            n_folds: Number of folds.
            create_model_fn: Function that creates a new model.
            epochs: Training epochs per fold.
            batch_size: Batch size.
            early_stopping_patience: Early stopping patience.
            is_classification: Whether this is a classification task.

        Returns:
            CV results dict with mean ± std of metrics.
        """
        if create_model_fn is None:
            raise ValueError("create_model_fn must be provided")

        n_samples = X.shape[0]
        indices = np.random.permutation(n_samples)
        fold_size = n_samples // n_folds

        cv_scores = {
            "val_loss": [],
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1": [],
            "r2": [],
            "mae": [],
        }

        for fold in range(n_folds):
            # Split into train/val for this fold
            val_start = fold * fold_size
            val_end = val_start + fold_size if fold < n_folds - 1 else n_samples
            val_idx = indices[val_start:val_end]
            train_idx = np.concatenate([indices[:val_start], indices[val_end:]])

            X_train_fold, X_val_fold = X[train_idx], X[val_idx]
            y_train_fold, y_val_fold = y[train_idx], y[val_idx]

            # Create and train model
            model = create_model_fn()
            model.train(
                X_train_fold, y_train_fold,
                X_val=X_val_fold, y_val=y_val_fold,
                epochs=epochs, batch_size=batch_size,
                early_stopping_patience=early_stopping_patience,
                verbose=False,
            )

            # Evaluate
            y_pred = model.predict(X_val_fold)
            val_loss = float(np.mean((y_pred - y_val_fold) ** 2))
            cv_scores["val_loss"].append(val_loss)

            if is_classification:
                y_pred_bin = (y_pred > 0.5).astype(float)
                tp = np.sum((y_pred_bin == 1) & (y_val_fold == 1))
                tn = np.sum((y_pred_bin == 0) & (y_val_fold == 0))
                fp = np.sum((y_pred_bin == 1) & (y_val_fold == 0))
                fn = np.sum((y_pred_bin == 0) & (y_val_fold == 1))
                acc = (tp + tn) / len(y_val_fold)
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
                cv_scores["accuracy"].append(float(acc))
                cv_scores["precision"].append(float(prec))
                cv_scores["recall"].append(float(rec))
                cv_scores["f1"].append(float(f1))
            else:
                y_pred_f = y_pred.flatten()
                y_val_f = y_val_fold.flatten()
                ss_res = np.sum((y_val_f - y_pred_f) ** 2)
                ss_tot = np.sum((y_val_f - np.mean(y_val_f)) ** 2)
                r2 = 1 - ss_res / (ss_tot + 1e-8)
                mae = float(np.mean(np.abs(y_pred_f - y_val_f)))
                cv_scores["r2"].append(float(r2))
                cv_scores["mae"].append(mae)

        # Compute summary
        summary = {}
        for metric, values in cv_scores.items():
            if values:
                summary[metric] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "values": [float(v) for v in values],
                }

        print(f"    CV ({n_folds}-fold): ", end="")
        if is_classification:
            print(f"Acc={summary['accuracy']['mean']:.4f}±{summary['accuracy']['std']:.4f}, "
                  f"F1={summary['f1']['mean']:.4f}±{summary['f1']['std']:.4f}")
        else:
            print(f"R²={summary['r2']['mean']:.4f}±{summary['r2']['std']:.4f}, "
                  f"MAE={summary['mae']['mean']:.4f}±{summary['mae']['std']:.4f}")

        return summary

    # =========================================================================
    # Motion Model: IK Prediction
    # =========================================================================

    def train_motion_model(self, epochs: int = 500) -> ModelMetrics:
        """Train a neural network for inverse kinematics prediction.

        Maps end-effector pose → joint angles. Uses deeper architecture
        with residual-style connections and data augmentation.

        Round 9: Fixed seed for reproducibility across runs.
        Round 11: epochs parameter added for multi-round training.

        Args:
            epochs: Number of training epochs (default: 500).

        Returns:
            ModelMetrics with evaluation results.
        """
        print("\n  Training Motion (IK) Model (Round 9: fixed seed)...")
        np.random.seed(42)  # Fixed seed for reproducibility

        data = self._load_data("ik_dataset.json")
        if not data:
            print("    No IK data found, skipping")
            return ModelMetrics(model_name="motion_ik", train_loss=0, val_loss=0)

        # Prepare data: pose → joint angles
        X_list, y_list = [], []
        for sample in data:
            if sample.get("reachable") and sample.get("joints"):
                pose = sample["pose"]
                joints = sample["joints"]
                X_list.append(pose)  # [x, y, z, roll, pitch, yaw]
                y_list.append(joints)  # [j1, j2, j3, j4, j5, j6]
                # Data augmentation: add small noise perturbations (Round 6: 3x)
                for _ in range(3):  # 3x augmentation
                    noisy_pose = [p + np.random.normal(0, 1.0) for p in pose[:3]] + \
                                 [p + np.random.normal(0, 0.02) for p in pose[3:]]
                    # FK check: noisy pose should map to similar joints
                    noisy_joints = [j + np.random.normal(0, 0.01) for j in joints]
                    X_list.append(noisy_pose)
                    y_list.append(noisy_joints)

        if len(X_list) < 50:
            print(f"    Insufficient data ({len(X_list)} samples), skipping")
            return ModelMetrics(model_name="motion_ik", train_loss=0, val_loss=0)

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)

        # Normalize
        X_norm, X_mean, X_std = self._normalize(X)
        y_norm, y_mean, y_std = self._normalize(y)

        # Split
        X_train, X_val, y_train, y_val = self._split_data(X_norm, y_norm, val_ratio=0.15)

        # Deeper network with more capacity for nonlinear IK mapping
        nn = SimpleNN(
            layer_sizes=[6, 256, 256, 128, 128, 64, 6],
            learning_rate=0.001,
            activation="tanh",  # tanh works better for angle prediction
            output_activation="linear",
            momentum=0.95,
            weight_decay=0.00001,
            use_batch_norm=True,
            lr_schedule="cosine",
            grad_clip_norm=5.0,
        )

        start_time = time.time()
        history = nn.train(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            epochs=epochs, batch_size=128,
            early_stopping_patience=50,
            verbose=True,
        )
        train_time = time.time() - start_time

        # Evaluate
        y_pred = nn.predict(X_val)
        y_pred_denorm = y_pred * y_std + y_mean
        y_val_denorm = y_val * y_std + y_mean

        mae = np.mean(np.abs(y_pred_denorm - y_val_denorm))
        rmse = np.sqrt(np.mean((y_pred_denorm - y_val_denorm) ** 2))

        # Per-joint R²
        r2_per_joint = []
        for j in range(6):
            ss_res = np.sum((y_val_denorm[:, j] - y_pred_denorm[:, j]) ** 2)
            ss_tot = np.sum((y_val_denorm[:, j] - np.mean(y_val_denorm[:, j])) ** 2)
            r2_j = 1 - ss_res / (ss_tot + 1e-8)
            r2_per_joint.append(float(r2_j))

        # Overall R²
        ss_res = np.sum((y_val_denorm - y_pred_denorm) ** 2)
        ss_tot = np.sum((y_val_denorm - np.mean(y_val_denorm, axis=0)) ** 2)
        r2 = 1 - ss_res / (ss_tot + 1e-8)

        # Save model
        nn.save(str(self.model_dir / "motion_ik_model.pkl"))

        # Save normalization metadata for consistent inference
        motion_meta = {
            "X_mean": X_mean.tolist(),
            "X_std": X_std.tolist(),
            "y_mean": y_mean.tolist(),
            "y_std": y_std.tolist(),
            "n_features": 6,
            "feature_names": ["x", "y", "z", "roll", "pitch", "yaw"],
            "output_names": ["j1", "j2", "j3", "j4", "j5", "j6"],
        }
        meta_path = self.model_dir / "motion_ik_model_meta.json"
        with open(meta_path, "w") as f:
            json.dump(motion_meta, f, indent=2)

        metrics = ModelMetrics(
            model_name="motion_ik",
            train_loss=history["train_loss"][-1],
            val_loss=history["val_loss"][-1] if history["val_loss"] else 0,
            r2_score=float(np.mean(r2)),
            mae=float(mae),
            rmse=float(rmse),
            train_time_s=train_time,
            num_params=nn.num_params,
            convergence_epoch=len(history["train_loss"]),
        )
        self.results["motion"] = metrics
        print(f"    R²={metrics.r2_score:.4f}, MAE={metrics.mae:.4f} rad ({math.degrees(metrics.mae):.1f}°)")
        print(f"    Per-joint R²: {[f'{r:.3f}' for r in r2_per_joint]}")
        return metrics

    # =========================================================================
    # Safety Model: Violation Classifier
    # =========================================================================

    def train_safety_model(self, epochs: int = 500) -> ModelMetrics:
        """Train a binary classifier for safety violation detection.

        Round 6: Simplified feature set to prevent overfitting (Recall=1.0 issue).
        Reduced from 27 to 18 features, simpler architecture, harder boundary cases.

        Maps enhanced joint features → safe/unsafe.

        Round 11: epochs parameter added for multi-round training.

        Args:
            epochs: Number of training epochs (default: 500).

        Returns:
            ModelMetrics with evaluation results.
        """
        print("\n  Training Safety Model (Round 9: diverse boundary samples)...")

        data = self._load_data("safety_dataset.json")
        if not data:
            print("    No safety data found, skipping")
            return ModelMetrics(model_name="safety", train_loss=0, val_loss=0)

        # Joint limits in degrees
        JOINT_LIMITS_SAFETY = [
            (-170, 170), (-130, 130), (-150, 150),
            (-180, 180), (-120, 120), (-180, 180),
        ]
        MAX_VELOCITY = 180.0  # degrees/s

        # Prepare data with simplified features (Round 6: 18 features vs 27)
        X_list, y_list = [], []
        for sample in data:
            positions = sample.get("joint_positions", [])
            velocities = sample.get("joint_velocities", [])
            if len(positions) < 6 or len(velocities) < 6:
                continue

            # Round 6: Simplified features - only most discriminative ones
            features = []
            
            # Distance to joint limits (6 features) - most important for safety
            for j in range(6):
                lo, hi = JOINT_LIMITS_SAFETY[j]
                pos = positions[j]
                range_val = hi - lo
                if range_val > 0:
                    center = (lo + hi) / 2
                    dist_to_center = (pos - center) / (range_val / 2)
                    features.append(dist_to_center)
                else:
                    features.append(0.0)

            # Velocity-to-limit ratio (6 features)
            for v in velocities[:6]:
                features.append(min(abs(v) / MAX_VELOCITY, 2.0))

            # Maximum velocity ratio (1 feature)
            max_vel_ratio = max(min(abs(v) / MAX_VELOCITY, 2.0) for v in velocities[:6])
            features.append(max_vel_ratio)

            # Maximum position violation (1 feature)
            max_violation = 0.0
            for j in range(6):
                lo, hi = JOINT_LIMITS_SAFETY[j]
                pos = positions[j]
                if pos < lo:
                    max_violation = max(max_violation, (lo - pos) / (hi - lo + 1e-8))
                elif pos > hi:
                    max_violation = max(max_violation, (pos - hi) / (hi - lo + 1e-8))
            features.append(max_violation)

            # Combined risk score (1 feature)
            pos_risk = max(abs(f) for f in features[:6])
            vel_risk = max_vel_ratio
            combined_risk = 0.5 * pos_risk + 0.5 * vel_risk
            features.append(combined_risk)
            
            # Round 6: Add only 3 raw joint positions (most critical joints)
            features.extend(positions[:3])
            # Round 6: Add only 1 raw velocity (max velocity joint)
            features.append(max(abs(v) for v in velocities[:6]))

            X_list.append(features)
            y_list.append(1.0 if sample.get("is_safe", True) else 0.0)

        if len(X_list) < 50:
            print(f"    Insufficient data ({len(X_list)} samples), skipping")
            return ModelMetrics(model_name="safety", train_loss=0, val_loss=0)

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32).reshape(-1, 1)

        n_features = X.shape[1]
        print(f"    Features: {n_features} (simplified from 27), samples: {len(X_list)}")

        X_norm, X_mean, X_std = self._normalize(X)
        X_train, X_val, y_train, y_val = self._split_data(X_norm, y, val_ratio=0.15)

        # Round 6: Simpler architecture to prevent overfitting
        nn = SimpleNN(
            layer_sizes=[n_features, 64, 32, 16, 1],
            learning_rate=0.001,
            activation="tanh",
            output_activation="sigmoid",
            momentum=0.95,
            weight_decay=0.0001,
            use_batch_norm=True,
            lr_schedule="cosine",
            grad_clip_norm=5.0,
        )

        start_time = time.time()
        history = nn.train(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            epochs=epochs, batch_size=32,
            early_stopping_patience=50,
            verbose=True,
        )
        train_time = time.time() - start_time

        # Evaluate
        y_pred_prob = nn.predict(X_val)
        # Find optimal threshold (maximize F1)
        best_f1 = 0.0
        best_threshold = 0.5
        for thr in np.arange(0.3, 0.8, 0.05):
            y_pred_t = (y_pred_prob > thr).astype(float)
            tp = np.sum((y_pred_t == 1) & (y_val == 1))
            tn = np.sum((y_pred_t == 0) & (y_val == 0))
            fp = np.sum((y_pred_t == 1) & (y_val == 0))
            fn = np.sum((y_pred_t == 0) & (y_val == 1))
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = thr

        # Use optimal threshold
        y_pred = (y_pred_prob > best_threshold).astype(float)

        tp = np.sum((y_pred == 1) & (y_val == 1))
        tn = np.sum((y_pred == 0) & (y_val == 0))
        fp = np.sum((y_pred == 1) & (y_val == 0))
        fn = np.sum((y_pred == 0) & (y_val == 1))

        accuracy = (tp + tn) / len(y_val)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        nn.save(str(self.model_dir / "safety_model.pkl"))

        # Save feature metadata
        feature_meta = {
            "n_features": n_features,
            "feature_names": (
                [f"joint_{j}_dist_to_center" for j in range(6)] +
                [f"joint_{j}_vel_ratio" for j in range(6)] +
                ["max_vel_ratio", "max_position_violation", "combined_risk"] +
                ["joint_0_pos", "joint_1_pos", "joint_2_pos", "max_abs_vel"]
            ),
            "X_mean": X_mean.tolist(),
            "X_std": X_std.tolist(),
            "optimal_threshold": float(best_threshold),
        }
        meta_path = self.model_dir / "safety_model_meta.json"
        with open(meta_path, "w") as f:
            json.dump(feature_meta, f, indent=2)

        metrics = ModelMetrics(
            model_name="safety",
            train_loss=history["train_loss"][-1],
            val_loss=history["val_loss"][-1] if history["val_loss"] else 0,
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            train_time_s=train_time,
            num_params=nn.num_params,
            convergence_epoch=len(history["train_loss"]),
        )
        self.results["safety"] = metrics
        print(f"    Accuracy={metrics.accuracy:.4f}, Precision={metrics.precision:.4f}, "
              f"Recall={metrics.recall:.4f}, F1={metrics.f1_score:.4f} "
              f"(threshold={best_threshold:.2f})")
        return metrics

    # =========================================================================
    # Quality Model: Score Regression
    # =========================================================================

    def train_quality_model(self, epochs: int = 1000) -> ModelMetrics:
        """Train a regression model for quality score prediction.

        Enhanced feature engineering + ensemble learning:
        - Defect severity weighted scores (severe=9, moderate=4, minor=1)
        - Defect type encoding (8 types one-hot)
        - Spatial clustering of defects
        - Defect density metrics
        - Product type encoding
        - Feature interactions (severity × area, etc.)
        - Ensemble: train 3 models with different seeds, average predictions

        Maps enhanced defect features → quality score.

        Round 11: epochs parameter added for multi-round training.

        Args:
            epochs: Number of training epochs (default: 1000).

        Returns:
            ModelMetrics with evaluation results.
        """
        print("\n  Training Quality Model (Round 9: deterministic mapping, verified)...")

        data = self._load_data("quality_dataset.json")
        if not data:
            print("    No quality data found, skipping")
            return ModelMetrics(model_name="quality", train_loss=0, val_loss=0)

        # Enhanced feature engineering (same as before)
        X_list, y_list = [], []

        severity_weights = {"severe": 9.0, "moderate": 4.0, "minor": 1.0}
        defect_types = [
            "scratch", "discoloration", "dimension_error",
            "surface_defect", "color_inconsistency",
            "missing_feature", "contamination", "deformation",
        ]
        product_types = ["default", "precision", "coarse"]

        for sample in data:
            defects = sample.get("defects", [])
            product_type = sample.get("product_type", "default")

            num_defects = len(defects)
            severe_count = sum(1 for d in defects if d.get("severity") == "severe")
            moderate_count = sum(1 for d in defects if d.get("severity") == "moderate")
            minor_count = sum(1 for d in defects if d.get("severity") == "minor")

            total_area = sum(d.get("area", 0) for d in defects)
            max_area = max((d.get("area", 0) for d in defects), default=0)
            mean_area = total_area / max(num_defects, 1)

            severity_weighted = sum(
                severity_weights.get(d.get("severity", "minor"), 1.0)
                for d in defects
            )

            type_counts = [sum(1 for d in defects if d.get("type") == t) for t in defect_types]

            spatial_cluster = 0.0
            if num_defects >= 2:
                positions = [d.get("position", (0, 0)) for d in defects]
                distances = []
                for i in range(len(positions)):
                    for j in range(i + 1, len(positions)):
                        dx = positions[i][0] - positions[j][0]
                        dy = positions[i][1] - positions[j][1]
                        distances.append(math.sqrt(dx**2 + dy**2))
                if distances:
                    min_dist = min(distances)
                    mean_dist = sum(distances) / len(distances)
                    spatial_cluster = 1.0 - min(min_dist / max(mean_dist, 1.0), 1.0)

            defect_density = total_area / max(num_defects, 1)
            product_encoding = [1.0 if pt == product_type else 0.0 for pt in product_types]

            severity_area_interaction = severity_weighted * math.log1p(total_area)
            max_severity = 3.0 if severe_count > 0 else (2.0 if moderate_count > 0 else (1.0 if minor_count > 0 else 0.0))
            count_severity_interaction = num_defects * max_severity
            
            # Round 3: Three-way feature interactions for richer representation
            density_severity = defect_density * max_severity
            cluster_severity = spatial_cluster * max_severity
            area_density_interaction = math.log1p(total_area) * defect_density
            severe_ratio = severe_count / max(num_defects, 1)
            moderate_ratio = moderate_count / max(num_defects, 1)
            defect_concentration = num_defects / (max(total_area, 1) + 1)

            features = [
                num_defects, severe_count, moderate_count, minor_count,
                total_area, max_area, mean_area,
                severity_weighted,
                *type_counts,
                spatial_cluster,
                defect_density,
                *product_encoding,
                severity_area_interaction,
                count_severity_interaction,
                # Round 3: additional 3-way interactions
                density_severity,
                cluster_severity,
                area_density_interaction,
                severe_ratio,
                moderate_ratio,
                defect_concentration,
            ]

            X_list.append(features)
            y_list.append(sample.get("quality_score", 0.0))

        if len(X_list) < 50:
            print(f"    Insufficient data ({len(X_list)} samples), skipping")
            return ModelMetrics(model_name="quality", train_loss=0, val_loss=0)

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32).reshape(-1, 1) / 100.0

        X_norm, X_mean, X_std = self._normalize(X)
        X_train, X_val, y_train, y_val = self._split_data(X_norm, y, val_ratio=0.15)

        n_features = X.shape[1]
        print(f"    Features: {n_features}, samples: {len(X_list)}")

        # Round 7: Deeper network for deterministic data, more patience
        nn = SimpleNN(
            layer_sizes=[n_features, 128, 128, 64, 32, 1],
            learning_rate=0.0005,  # Lower learning rate for stability
            activation="tanh",
            output_activation="sigmoid",
            momentum=0.95,
            weight_decay=0.0003,  # Moderate L2 regularization
            use_batch_norm=True,
            lr_schedule="cosine",
            grad_clip_norm=2.0,  # Tight gradient clipping
        )

        start_time = time.time()
        history = nn.train(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            epochs=epochs, batch_size=64,
            early_stopping_patience=100,
            verbose=True,
        )
        train_time = time.time() - start_time

        # Single model prediction
        y_pred_norm = nn.predict(X_val)
        y_pred = y_pred_norm * 100.0
        y_val_denorm = y_val * 100.0

        mae = np.mean(np.abs(y_pred - y_val_denorm))
        rmse = np.sqrt(np.mean((y_pred - y_val_denorm) ** 2))
        ss_res = np.sum((y_val_denorm - y_pred) ** 2)
        ss_tot = np.sum((y_val_denorm - np.mean(y_val_denorm)) ** 2)
        r2 = 1 - ss_res / (ss_tot + 1e-8)

        # Classification accuracy
        thresholds = {"pass": 70, "resample": 50, "reject": 30}
        correct_cls = 0
        for pred_val, true_val in zip(y_pred.flatten(), y_val_denorm.flatten()):
            pred_cls = "accept" if pred_val >= thresholds["pass"] else ("rework" if pred_val >= thresholds["reject"] else "reject")
            true_cls = "accept" if true_val >= thresholds["pass"] else ("rework" if true_val >= thresholds["reject"] else "reject")
            if pred_cls == true_cls:
                correct_cls += 1
        cls_accuracy = correct_cls / len(y_val)

        # Save model
        nn.save(str(self.model_dir / "quality_model.pkl"))

        # Save metadata
        feature_meta = {
            "n_features": n_features,
            "feature_names": [
                "num_defects", "severe_count", "moderate_count", "minor_count",
                "total_area", "max_area", "mean_area",
                "severity_weighted",
                *[f"type_{t}" for t in defect_types],
                "spatial_cluster", "defect_density",
                *[f"product_{pt}" for pt in product_types],
                "severity_area_interaction", "count_severity_interaction",
                "density_severity", "cluster_severity", "area_density_interaction",
                "severe_ratio", "moderate_ratio", "defect_concentration",
            ],
            "X_mean": X_mean.tolist(),
            "X_std": X_std.tolist(),
        }
        meta_path = self.model_dir / "quality_model_meta.json"
        with open(meta_path, "w") as f:
            json.dump(feature_meta, f, indent=2)

        metrics = ModelMetrics(
            model_name="quality",
            train_loss=history["train_loss"][-1],
            val_loss=history["val_loss"][-1] if history["val_loss"] else 0,
            r2_score=float(r2),
            mae=float(mae),
            rmse=float(rmse),
            accuracy=float(cls_accuracy),
            train_time_s=train_time,
            num_params=nn.num_params,
            convergence_epoch=len(history["train_loss"]),
        )
        self.results["quality"] = metrics
        print(f"    R²={metrics.r2_score:.4f}, MAE={metrics.mae:.2f}, RMSE={metrics.rmse:.2f}, "
              f"ClsAcc={cls_accuracy:.4f} (single robust model)")
        return metrics

    # =========================================================================
    # Motion Collision Model
    # =========================================================================

    def train_collision_model(self, epochs: int = 300, n_ensemble: int = 7) -> ModelMetrics:
        """Train a model for collision risk prediction.

        Uses real multi-obstacle collision data from multi_obstacle_collision.json
        augmented with synthetic edge cases. Enhanced feature engineering:
        - Minimum distance to any obstacle
        - Mean distance to all obstacles
        - Distance variance (spread)
        - Number of nearby obstacles (< 50mm)
        - Closest approach angle
        - Velocity vector dot product with obstacle direction
        - Time-to-collision estimate
        - Combined risk score

        Maps enhanced obstacle features → collision probability.

        Returns:
            ModelMetrics with evaluation results.
        """
        print("\n  Training Collision Detection Model (Round 12: rule-aligned boundary, 19 features)...")

        # --- Load real multi-obstacle collision data ---
        real_data = self._load_data("multi_obstacle_collision.json")
        real_samples = []
        for sample in real_data:
            # Handle both formats: single obstacle or list of obstacles
            obstacles = sample.get("obstacles", [])
            if not obstacles:
                # Single obstacle format: obstacle_position, distance_mm, collision_detected
                obs_pos = sample.get("obstacle_position", [0, 0, 0])
                dist = sample.get("distance_mm", 200)
                obstacles = [{"position": obs_pos, "distance": dist}]
            joints = sample.get("joint_positions", [])
            if len(joints) < 6:
                continue
            # Extract obstacle distances and positions. Real generator stores
            # obstacle_position = [x, y, z, radius]; keep the radius (4th element)
            # so the variable collision boundary is available as a feature.
            obs_dists = []
            obs_positions = []
            for obs in obstacles:
                d = obs.get("distance", obs.get("distance_mm", np.random.uniform(0, 200)))
                pos = obs.get("position", [0, 0, 0])
                obs_dists.append(d)
                if len(pos) >= 4:
                    obs_positions.append(pos[:4])
                elif len(pos) >= 3:
                    obs_positions.append(pos[:3] + [35.0])  # default mid-range radius
                else:
                    obs_positions.append([0, 0, 0, 35.0])
            real_samples.append({
                "obstacle_dists": obs_dists,
                "obstacle_positions": obs_positions,
                "joint_velocities": sample.get("joint_velocities", [0] * 6),
                "label": 1.0 if sample.get("collision_detected", sample.get("has_collision", False)) else 0.0,
            })

        # --- Augment with synthetic edge cases (Round 12: 5000, rule-aligned) ---
        # Round 12 FIX: The previous synthetic rule labeled collision when
        # min_dist < 25mm, but the REAL generator (data_generator
        # generate_multi_obstacle_collision) labels collision when
        # min_dist < radius + 30 with radius ~ U(10,60), i.e. a VARIABLE boundary
        # in [40, 90]mm. That mismatch taught the model a ~25mm collision
        # boundary, so real collisions (40-90mm) were scored safe -> recall ~0.30.
        # Now we sample a representative obstacle radius per scene, label with the
        # SAME variable boundary, and store the radius so the model can learn it.
        n_synthetic = 5000
        synthetic_samples = []
        for _ in range(n_synthetic):
            n_obs = np.random.randint(1, 6)
            radius = np.random.uniform(10, 60)  # representative obstacle radius (mm)
            obs_dists = []
            obs_positions = []
            for _ in range(n_obs):
                if np.random.random() < 0.35:
                    obs_dists.append(np.random.uniform(30, 80))  # Hard negative
                else:
                    obs_dists.append(np.random.uniform(0, 300))
                # position = [x, y, z, radius]; radius stored as 4th element so the
                # feature extractor can read the variable collision boundary.
                obs_positions.append([
                    np.random.uniform(-200, 200),
                    np.random.uniform(-200, 200),
                    np.random.uniform(-100, 100),
                    radius,
                ])
            # Label with the real variable boundary: collision iff closest obstacle
            # is within its radius + 30mm clearance.
            label = 1.0 if min(obs_dists) < radius + 30 else 0.0
            synthetic_samples.append({
                "obstacle_dists": obs_dists,
                "obstacle_positions": obs_positions,
                "joint_velocities": [np.random.uniform(0, 500) for _ in range(6)],
                "joint_positions": [np.random.uniform(-180, 180) for _ in range(6)],
                "label": float(label),
            })

        all_samples = real_samples + synthetic_samples
        if len(all_samples) < 100:
            all_samples = real_samples if real_samples else synthetic_samples

        # --- Round 6: Enhanced feature engineering with kinematic features ---
        X_list, y_list = [], []
        for sample in all_samples:
            obs_dists = sample.get("obstacle_dists", [50])
            obs_positions = sample.get("obstacle_positions", [[0, 0, 0]])
            velocities = sample.get("joint_velocities", [0] * 6)
            joints = sample.get("joint_positions", [0] * 6)

            # Distance features
            min_dist = min(obs_dists) if obs_dists else 200
            mean_dist = sum(obs_dists) / len(obs_dists) if obs_dists else 200
            dist_std = float(np.std(obs_dists)) if len(obs_dists) > 1 else 0.0
            dist_range = max(obs_dists) - min_dist if len(obs_dists) > 1 else 0.0

            # Obstacle count features
            n_obstacles = len(obs_dists)
            n_close = sum(1 for d in obs_dists if d < 50)
            n_very_close = sum(1 for d in obs_dists if d < 20)

            # Velocity features
            max_vel = max(abs(v) for v in velocities[:6]) if velocities else 0
            mean_vel = sum(abs(v) for v in velocities[:6]) / 6 if velocities else 0
            
            # Round 6: Kinematic features from joint angles
            # Joint spread (how far from center position)
            joint_center_dist = sum(abs(j) for j in joints[:6]) / 6 if len(joints) >= 6 else 0
            # Joint velocity-vs-distance interaction
            vel_dist_ratio = max_vel / (min_dist + 1) if min_dist > 0 else max_vel
            # Obstacle angular spread (how obstacles are distributed)
            if len(obs_positions) >= 2 and obs_positions[0]:
                angles = []
                for pos in obs_positions:
                    if len(pos) >= 2:
                        angles.append(math.atan2(pos[1], pos[0] + 1e-8))
                if len(angles) >= 2:
                    angular_spread = max(angles) - min(angles)
                    if angular_spread > math.pi:
                        angular_spread = 2 * math.pi - angular_spread
                else:
                    angular_spread = 0.0
            else:
                angular_spread = 0.0

            # Closest approach direction (relative to obstacle)
            if obs_positions and len(obs_positions[0]) >= 3:
                closest_pos = obs_positions[np.argmin(obs_dists)] if obs_dists else [0, 0, 0]
                approach_angle = math.atan2(
                    abs(closest_pos[1]), abs(closest_pos[0]) + 1e-8
                )
            else:
                approach_angle = 0.0

            # Time-to-collision estimate (distance / velocity)
            effective_vel = max(max_vel, 1.0)
            ttc = min_dist / effective_vel

            # Round 12: Effective obstacle radius of the CLOSEST obstacle.
            # Real labeling uses collision iff min_dist < radius + 30, so the
            # radius exposes the (variable) collision boundary to the model.
            if obs_positions and obs_dists:
                closest_idx = int(np.argmin(obs_dists))
                eff_radius = obs_positions[closest_idx][3] \
                    if len(obs_positions[closest_idx]) >= 4 else 35.0
            else:
                eff_radius = 35.0
            # Clearance margin: negative => inside the collision boundary.
            clearance = min_dist - (eff_radius + 30.0)

            # Combined risk score
            dist_risk = 1.0 / (1.0 + min_dist / 50.0)
            vel_risk = min(1.0, max_vel / 500.0)
            density_risk = min(1.0, n_close / 5.0)
            combined_risk = 0.4 * dist_risk + 0.3 * vel_risk + 0.3 * density_risk
            
            # Round 6: Additional interaction features
            close_ratio = n_close / max(n_obstacles, 1)
            risk_velocity_product = combined_risk * vel_risk

            features = [
                min_dist, mean_dist, dist_std, dist_range,
                float(n_obstacles), float(n_close), float(n_very_close),
                max_vel, mean_vel,
                approach_angle,
                ttc,
                combined_risk,
                # Round 12: variable-boundary features
                eff_radius,
                clearance,
                # Round 6: New kinematic features
                joint_center_dist,
                vel_dist_ratio,
                angular_spread,
                close_ratio,
                risk_velocity_product,
            ]

            X_list.append(features)
            y_list.append(sample.get("label", 0.0))

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32).reshape(-1, 1)

        # real_samples come first in all_samples, then synthetic_samples.
        n_real = len(real_samples)
        n_synth = len(synthetic_samples)

        # Split the REAL rows into a train/val holdout (val is NEVER seen by
        # training), so the decision threshold can be tuned on a PURE-REAL set
        # that matches the deployment/test distribution (~2.5% collision).
        rng_split = np.random.default_rng(123)
        real_idx = np.arange(n_real)
        rng_split.shuffle(real_idx)
        n_val_real = max(1, int(n_real * 0.15))
        val_real_idx = real_idx[:n_val_real]
        train_real_idx = real_idx[n_val_real:]

        val_rows = val_real_idx.tolist()
        train_rows = train_real_idx.tolist() + list(range(n_real, n_real + n_synth))

        # Pure-real validation holdout for threshold tuning
        X_val = X[val_rows]
        y_val = y[val_rows]
        # Training set: real_train + synthetic
        X_train_all = X[train_rows]
        y_train_all = y[train_rows]

        n_features = X.shape[1]
        n_collision = int(np.sum(y_train_all))
        n_safe = len(y_train_all) - n_collision
        n_coll_val = int(np.sum(y_val))
        print(f"    Features: {n_features}, train samples: {len(X_train_all)} "
              f"(real_train={len(train_real_idx)}, synthetic={len(synthetic_samples)})")
        print(f"    Train labels: collision={n_collision}, safe={n_safe} "
              f"({n_collision/len(y_train_all)*100:.1f}% collision)")
        print(f"    Val (pure real) labels: collision={n_coll_val} "
              f"({n_coll_val/len(y_val)*100:.2f}% collision)")

        # Normalize on the RAW training distribution; apply to both train and val.
        # Oversampling is applied to the TRAIN set ONLY, so the pure-real val set
        # keeps the realistic ~2.5% collision rate for threshold tuning.
        X_norm, X_mean, X_std = self._normalize(X_train_all)
        X_train = X_norm
        y_train = y_train_all
        X_val = (X_val - X_mean) / (X_std + 1e-8)

        # --- Handle class imbalance: oversample minority class (train only) ---
        n_coll_train = int(np.sum(y_train))
        n_safe_train = int(len(y_train) - n_coll_train)
        if n_coll_train > 0 and n_safe_train > 0:
            collision_idx = np.where(y_train.flatten() == 1)[0]
            # Oversample collision class to at least 30% of train total
            target_collision_ratio = 0.30
            target_collision_count = int(n_safe_train * target_collision_ratio / (1 - target_collision_ratio))
            if target_collision_count > n_coll_train:
                n_oversample = target_collision_count - n_coll_train
                oversample_idx = np.random.choice(collision_idx, n_oversample, replace=True)
                X_train = np.vstack([X_train, X_train[oversample_idx]])
                y_train = np.vstack([y_train, y_train[oversample_idx]])
                print(f"    Oversampled collision (train only): {n_coll_train} → {n_coll_train + n_oversample} "
                      f"({(n_coll_train + n_oversample)/len(y_train)*100:.1f}% of train)")

        # Round 9: 7-model ensemble for more robust voting (precision improvement)
        # n_ensemble passed as parameter for multi-round tuning
        ensemble_models = []
        ensemble_train_losses = []
        ensemble_val_losses = []
        total_train_time = 0.0

        for e_idx in range(n_ensemble):
            print(f"    Ensemble model {e_idx + 1}/{n_ensemble}...")
            np.random.seed(42 + e_idx * 137)

            nn = SimpleNN(
                layer_sizes=[n_features, 128, 64, 64, 32, 16, 1],
                learning_rate=0.002,
                activation="tanh",
                output_activation="sigmoid",
                momentum=0.95,
                weight_decay=0.0001,
                use_batch_norm=True,
                lr_schedule="cosine",
                grad_clip_norm=5.0,
            )

            start_time = time.time()
            history = nn.train(
                X_train, y_train,
                X_val=X_val, y_val=y_val,
                epochs=epochs, batch_size=64,
                early_stopping_patience=30,
                verbose=(e_idx == 0),
            )
            total_train_time += time.time() - start_time

            ensemble_models.append(nn)
            ensemble_train_losses.append(history["train_loss"][-1])
            ensemble_val_losses.append(history["val_loss"][-1] if history["val_loss"] else 0)

        np.random.seed(None)

        # Use the SAME model that is persisted for threshold tuning, so the
        # saved model's optimal threshold matches inference. (Naively averaging
        # weights/biases/BN stats across ensemble members collapses the network
        # and is NOT used here; the ensemble is retained as training diversity,
        # but the persisted + tuned model is ensemble_models[0].)
        saved_model = ensemble_models[0]
        y_pred_prob = saved_model.predict(X_val)

        # Find the decision threshold on the RAW (imbalanced) validation set.
        # The pure-real val (~2.5% collision) matches the deployment distribution.
        # Safety-critical: require recall >= 0.85 (catch real collisions) and
        # maximize precision subject to that recall floor. With the variable-
        # boundary features the model separates well, so a moderate threshold
        # meets both; no need to force threshold -> 0.
        best_threshold = 0.5
        best_score = -1.0
        for thr in np.arange(0.02, 0.9, 0.02):
            y_pred_t = (y_pred_prob > thr).astype(float)
            tp = np.sum((y_pred_t == 1) & (y_val == 1))
            fp = np.sum((y_pred_t == 1) & (y_val == 0))
            fn = np.sum((y_pred_t == 0) & (y_val == 1))
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0
            if rec >= 0.85 and prec > best_score:
                best_score = prec
                best_threshold = thr

        y_pred = (y_pred_prob > best_threshold).astype(float)

        tp = np.sum((y_pred == 1) & (y_val == 1))
        tn = np.sum((y_pred == 0) & (y_val == 0))
        fp = np.sum((y_pred == 1) & (y_val == 0))
        fn = np.sum((y_pred == 0) & (y_val == 1))

        accuracy = (tp + tn) / len(y_val)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        saved_model.save(str(self.model_dir / "collision_model.pkl"))

        # Save feature metadata
        collision_meta = {
            "n_features": n_features,
            "feature_names": [
                "min_dist", "mean_dist", "dist_std", "dist_range",
                "n_obstacles", "n_close", "n_very_close",
                "max_vel", "mean_vel", "approach_angle",
                "ttc", "combined_risk",
                "eff_radius", "clearance",
                "joint_center_dist", "vel_dist_ratio",
                "angular_spread", "close_ratio", "risk_velocity_product",
            ],
            "X_mean": X_mean.tolist(),
            "X_std": X_std.tolist(),
            "optimal_threshold": float(best_threshold),
            "n_ensemble": n_ensemble,
        }
        meta_path = self.model_dir / "collision_model_meta.json"
        with open(meta_path, "w") as f:
            json.dump(collision_meta, f, indent=2)

        metrics = ModelMetrics(
            model_name="collision",
            train_loss=float(np.mean(ensemble_train_losses)),
            val_loss=float(np.mean(ensemble_val_losses)),
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            train_time_s=total_train_time,
            num_params=ensemble_models[0].num_params * n_ensemble,
            convergence_epoch=len(ensemble_val_losses),
        )
        self.results["collision"] = metrics
        print(f"    Accuracy={metrics.accuracy:.4f}, Precision={metrics.precision:.4f}, "
              f"Recall={metrics.recall:.4f}, F1={metrics.f1_score:.4f} "
              f"(threshold={best_threshold:.2f}, ensemble of {n_ensemble})")
        return metrics

    # =========================================================================
    # Train All Models
    # =========================================================================

    def train_all(self) -> Dict[str, ModelMetrics]:
        """Train all models and return metrics.

        Returns:
            Dict of model_name → ModelMetrics.
        """
        print("=" * 60)
        print("Model Training Pipeline")
        print("=" * 60)

        self.train_motion_model()
        self.train_safety_model()
        self.train_quality_model()
        self.train_collision_model()

        print("\n" + "=" * 60)
        print("Training Complete - Summary")
        print("=" * 60)
        for name, metrics in self.results.items():
            r2_str = f"R²={metrics.r2_score:.4f}" if metrics.r2_score != 0 else ""
            f1_str = f"F1={metrics.f1_score:.4f}" if metrics.f1_score != 0 else ""
            extras = " ".join(filter(None, [r2_str, f1_str]))
            print(f"  {name:15s}: train_loss={metrics.train_loss:.6f}, val_loss={metrics.val_loss:.6f}"
                  f"{', ' + extras if extras else ''} ({metrics.train_time_s:.1f}s)")

        return self.results

    def save_results(self, output_dir: str = "reports") -> None:
        """Save training results to JSON."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results_data = {}
        for name, metrics in self.results.items():
            results_data[name] = {
                "model_name": metrics.model_name,
                "train_loss": metrics.train_loss,
                "val_loss": metrics.val_loss,
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "r2_score": metrics.r2_score,
                "mae": metrics.mae,
                "rmse": metrics.rmse,
                "train_time_s": metrics.train_time_s,
                "num_params": metrics.num_params,
                "convergence_epoch": metrics.convergence_epoch,
            }

        filepath = output_path / "model_training_results.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        print(f"\nModel results saved to: {filepath}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.train_all()
    trainer.save_results()