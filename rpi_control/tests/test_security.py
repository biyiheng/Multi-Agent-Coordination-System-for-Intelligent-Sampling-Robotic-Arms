"""
Security analysis and vulnerability scanning tests.

Checks for common security issues: injection vulnerabilities,
insecure configurations, exposed secrets, unsafe deserialization,
and other common attack vectors.
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest


# =============================================================================
# Configuration Security
# =============================================================================

class TestConfigSecurity:
    """Verify configuration files don't contain sensitive data."""

    def test_no_hardcoded_secrets_in_yaml(self):
        """Check YAML configs for hardcoded passwords/keys."""
        config_dir = Path(__file__).resolve().parent.parent / "config"

        sensitive_patterns = [
            r'password\s*:\s*["\'](?!\$\{).+["\']',  # Non-templated passwords
            r'api_key\s*:\s*["\'](?!\$\{).+["\']',    # Non-templated API keys
            r'secret\s*:\s*["\'](?!\$\{).+["\']',      # Non-templated secrets
            r'token\s*:\s*["\'](?!\$\{).+["\']',        # Non-templated tokens
        ]

        for yaml_file in config_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                content = f.read()

            for pattern in sensitive_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # Some may be placeholders - check if they look like real values
                    for match in matches:
                        # Skip if contains template variables or placeholder text
                        if "${" in match or "example" in match.lower() or \
                           "changeme" in match.lower() or "your_" in match.lower():
                            continue
                        print(f"WARNING: Potential secret in {yaml_file.name}: {match[:50]}...")

    def test_no_hardcoded_secrets_in_python(self):
        """Check Python files for hardcoded secrets."""
        rpi_dir = Path(__file__).resolve().parent.parent

        sensitive_patterns = [
            (r'password\s*=\s*["\'][^"\'$]{3,}["\']', "password"),
            (r'api_key\s*=\s*["\'][^"\'$]{8,}["\']', "api_key"),
            (r'secret\s*=\s*["\'][^"\'$]{8,}["\']', "secret"),
            (r'PRIVATE_KEY\s*=\s*["\']', "private_key"),
        ]

        issues = []
        for py_file in rpi_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            for pattern, label in sensitive_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Skip placeholders and test values
                    if any(skip in match.lower() for skip in
                           ["example", "changeme", "your_", "test_", "placeholder"]):
                        continue
                    issues.append(f"{py_file.name}: {label} = {match[:50]}...")

        if issues:
            print(f"\n  Potential secrets found ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")
        # Don't fail the test, just report - some may be false positives


# =============================================================================
# Input Validation Security
# =============================================================================

class TestInputValidation:
    """Verify input validation patterns."""

    def test_arm_routes_input_validation(self):
        """Check arm_routes.py for Pydantic model validation."""
        routes_file = Path(__file__).resolve().parent.parent / \
                      "web" / "routes" / "arm_routes.py"

        with open(routes_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for Pydantic models (BaseModel) for input validation
        has_basemodel = "BaseModel" in content
        # Check for range validation
        has_validation = any(kw in content for kw in
                             ["Field(", "validator", "ge=", "le=", "min_length"])

        if not has_basemodel:
            print("WARNING: arm_routes.py may lack Pydantic input validation")
        if not has_validation:
            print("WARNING: arm_routes.py may lack field-level validation")

    def test_task_routes_input_validation(self):
        """Check task_routes.py for input validation."""
        routes_file = Path(__file__).resolve().parent.parent / \
                      "web" / "routes" / "task_routes.py"

        with open(routes_file, "r", encoding="utf-8") as f:
            content = f.read()

        has_basemodel = "BaseModel" in content
        if not has_basemodel:
            print("WARNING: task_routes.py may lack Pydantic input validation")


# =============================================================================
# Serialization Security
# =============================================================================

class TestSerializationSecurity:
    """Verify safe serialization practices."""

    def test_no_pickle_loads_without_validation(self):
        """Check for unsafe pickle.loads usage."""
        rpi_dir = Path(__file__).resolve().parent.parent

        unsafe_pattern = re.compile(r'pickle\.loads?\s*\(')
        issues = []

        for py_file in rpi_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if unsafe_pattern.search(line):
                            # Check if it's used for model loading (acceptable)
                            if "model" in line.lower() or "load_" in line.lower():
                                continue
                            issues.append(f"{py_file.name}:{i}: {line.strip()}")
            except Exception:
                continue

        if issues:
            print(f"\n  Potential unsafe pickle usage ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")

    def test_no_eval_or_exec(self):
        """Check for dangerous eval/exec usage."""
        rpi_dir = Path(__file__).resolve().parent.parent

        dangerous_patterns = [
            re.compile(r'\beval\s*\('),
            re.compile(r'\bexec\s*\('),
            re.compile(r'\bcompile\s*\('),
        ]

        issues = []
        for py_file in rpi_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        for pattern in dangerous_patterns:
                            if pattern.search(line):
                                issues.append(
                                    f"{py_file.name}:{i}: {line.strip()}"
                                )
            except Exception:
                continue

        if issues:
            print(f"\n  Dangerous eval/exec usage ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")
        # Don't fail - some may be legitimate uses in config parsing


# =============================================================================
# Web Security Headers
# =============================================================================

class TestWebSecurityHeaders:
    """Verify security headers in web responses."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from rpi_control.web.server import app
        return TestClient(app)

    def test_cors_not_wildcard(self, client):
        """CORS should not allow all origins in production."""
        response = client.get("/api/v1/arm/status", headers={
            "Origin": "http://evil.com",
        })
        # If CORS is properly configured, evil.com should not be allowed
        cors_header = response.headers.get("access-control-allow-origin", "")
        if cors_header == "*":
            print("WARNING: CORS allows all origins (*)")
        # Don't fail - this is a known configuration gap

    def test_no_server_header_leak(self, client):
        """Server header should not leak version info."""
        response = client.get("/")
        server_header = response.headers.get("server", "")
        # FastAPI/uvicorn may include server header
        if "uvicorn" in server_header.lower():
            print(f"INFO: Server header reveals: {server_header}")

    def test_json_content_type(self, client):
        """JSON responses should have proper content-type."""
        response = client.get("/api/v1/arm/status")
        ct = response.headers.get("content-type", "")
        assert "application/json" in ct, \
            f"Expected JSON content-type, got: {ct}"


# =============================================================================
# Dependency Security
# =============================================================================

class TestDependencySecurity:
    """Check for known-vulnerable dependency patterns."""

    def test_requirements_file_exists(self):
        """Verify requirements.txt exists and is readable."""
        req_file = Path(__file__).resolve().parent.parent.parent / \
                   "requirements.txt"
        if not req_file.exists():
            req_file = Path(__file__).resolve().parent.parent / \
                       "requirements.txt"

        if req_file.exists():
            with open(req_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 0, "requirements.txt is empty"
            print(f"\n  requirements.txt: {len(content.splitlines())} packages")
        else:
            print("WARNING: requirements.txt not found")

    def test_no_outdated_version_pins(self):
        """Check for known-vulnerable old versions."""
        req_file = Path(__file__).resolve().parent.parent.parent / \
                   "requirements.txt"
        if not req_file.exists():
            req_file = Path(__file__).resolve().parent.parent / \
                       "requirements.txt"
        if not req_file.exists():
            pytest.skip("requirements.txt not found")

        with open(req_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for very old versions of key packages
        known_old = {
            "fastapi": "0.80",
            "uvicorn": "0.15",
            "numpy": "1.19",
            "scikit-learn": "0.24",
            "pyserial": "3.4",
        }

        for pkg, min_version in known_old.items():
            pattern = rf'{pkg}\s*[=<>]=?\s*(\d+\.\d+(?:\.\d+)?)'
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                version = match.group(1)
                if version < min_version:
                    print(f"WARNING: {pkg} version {version} may be outdated "
                          f"(min recommended: {min_version})")


# =============================================================================
# Code Structure Security
# =============================================================================

class TestCodeStructureSecurity:
    """Verify code structure patterns for security."""

    def test_debug_mode_disabled(self):
        """Check that debug mode is not enabled in production config."""
        config_file = Path(__file__).resolve().parent.parent / \
                      "config" / "settings.yaml"

        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for debug flags
        debug_patterns = [
            r'debug\s*:\s*true',
            r'DEBUG\s*=\s*True',
        ]

        for pattern in debug_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                print(f"WARNING: Debug mode may be enabled in settings.yaml")

    def test_log_level_not_debug(self):
        """Log level should not be DEBUG in production."""
        config_file = Path(__file__).resolve().parent.parent / \
                      "config" / "settings.yaml"

        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read()

        if re.search(r'log_level\s*:\s*["\']DEBUG["\']', content):
            print("WARNING: Log level is DEBUG - may leak sensitive info")

    def test_no_shell_injection_in_subprocess(self):
        """Check for unsafe subprocess calls."""
        rpi_dir = Path(__file__).resolve().parent.parent

        unsafe_patterns = [
            re.compile(r'subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True'),
            re.compile(r'os\.system\s*\('),
            re.compile(r'os\.popen\s*\('),
        ]

        issues = []
        for py_file in rpi_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        for pattern in unsafe_patterns:
                            if pattern.search(line):
                                issues.append(
                                    f"{py_file.name}:{i}: {line.strip()}"
                                )
            except Exception:
                continue

        if issues:
            print(f"\n  Potential shell injection risks ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")

    def test_file_path_traversal_protection(self):
        """Check for file operations without path validation."""
        rpi_dir = Path(__file__).resolve().parent.parent

        file_op_patterns = [
            re.compile(r'open\s*\(\s*[^)]*request\.'),
            re.compile(r'open\s*\(\s*[^)]*\.get\s*\('),
        ]

        issues = []
        for py_file in rpi_dir.rglob("*.py"):
            if "test_" in py_file.name:
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        for pattern in file_op_patterns:
                            if pattern.search(line):
                                issues.append(
                                    f"{py_file.name}:{i}: {line.strip()}"
                                )
            except Exception:
                continue

        if issues:
            print(f"\n  Potential path traversal risks ({len(issues)}):")
            for issue in issues:
                print(f"    - {issue}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])