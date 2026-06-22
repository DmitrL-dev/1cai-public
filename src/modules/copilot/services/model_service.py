"""
Model Service
"""
import os
from typing import Any, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class ModelService:
    """Service for managing AI model and tokenizer"""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.device = "cpu"
        self._load_model()

    def _load_model(self):
        """Attempt to load fine-tuned model"""
        try:
            model_path = os.getenv("COPILOT_MODEL_PATH", "./models/1c-copilot-lora")

            if os.path.exists(model_path):
                logger.info("Loading Copilot model", extra={"model_path": model_path})

                try:
                    import torch
                    from peft import PeftModel
                    from transformers import AutoModelForCausalLM, AutoTokenizer

                    # Determine device
                    self.device = "cuda" if torch.cuda.is_available() else "cpu"
                    logger.info("Using device", extra={"device": self.device})

                    # Load base model
                    base_model_name = os.getenv(
                        "BASE_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct"
                    )

                    logger.info(
                        "Loading base model",
                        extra={"base_model_name": base_model_name},
                    )
                    base_model = AutoModelForCausalLM.from_pretrained(
                        base_model_name,
                        device_map="auto",
                        torch_dtype=(
                            torch.float16 if self.device == "cuda" else torch.float32
                        ),
                        low_cpu_mem_usage=True,
                    )

                    # Load LoRA adapter
                    logger.info("Loading LoRA adapter...")
                    self.model = PeftModel.from_pretrained(base_model, model_path)

                    # Load tokenizer
                    self.tokenizer = AutoTokenizer.from_pretrained(model_path)

                    self.model.eval()  # Set to evaluation mode
                    self.model_loaded = True

                    logger.info("✅ Copilot model loaded successfully!")

                except ImportError as e:
                    logger.warning(
                        "Required libraries not installed",
                        extra={"error": str(e), "error_type": type(e).__name__},
                    )
                    logger.warning("Install with: pip install transformers peft torch")
                except Exception as e:
                    logger.error(
                        "Failed to load model",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "model_path": model_path,
                        },
                        exc_info=True,
                    )
            else:
                logger.info(
                    "Model path not found, using rule-based fallback",
                    extra={"model_path": model_path},
                )

        except Exception as e:
            logger.error(
                "Copilot initialization error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

    def get_model(self) -> Optional[Any]:
        """Get loaded model"""
        return self.model

    def get_tokenizer(self) -> Optional[Any]:
        """Get loaded tokenizer"""
        return self.tokenizer

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model_loaded

    def get_device(self) -> str:
        """Get current device"""
        return self.device
