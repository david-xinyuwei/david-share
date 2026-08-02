#!/usr/bin/env python3
from minisweagent.models.litellm_model import LitellmModel

from scripts.provider_compat import remove_provider_specific_fields


class SanitizingOpenAIModel(LitellmModel):
    def _prepare_messages_for_api(self, messages: list[dict]) -> list[dict]:
        prepared = super()._prepare_messages_for_api(messages)
        return remove_provider_specific_fields(prepared)