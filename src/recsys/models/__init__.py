"""Recommenders. Each one is fit on a list of baskets and scores every variant in the
universe for a given context and date. Models never see the date of the query as a
feature; it is passed only so a model can refuse to score what did not exist yet."""
from .base import Model
from .copurchase import CoPurchase
from .popularity import Popularity

__all__ = ["Model", "Popularity", "CoPurchase"]
