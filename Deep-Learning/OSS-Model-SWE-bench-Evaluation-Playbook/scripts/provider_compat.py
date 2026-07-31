#!/usr/bin/env python3


def remove_provider_specific_fields(messages: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in message.items() if key != "provider_specific_fields"}
        for message in messages
    ]