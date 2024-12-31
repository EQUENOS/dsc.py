# SPDX-License-Identifier: MIT


def pdm_build_initialize(context):
    metadata = context.config.metadata
    metadata["optional-dependencies"]["discord"] = ["discord-disnake"]
