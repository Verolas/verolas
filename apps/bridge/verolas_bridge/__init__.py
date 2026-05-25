"""Verolas Bridge agent.

A long-running daemon that runs inside a firm's network (or on an
engineer's Windows workstation) and connects locally installed
engineering software to the Verolas cloud.

The agent polls the cloud for `bridge_jobs`, dispatches them to the
right local tool adapter (SOFiSTiK / RFEM / Tekla / ...), and posts
the result back. Tool adapters land in subsequent releases; this
package ships the polling loop and the wire protocol.
"""

__version__ = "0.0.0"
