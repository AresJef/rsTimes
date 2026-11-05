"""Owned startup fault: no product module is modified to inject a hang."""
import threading

threading.Event().wait()
