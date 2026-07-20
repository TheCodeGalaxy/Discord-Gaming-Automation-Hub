"""Startup-based channel scheduler for automated Discord posts.

Replaces the n8n webhook scheduling for the five poster channels.
Uses SQLite persistence to guarantee at-most-once publication per period.
"""
