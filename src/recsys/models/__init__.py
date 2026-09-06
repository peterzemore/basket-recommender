"""Recommenders. Each one is fit on a list of baskets and scores every variant in the
universe for a given context and date. Models never see the date of the query as a
feature; it is passed only so a model can refuse to score what did not exist yet."""
from .base import Model
from .content import AttributeCooccurrence, ContentCosine
from .copurchase import CoPurchase
from .hybrid import Hybrid
from .itemitem import ItemItem
from .popularity import Popularity

__all__ = ["Model", "Popularity", "CoPurchase", "ItemItem", "ContentCosine", "AttributeCooccurrence", "Hybrid"]
