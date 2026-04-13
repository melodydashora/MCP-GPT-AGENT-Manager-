"""Eidolon - Secure agent for repository operations."""
from .agent import EidolonAgent
from .auth import SecurityGate

__all__ = ["EidolonAgent", "SecurityGate"]
