"""Brand configuration for the chatbot.

This module loads brand-specific settings from environment variables,
making it easy to switch the chatbot between different brands without code changes.
"""
import os
from dataclasses import dataclass


@dataclass
class BrandConfig:
    """Brand configuration settings."""

    # Core brand identity
    name: str  # e.g., "GroundCoverGroup"
    product_line: str  # e.g., "Ecostyle"
    assistant_name: str  # e.g., "GroundCover"

    # Topic validation (comma-separated list of relevant topics)
    relevant_topics: str  # e.g., "tuinieren, Ecostyle, GroundCover, producten"

    # Welcome messages
    welcome_message_nl: str
    welcome_message_en: str

    # Support header text
    support_header: str

    @classmethod
    def from_env(cls) -> "BrandConfig":
        """Load brand configuration from environment variables."""
        name = os.environ.get("BRAND_NAME", "GroundCoverGroup")
        product_line = os.environ.get("BRAND_PRODUCT_LINE", "Ecostyle")
        assistant_name = os.environ.get("BRAND_ASSISTANT_NAME", "GroundCover")

        # Default relevant topics
        default_topics = f"tuinieren, {product_line}, {name}, producten, gardening, products"
        relevant_topics = os.environ.get("BRAND_RELEVANT_TOPICS", default_topics)

        # Default welcome messages with brand interpolation
        default_welcome_nl = f"Hallo! Ik ben de {assistant_name} assistent. Hoe kan ik je helpen?"
        default_welcome_en = f"Hello! I'm the {assistant_name} assistant. How can I help you?"

        welcome_nl = os.environ.get("BRAND_WELCOME_NL", default_welcome_nl)
        welcome_en = os.environ.get("BRAND_WELCOME_EN", default_welcome_en)

        support_header = os.environ.get("BRAND_SUPPORT_HEADER", f"{assistant_name} Support")

        return cls(
            name=name,
            product_line=product_line,
            assistant_name=assistant_name,
            relevant_topics=relevant_topics,
            welcome_message_nl=welcome_nl,
            welcome_message_en=welcome_en,
            support_header=support_header,
        )


# Global singleton instance
_brand_config: BrandConfig | None = None


def get_brand_config() -> BrandConfig:
    """Get the brand configuration singleton."""
    global _brand_config
    if _brand_config is None:
        _brand_config = BrandConfig.from_env()
    return _brand_config


def reload_brand_config() -> BrandConfig:
    """Reload brand configuration from environment (useful for testing)."""
    global _brand_config
    _brand_config = BrandConfig.from_env()
    return _brand_config
