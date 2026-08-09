"""System status and configuration data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SystemConfig(BaseModel):
    """System configuration model."""

    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, description="Configuration description")
    updated_at: datetime = Field(default_factory=datetime.now)


class SystemConfigUpdate(BaseModel):
    """System configuration update request."""

    configs: Dict[str, Any] = Field(..., description="Key-value pairs to update")


class FirmwareInfo(BaseModel):
    """Firmware version information."""

    component: str = Field(..., description="Component name (stm32, openmv, rpi)")
    version: str = Field(..., description="Firmware version")
    build_date: Optional[str] = Field(None, description="Build date")
    checksum: Optional[str] = Field(None, description="Firmware checksum")


class NetworkStatus(BaseModel):
    """Network connectivity status."""

    wifi_connected: bool = Field(False, description="WiFi connection status")
    wifi_ssid: Optional[str] = Field(None, description="WiFi SSID")
    wifi_signal: Optional[int] = Field(None, description="WiFi signal strength (dBm)")
    ip_address: Optional[str] = Field(None, description="Local IP address")
    ethernet_connected: bool = Field(False, description="Ethernet connection status")
    internet_accessible: bool = Field(False, description="Internet accessibility")
    stm32_connected: bool = Field(False, description="STM32 UART connection")
    openmv_connected: bool = Field(False, description="OpenMV UART connection")


class SystemStatus(BaseModel):
    """Overall system status."""

    status: str = Field("running", description="System status (running, error, maintenance)")
    version: str = Field("2.0.0", description="System version")
    uptime_seconds: int = Field(0, description="System uptime in seconds")
    cpu_usage: float = Field(0.0, description="CPU usage percentage")
    memory_usage: float = Field(0.0, description="Memory usage percentage")
    disk_free_gb: float = Field(0.0, description="Free disk space in GB")
    temperature_celsius: float = Field(25.0, description="CPU temperature")
    network: Optional[NetworkStatus] = Field(None, description="Network status")
    firmware: List[FirmwareInfo] = Field(default_factory=list, description="Firmware versions")


class LogEntry(BaseModel):
    """System log entry."""

    id: int = Field(..., description="Log entry ID")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR)")
    source: str = Field(..., description="Source module")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class LogQuery(BaseModel):
    """Log query parameters."""

    level: Optional[str] = Field(None, description="Filter by log level")
    source: Optional[str] = Field(None, description="Filter by source")
    limit: int = Field(50, ge=1, le=200, description="Maximum entries")
    offset: int = Field(0, ge=0, description="Pagination offset")


class DiagnosticResult(BaseModel):
    """System diagnostic check result."""

    name: str = Field(..., description="Check name")
    status: str = Field(..., description="Check status (pass, fail, warning)")
    detail: Optional[str] = Field(None, description="Check detail")
    value: Optional[Any] = Field(None, description="Check value")


class DiagnosticReport(BaseModel):
    """System diagnostic report."""

    timestamp: datetime = Field(default_factory=datetime.now)
    overall: str = Field("pass", description="Overall diagnostic result")
    checks: List[DiagnosticResult] = Field(default_factory=list, description="Individual check results")