"""Connector content sync engines.

One module per source. Each engine takes a `connector_bindings` row
(plus the org's installation credentials) and mirrors the bound
resource into the project's `files` rows + object storage.

Engines are dispatched from `verolas_api.sync.dispatch.sync_binding`
based on the binding's class_id.
"""
