"""
TRIPLE:
  Skill: azure-servicebus-py
  Prompt: "Using azure-servicebus-py skill, write a Python script that sends a document-ingestion
           message to a Service Bus queue using DefaultAzureCredential, then receives it with
           peek-lock and settles (complete or dead-letter on parse failure)."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-servicebus-py
"""
import json
import os
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

namespace = os.environ["SERVICEBUS_NAMESPACE"]  # <namespace>.servicebus.windows.net
queue_name = os.environ.get("SERVICEBUS_QUEUE", "document-ingestion")
credential = DefaultAzureCredential()

client = ServiceBusClient(fully_qualified_namespace=namespace, credential=credential)

# Send
with client.get_queue_sender(queue_name) as sender:
    msg = ServiceBusMessage(
        body=json.dumps({"blob_url": "https://storage/container/doc.pdf", "action": "index"}),
        content_type="application/json",
        subject="document-ingestion",
    )
    sender.send_messages(msg)
    print(f"Sent message to queue '{queue_name}'")

# Receive with peek-lock
with client.get_queue_receiver(queue_name, max_wait_time=10) as receiver:
    for msg in receiver:
        try:
            body = json.loads(str(msg))
            print(f"Received: {body}")
            receiver.complete_message(msg)
            print("  → completed")
        except json.JSONDecodeError:
            receiver.dead_letter_message(msg, reason="parse_failure", error_description="Invalid JSON")
            print("  → dead-lettered (invalid JSON)")
