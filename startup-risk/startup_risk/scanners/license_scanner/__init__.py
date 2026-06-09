"""License risk scanner package."""

__all__ = [
    "LicenseRiskScanner",
]


def __getattr__(name: str):
    if name == "LicenseRiskScanner":
        from startup_risk.scanners.license_scanner.scanner import LicenseRiskScanner

        return LicenseRiskScanner
    raise AttributeError(name)
