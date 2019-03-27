#!/usr/bin/env python3

import logging

logger = logging.getLogger(__name__)

from app import MATRIX_AGENT

def proactive(body):
    MATRIX_AGENT.proactive_message(body)
    return '', 204

