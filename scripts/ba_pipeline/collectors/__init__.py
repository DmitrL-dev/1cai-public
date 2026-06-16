
"""
Collector registry for BA data pipeline.
"""

from .conference import ConferenceCollector
from .internal_usage import InternalUsageCollector
from .job_market import JobMarketCollector
from .regulation import RegulationCollector

__all__ = [
    "ConferenceCollector",
    "InternalUsageCollector",
    "JobMarketCollector",
    "RegulationCollector",
]

