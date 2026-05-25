"""Code-authored Verolas workflow templates.

Each module in this directory constructs one TemplateSpec and registers
it via verolas_api.workflow.registry.register_template at import time.
Registration runs once on app startup via bootstrap_workflow_templates.
"""

from __future__ import annotations
