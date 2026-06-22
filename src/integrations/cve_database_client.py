"""
CVE Database Client - Multi-Source Vulnerability Database Integration

Integrates with multiple CVE sources:
- NVD (National Vulnerability Database)
- Snyk
- GitHub Security Advisories
- OSV (Open Source Vulnerabilities)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CVE:
    """CVE vulnerability information"""

    cve_id: str
    description: str
    severity: str  # low, medium, high, critical
    cvss_score: float
    published_date: datetime
    affected_versions: List[str]
    fixed_versions: List[str]
    source: str  # nvd, snyk, github, osv
    references: List[str]


class CVEDatabaseClient:
    """
    Multi-source CVE database client

    Aggregates vulnerability data from:
    - NVD API
    - Snyk API
    - GitHub Security Advisories API
    - OSV API
    """

    def __init__(
        self,
        nvd_api_key: Optional[str] = None,
        snyk_api_key: Optional[str] = None,
        github_token: Optional[str] = None,
    ):
        """
        Initialize CVE database client

        Args:
            nvd_api_key: NVD API key
            snyk_api_key: Snyk API token
            github_token: GitHub personal access token
        """
        self.nvd_api_key = nvd_api_key
        self.snyk_api_key = snyk_api_key
        self.github_token = github_token
        self.logger = logging.getLogger("cve_database_client")

        # Initialize clients
        self.nvd_client = None
        self.snyk_client = None
        self.github_client = None
        self.osv_client = None

        self._init_clients()

    def _init_clients(self):
        """Initialize API clients"""
        # NVD Client
        if self.nvd_api_key:
            try:
                self.logger.info("NVD API key configured; HTTP adapter is not wired")
            except Exception as e:
                self.logger.error("Failed to init NVD client: %s", e)

        # Snyk Client
        if self.snyk_api_key:
            try:
                self.logger.info("Snyk API key configured; HTTP adapter is not wired")
            except Exception as e:
                self.logger.error("Failed to init Snyk client: %s", e)

        # GitHub Client
        if self.github_token:
            try:
                self.logger.info(
                    "GitHub token configured; security advisory adapter is not wired"
                )
            except Exception as e:
                self.logger.error("Failed to init GitHub client: %s", e)

        self.logger.info("OSV adapter is not wired in the baseline profile")

    async def check_vulnerability(
        self, package_name: str, version: str, ecosystem: str = "pypi"
    ) -> List[CVE]:
        """
        Check for vulnerabilities in a package

        Args:
            package_name: Package name
            version: Package version
            ecosystem: Package ecosystem (pypi, npm, maven, etc.)

        Returns:
            List of CVEs found
        """
        all_cves = []
        if not any(
            [self.nvd_client, self.snyk_client, self.github_client, self.osv_client]
        ):
            self.logger.warning(
                "No CVE sources configured for %s@%s; vulnerability lookup not measured",
                package_name,
                version,
            )
            return []

        # Check NVD
        if self.nvd_client:
            nvd_cves = await self._check_nvd(package_name, version)
            all_cves.extend(nvd_cves)

        # Check Snyk
        if self.snyk_client:
            snyk_cves = await self._check_snyk(package_name, version, ecosystem)
            all_cves.extend(snyk_cves)

        # Check GitHub
        if self.github_client:
            github_cves = await self._check_github(package_name, version, ecosystem)
            all_cves.extend(github_cves)

        # Check OSV
        if self.osv_client:
            osv_cves = await self._check_osv(package_name, version, ecosystem)
            all_cves.extend(osv_cves)

        # Deduplicate by CVE ID
        unique_cves = self._deduplicate_cves(all_cves)

        self.logger.info(
            f"Found {len(unique_cves)} unique CVEs for " f"{package_name}@{version}"
        )

        return unique_cves

    async def _check_nvd(self, package_name: str, version: str) -> List[CVE]:
        """Check NVD database"""
        # https://nvd.nist.gov/developers/vulnerabilities
        self.logger.debug("NVD adapter not wired for %s@%s", package_name, version)
        return []

    async def _check_snyk(
        self, package_name: str, version: str, ecosystem: str
    ) -> List[CVE]:
        """Check Snyk database"""
        # https://snyk.io/api/
        self.logger.debug("Snyk adapter not wired for %s@%s", package_name, version)
        return []

    async def _check_github(
        self, package_name: str, version: str, ecosystem: str
    ) -> List[CVE]:
        """Check GitHub Security Advisories"""
        # https://docs.github.com/en/rest/security-advisories
        self.logger.debug(
            "GitHub advisory adapter not wired for %s@%s", package_name, version
        )
        return []

    async def _check_osv(
        self, package_name: str, version: str, ecosystem: str
    ) -> List[CVE]:
        """Check OSV database"""
        # https://osv.dev/
        self.logger.debug("OSV adapter not wired for %s@%s", package_name, version)
        return []

    def _deduplicate_cves(self, cves: List[CVE]) -> List[CVE]:
        """Deduplicate CVEs by ID, keeping highest severity"""
        cve_dict = {}

        for cve in cves:
            if cve.cve_id not in cve_dict:
                cve_dict[cve.cve_id] = cve
            else:
                # Keep CVE with higher CVSS score
                if cve.cvss_score > cve_dict[cve.cve_id].cvss_score:
                    cve_dict[cve.cve_id] = cve

        return list(cve_dict.values())

    async def get_cve_details(self, cve_id: str) -> Optional[CVE]:
        """
        Get detailed information about a specific CVE

        Args:
            cve_id: CVE identifier (e.g., CVE-2021-12345)

        Returns:
            CVE details or None if not found
        """
        # Try all sources
        sources = [
            self._get_nvd_details,
            self._get_snyk_details,
            self._get_github_details,
            self._get_osv_details,
        ]

        for source_func in sources:
            try:
                cve = await source_func(cve_id)
                if cve:
                    return cve
            except Exception as e:
                self.logger.debug("Source failed for %s: {e}", cve_id)
                continue

        return None

    async def _get_nvd_details(self, cve_id: str) -> Optional[CVE]:
        """Get CVE details from NVD"""
        self.logger.debug("NVD details adapter not wired for %s", cve_id)
        return None

    async def _get_snyk_details(self, cve_id: str) -> Optional[CVE]:
        """Get CVE details from Snyk"""
        self.logger.debug("Snyk details adapter not wired for %s", cve_id)
        return None

    async def _get_github_details(self, cve_id: str) -> Optional[CVE]:
        """Get CVE details from GitHub"""
        self.logger.debug("GitHub advisory details adapter not wired for %s", cve_id)
        return None

    async def _get_osv_details(self, cve_id: str) -> Optional[CVE]:
        """Get CVE details from OSV"""
        self.logger.debug("OSV details adapter not wired for %s", cve_id)
        return None


# Singleton instance
_cve_client: Optional[CVEDatabaseClient] = None


def get_cve_client(
    nvd_api_key: Optional[str] = None,
    snyk_api_key: Optional[str] = None,
    github_token: Optional[str] = None,
) -> CVEDatabaseClient:
    """
    Get or create CVE database client singleton

    Args:
        nvd_api_key: NVD API key
        snyk_api_key: Snyk API token
        github_token: GitHub token

    Returns:
        CVEDatabaseClient instance
    """
    global _cve_client

    if _cve_client is None:
        _cve_client = CVEDatabaseClient(
            nvd_api_key=nvd_api_key,
            snyk_api_key=snyk_api_key,
            github_token=github_token,
        )

    return _cve_client


__all__ = ["CVE", "CVEDatabaseClient", "get_cve_client"]
