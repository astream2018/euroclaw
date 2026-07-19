"""EuroClaw connector-generator subsystem (out-of-process developer tool).

Generated connector code is UNTRUSTED and must be reviewed before enabling.
"""

from euroclaw.connectors.generator import ConnectorGenerator
from euroclaw.connectors.spec import (
    ConnectorAuth,
    ConnectorManifest,
    ConnectorTool,
    validate_connector_dir,
)

__all__ = [
    "ConnectorManifest",
    "ConnectorAuth",
    "ConnectorTool",
    "ConnectorGenerator",
    "validate_connector_dir",
]
