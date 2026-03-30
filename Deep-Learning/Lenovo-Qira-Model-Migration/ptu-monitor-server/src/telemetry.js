const { resourceFromAttributes } = require("@opentelemetry/resources");
const {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_NAMESPACE,
  ATTR_SERVICE_INSTANCE_ID,
} = require("@opentelemetry/semantic-conventions");
const { useAzureMonitor } = require("@azure/monitor-opentelemetry");

const serviceName = process.env.OTEL_SERVICE_NAME || "ptu-monitor-server";

if (process.env.APPLICATIONINSIGHTS_CONNECTION_STRING) {
  useAzureMonitor({
    azureMonitorExporterOptions: {
      connectionString: process.env.APPLICATIONINSIGHTS_CONNECTION_STRING,
    },
    tracesPerSecond: 0,
    samplingRatio: 1,
    enableLiveMetrics: true,
    enableStandardMetrics: true,
    instrumentationOptions: {
      http: { enabled: true },
      azureSdk: { enabled: true },
      winston: { enabled: true },
    },
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: serviceName,
      [ATTR_SERVICE_NAMESPACE]: "appinsight-ptu-monitor",
      [ATTR_SERVICE_INSTANCE_ID]: process.env.HOSTNAME || "local",
    }),
  });
} else {
  console.warn("APPLICATIONINSIGHTS_CONNECTION_STRING is not set. Azure Monitor export is disabled.");
}

module.exports = { serviceName };
