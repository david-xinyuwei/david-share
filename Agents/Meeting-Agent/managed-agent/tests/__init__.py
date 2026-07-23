import os

os.environ["OTEL_EXPERIMENTAL_RESOURCE_DETECTORS"] = "service_instance,otel"
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
"""Test-only support package for Meeting Agent."""