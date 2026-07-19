# -*- coding: utf-8 -*-
"""Generic WSGI entrypoint for hosts that look for wsgi:application."""

from __future__ import annotations

from app import app


application = app
