"""
Observability utilities for Application Insights integration
Provides logging, tracing, and correlation ID tracking
"""

import os
import uuid
import logging
from typing import Optional
from datetime import datetime

try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.azure import metrics_exporter
    from opencensus.stats import aggregation as aggregation_module
    from opencensus.stats import measure as measure_module
    from opencensus.stats import stats as stats_module
    from opencensus.stats import view as view_module
    from opencensus.tags import tag_map as tag_map_module
    APPINSIGHTS_AVAILABLE = True
except ImportError:
    APPINSIGHTS_AVAILABLE = False
    print("Warning: Application Insights SDK not installed. Observability features disabled.")

class ObservabilityManager:
    """
    Manager for Application Insights integration
    Provides correlation IDs, structured logging, and metrics tracking
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the observability manager
        
        Args:
            connection_string: Application Insights connection string
                              If not provided, will try to load from APPINSIGHTS_CONNECTION_STRING env var
        """
        self.connection_string = connection_string or os.getenv('APPINSIGHTS_CONNECTION_STRING')
        self.correlation_id = str(uuid.uuid4())
        self.enabled = APPINSIGHTS_AVAILABLE and bool(self.connection_string)
        
        if self.enabled:
            self._setup_logger()
            self._setup_metrics()
        else:
            self._setup_basic_logger()
    
    def _setup_basic_logger(self):
        """Setup basic logger when Application Insights is not available"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [CorrelationId: %(correlation_id)s] - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _setup_logger(self):
        """Setup logger with Application Insights integration"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Add Azure Log Handler
        azure_handler = AzureLogHandler(connection_string=self.connection_string)
        azure_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(azure_handler)
        
        # Also add console handler for local visibility
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [CorrelationId: %(correlation_id)s] - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        print(f"Application Insights enabled with correlation ID: {self.correlation_id}")
    
    def _setup_metrics(self):
        """Setup metrics tracking"""
        if not self.enabled:
            return
        
        try:
            # Create metrics exporter
            self.metrics_exporter = metrics_exporter.new_metrics_exporter(
                connection_string=self.connection_string
            )
            
            # Setup stats recorder
            self.stats = stats_module.stats
            self.view_manager = self.stats.view_manager
            self.stats_recorder = self.stats.stats_recorder
            
        except Exception as e:
            print(f"Warning: Could not setup metrics: {e}")
    
    def log_info(self, message: str, **kwargs):
        """Log info message with correlation ID"""
        extra = {'correlation_id': self.correlation_id}
        extra.update(kwargs)
        self.logger.info(message, extra=extra)
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message with correlation ID"""
        extra = {'correlation_id': self.correlation_id}
        extra.update(kwargs)
        self.logger.warning(message, extra=extra)
    
    def log_error(self, message: str, **kwargs):
        """Log error message with correlation ID"""
        extra = {'correlation_id': self.correlation_id}
        extra.update(kwargs)
        self.logger.error(message, extra=extra)
    
    def log_exception(self, message: str, exception: Exception, **kwargs):
        """Log exception with correlation ID"""
        extra = {'correlation_id': self.correlation_id, 'exception_type': type(exception).__name__}
        extra.update(kwargs)
        self.logger.exception(f"{message}: {str(exception)}", extra=extra)
    
    def track_metric(self, metric_name: str, value: float, **properties):
        """
        Track a custom metric
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            **properties: Additional properties to attach to the metric
        """
        if not self.enabled:
            print(f"Metric: {metric_name} = {value}")
            return
        
        try:
            # Add correlation ID to properties
            props = {'correlation_id': self.correlation_id}
            props.update(properties)
            
            # Log as structured data
            self.log_info(f"Metric: {metric_name}", metric_value=value, **props)
        except Exception as e:
            print(f"Warning: Could not track metric: {e}")
    
    def track_request(self, name: str, duration_ms: float, success: bool, **properties):
        """
        Track a request/operation
        
        Args:
            name: Name of the request/operation
            duration_ms: Duration in milliseconds
            success: Whether the request was successful
            **properties: Additional properties
        """
        props = {
            'correlation_id': self.correlation_id,
            'duration_ms': duration_ms,
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        }
        props.update(properties)
        
        status = "Success" if success else "Failed"
        self.log_info(f"Request: {name} - {status}", **props)
    
    def get_correlation_id(self) -> str:
        """Get the current correlation ID"""
        return self.correlation_id
    
    def new_correlation_id(self) -> str:
        """Generate and set a new correlation ID"""
        self.correlation_id = str(uuid.uuid4())
        return self.correlation_id


# Global instance
_observability_manager: Optional[ObservabilityManager] = None

def get_observability_manager() -> ObservabilityManager:
    """Get or create the global observability manager"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager

def init_observability(connection_string: Optional[str] = None) -> ObservabilityManager:
    """
    Initialize the global observability manager
    
    Args:
        connection_string: Application Insights connection string
    
    Returns:
        ObservabilityManager instance
    """
    global _observability_manager
    _observability_manager = ObservabilityManager(connection_string)
    return _observability_manager
