"""License risk scanner package."""

try:
    from startup_risk.scanners.license_scanner.scanner import LicenseRiskScanner
except ModuleNotFoundError:
    LicenseRiskScanner = None  # type: ignore[assignment]

__all__ = [
    "LicenseRiskScanner",
]
