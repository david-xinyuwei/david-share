"""
Telemetry and logging for MedImageParse application
Integrates with Azure Application Insights
"""
import os
import uuid
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Correlation ID for distributed tracing
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> str:
    """Get or create correlation ID for current request"""
    correlation_id = correlation_id_var.get()
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
    return correlation_id


def reset_correlation_id():
    """Reset correlation ID (call at start of new request)"""
    new_id = str(uuid.uuid4())
    correlation_id_var.set(new_id)
    return new_id


class TelemetryLogger:
    """Enhanced logger with Application Insights integration"""
    
    def __init__(self, name: str = "MedImageParse"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Try to initialize Application Insights
        self._setup_app_insights()
    
    def _setup_app_insights(self):
        """Setup Application Insights if available"""
        connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
        if connection_string:
            try:
                from opencensus.ext.azure.log_exporter import AzureLogHandler
                azure_handler = AzureLogHandler(connection_string=connection_string)
                self.logger.addHandler(azure_handler)
            except ImportError:
                self.logger.warning("opencensus-ext-azure not installed, Application Insights disabled")
            except Exception as e:
                self.logger.warning(f"Could not initialize Application Insights: {e}")
    
    def _add_correlation_id(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add correlation ID to log extra data"""
        if extra is None:
            extra = {}
        extra['correlation_id'] = get_correlation_id()
        return extra
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with correlation ID"""
        self.logger.info(message, extra=self._add_correlation_id(extra))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with correlation ID"""
        self.logger.warning(message, extra=self._add_correlation_id(extra))
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error message with correlation ID"""
        self.logger.error(message, extra=self._add_correlation_id(extra))
    
    def exception(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log exception with correlation ID"""
        self.logger.exception(message, extra=self._add_correlation_id(extra))
    
    def track_event(self, event_name: str, properties: Optional[Dict[str, Any]] = None):
        """Track custom event"""
        properties = properties or {}
        properties['correlation_id'] = get_correlation_id()
        self.info(f"Event: {event_name}", extra={'properties': properties})


# Global telemetry logger instance
telemetry = TelemetryLogger()
